from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.service import Service
from app.db.repositories.booking_repository import BookingRepository
from app.db.repositories.business_repository import BusinessRepository
from app.db.repositories.staff_repository import StaffRepository

logger = structlog.get_logger(__name__)

HOLD_PREFIX = "slot_hold"
COOLDOWN_PREFIX = "slot_cooldown"


def slot_hold_key(staff_id: UUID, start_time: datetime) -> str:
    """Hold keys are per-staff-per-time. The capacity unit is a stylist's
    chair, not a service — two customers booking different services with the
    same stylist still conflict, while the same time with different stylists
    does not."""
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    return f"{HOLD_PREFIX}:{staff_id}:{start_time.isoformat()}"


def slot_cooldown_key(user_id: UUID, start_time: datetime) -> str:
    """Cooldown is keyed by (user, time) only — *not* by service. Otherwise a
    user could cancel a 30-min haircut at 10:00 and immediately rebook a
    different service at the same time, defeating the cooldown's purpose."""
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    return f"{COOLDOWN_PREFIX}:{user_id}:{start_time.isoformat()}"


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _staff_free_at(
    redis: Redis,
    booking_repo: BookingRepository,
    staff_id: UUID,
    start: datetime,
    end: datetime,
) -> bool:
    """True if the given staff has no Redis hold AND no confirmed-booking
    overlap for the [start, end) range."""
    if await redis.get(slot_hold_key(staff_id, start)):
        return False
    if await booking_repo.has_overlap(start, end, staff_id=staff_id):
        return False
    return True


async def get_slots(
    db: AsyncSession,
    redis: Redis,
    service: Service,
    target_date: date,
    user_id: UUID | None = None,
    staff_id: UUID | None = None,
) -> list[dict]:
    """Return per-slot availability for `target_date`.

    When `staff_id` is given, availability reflects only that stylist. When
    it isn't, a slot is "available" if at least one active staff member who
    offers this service is free at that time — i.e. union availability,
    matching the customer-facing "any stylist" UX."""
    business_repo = BusinessRepository(db)

    if await business_repo.is_date_blocked(target_date):
        logger.debug("slots_skipped_blocked_date", date=target_date.isoformat())
        return []

    hours = await business_repo.get_hours_for_day(target_date.weekday())
    if not hours or hours.is_closed:
        logger.debug("slots_skipped_closed_day", date=target_date.isoformat())
        return []

    # Pre-resolve which staff are eligible for this service. With one staff
    # (the post-migration default) this is a single row; with N staff it's at
    # most N rows. Either way, fetched once per call rather than per slot.
    staff_repo = StaffRepository(db)
    eligible_staff = await staff_repo.get_active_for_service(service.id)
    if staff_id is not None:
        eligible_staff = [s for s in eligible_staff if s.id == staff_id]
    if not eligible_staff:
        logger.debug("slots_skipped_no_staff", service_id=str(service.id), staff_id=str(staff_id))
        return []

    # Business hours are stored as wall-clock times in the salon's local timezone.
    # Building datetimes with ZoneInfo means Python converts them correctly when
    # comparing against UTC booking times — no manual offset arithmetic needed.
    salon_tz = ZoneInfo(settings.SALON_TIMEZONE)

    duration = timedelta(minutes=service.duration_minutes)
    slot_start = datetime(
        target_date.year, target_date.month, target_date.day,
        hours.open_time.hour, hours.open_time.minute,
        tzinfo=salon_tz,
    )
    day_close = datetime(
        target_date.year, target_date.month, target_date.day,
        hours.close_time.hour, hours.close_time.minute,
        tzinfo=salon_tz,
    )
    now = datetime.now(timezone.utc)
    min_bookable = now + timedelta(minutes=settings.MIN_LEAD_MINUTES)

    starts: list[datetime] = []
    current = slot_start
    while current + duration <= day_close:
        starts.append(current)
        current += duration

    booking_repo = BookingRepository(db)

    slots: list[dict] = []
    for start in starts:
        end = start + duration

        # Hide slots inside the lead window. Compares absolute instants, so
        # the result is identical regardless of which timezone `start` is in.
        if start < min_bookable:
            continue

        # Find any free stylist. Returning the first match is enough to call
        # the slot "available"; the booking step picks which one definitively.
        any_free = False
        all_held = True  # only relevant for the all-staff case
        for s in eligible_staff:
            if await redis.get(slot_hold_key(s.id, start)):
                continue  # held — try next staff
            if await booking_repo.has_overlap(start, end, staff_id=s.id):
                all_held = False  # this one is booked, not held
                continue
            any_free = True
            all_held = False
            break

        if any_free:
            if user_id and await redis.exists(slot_cooldown_key(user_id, start)):
                slots.append({"start_time": start, "end_time": end, "status": "cooldown"})
            else:
                slots.append({"start_time": start, "end_time": end, "status": "available"})
            continue

        # No staff free. Distinguish "held" (eligible to retry shortly) from
        # "booked" (stuck for the rest of the day). With one stylist the two
        # cases are crisp; with multiple, "held" means every offering staff
        # is currently held — typically rare.
        slots.append({
            "start_time": start,
            "end_time": end,
            "status": "held" if all_held else "booked",
        })

    logger.debug(
        "slots_calculated",
        date=target_date.isoformat(),
        service_id=str(service.id),
        staff_id=str(staff_id) if staff_id else None,
        salon_tz=settings.SALON_TIMEZONE,
        total=len(slots),
    )
    return slots
