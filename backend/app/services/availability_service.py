from datetime import date, datetime, time as time_t, timedelta, timezone
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
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    return f"{HOLD_PREFIX}:{staff_id}:{start_time.isoformat()}"


def slot_cooldown_key(user_id: UUID, start_time: datetime) -> str:
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    return f"{COOLDOWN_PREFIX}:{user_id}:{start_time.isoformat()}"


def _wall_time(target_date: date, value: time_t, salon_tz: ZoneInfo) -> datetime:
    return datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        value.hour,
        value.minute,
        tzinfo=salon_tz,
    )


def _starts_for_hours(target_date: date, open_time: time_t, close_time: time_t, duration: timedelta) -> list[datetime]:
    salon_tz = ZoneInfo(settings.SALON_TIMEZONE)
    slot_start = _wall_time(target_date, open_time, salon_tz)
    day_close = _wall_time(target_date, close_time, salon_tz)
    starts: list[datetime] = []
    current = slot_start
    while current + duration <= day_close:
        starts.append(current)
        current += duration
    return starts


async def get_slots(
    db: AsyncSession,
    redis: Redis,
    service: Service,
    target_date: date,
    user_id: UUID | None = None,
    staff_id: UUID | None = None,
) -> list[dict]:
    """Return per-slot availability for a service and optional staff member."""
    business_repo = BusinessRepository(db)

    if await business_repo.is_date_blocked(target_date):
        logger.debug("slots_skipped_blocked_date", date=target_date.isoformat())
        return []

    global_hours = await business_repo.get_hours_for_day(target_date.weekday())

    staff_repo = StaffRepository(db)
    eligible_staff = await staff_repo.get_active_for_service(service.id)
    if staff_id is not None:
        eligible_staff = [s for s in eligible_staff if s.id == staff_id]
    if not eligible_staff:
        logger.debug("slots_skipped_no_staff", service_id=str(service.id), staff_id=str(staff_id))
        return []

    duration = timedelta(minutes=service.duration_minutes)
    starts_by_staff: dict[datetime, list[UUID]] = {}
    for staff in eligible_staff:
        staff_hours = await staff_repo.get_hours_for_day(staff.id, target_date.weekday())
        effective_hours = staff_hours or global_hours
        if not effective_hours or effective_hours.is_closed:
            continue
        for start in _starts_for_hours(
            target_date,
            effective_hours.open_time,
            effective_hours.close_time,
            duration,
        ):
            starts_by_staff.setdefault(start, []).append(staff.id)

    if not starts_by_staff:
        logger.debug(
            "slots_skipped_closed_day",
            date=target_date.isoformat(),
            staff_id=str(staff_id) if staff_id else None,
        )
        return []

    booking_repo = BookingRepository(db)
    min_bookable = datetime.now(timezone.utc) + timedelta(minutes=settings.MIN_LEAD_MINUTES)

    slots: list[dict] = []
    for start in sorted(starts_by_staff):
        end = start + duration

        if start < min_bookable:
            continue

        any_free = False
        all_held = True
        for candidate_staff_id in starts_by_staff[start]:
            if await staff_repo.has_blocked_overlap(candidate_staff_id, start, end):
                all_held = False
                continue
            if await redis.get(slot_hold_key(candidate_staff_id, start)):
                continue
            if await booking_repo.has_overlap(start, end, staff_id=candidate_staff_id):
                all_held = False
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
