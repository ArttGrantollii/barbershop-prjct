from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.service import Service
from app.db.repositories.booking_repository import BookingRepository
from app.db.repositories.business_repository import BusinessRepository

HOLD_PREFIX = "slot_hold"


def slot_hold_key(service_id: UUID, start_time: datetime) -> str:
    # Normalise to UTC-aware ISO string so the key is unambiguous
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    return f"{HOLD_PREFIX}:{service_id}:{start_time.isoformat()}"


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def get_slots(
    db: AsyncSession,
    redis: Redis,
    service: Service,
    target_date: date,
) -> list[dict]:
    business_repo = BusinessRepository(db)

    if await business_repo.is_date_blocked(target_date):
        return []

    hours = await business_repo.get_hours_for_day(target_date.weekday())
    if not hours or hours.is_closed:
        return []

    duration = timedelta(minutes=service.duration_minutes)
    slot_start = datetime(target_date.year, target_date.month, target_date.day,
                          hours.open_time.hour, hours.open_time.minute, tzinfo=timezone.utc)
    day_close = datetime(target_date.year, target_date.month, target_date.day,
                         hours.close_time.hour, hours.close_time.minute, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    # Build the list of slot start times for this day
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

        is_booked = await booking_repo.has_overlap(start, end)
        slots.append({
            "start_time": start,
            "end_time": end,
            "status": "booked" if is_booked else "available",
        })

    return slots
