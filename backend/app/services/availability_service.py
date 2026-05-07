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

logger = structlog.get_logger(__name__)

HOLD_PREFIX = "slot_hold"
COOLDOWN_PREFIX = "slot_cooldown"


def slot_hold_key(service_id: UUID, start_time: datetime) -> str:
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    return f"{HOLD_PREFIX}:{service_id}:{start_time.isoformat()}"


def slot_cooldown_key(user_id: UUID, service_id: UUID, start_time: datetime) -> str:
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    return f"{COOLDOWN_PREFIX}:{user_id}:{service_id}:{start_time.isoformat()}"


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def get_slots(
    db: AsyncSession,
    redis: Redis,
    service: Service,
    target_date: date,
    user_id: UUID | None = None,
) -> list[dict]:
    business_repo = BusinessRepository(db)

    if await business_repo.is_date_blocked(target_date):
        logger.debug("slots_skipped_blocked_date", date=target_date.isoformat())
        return []

    hours = await business_repo.get_hours_for_day(target_date.weekday())
    if not hours or hours.is_closed:
        logger.debug("slots_skipped_closed_day", date=target_date.isoformat())
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

    starts: list[datetime] = []
    current = slot_start
    while current + duration <= day_close:
        starts.append(current)
        current += duration

    booking_repo = BookingRepository(db)

    slots: list[dict] = []
    for start in starts:
        end = start + duration

        if start <= now:
            continue

        key = slot_hold_key(service.id, start)
        if await redis.get(key):
            slots.append({"start_time": start, "end_time": end, "status": "held"})
            continue

        if await booking_repo.has_overlap(start, end):
            slots.append({"start_time": start, "end_time": end, "status": "booked"})
            continue

        if user_id and await redis.exists(slot_cooldown_key(user_id, service.id, start)):
            slots.append({"start_time": start, "end_time": end, "status": "cooldown"})
            continue

        slots.append({"start_time": start, "end_time": end, "status": "available"})

    logger.debug(
        "slots_calculated",
        date=target_date.isoformat(),
        service_id=str(service.id),
        salon_tz=settings.SALON_TIMEZONE,
        total=len(slots),
    )
    return slots
