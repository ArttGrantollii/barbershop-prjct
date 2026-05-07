from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.websocket_manager import manager
from app.db.models.booking import Booking, BookingStatus
from app.db.repositories.booking_repository import BookingRepository
from app.db.repositories.service_repository import ServiceRepository
from app.db.repositories.user_repository import UserRepository
from app.notifications.schemas import BookingInfo
from app.notifications.service import notify_booking_cancelled, notify_booking_confirmed
from app.services.availability_service import slot_cooldown_key, slot_hold_key

logger = structlog.get_logger(__name__)


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _cancel_count_key(user_id: UUID) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    return f"cancel_count:{user_id}:{today}"


async def hold_slot(
    db: AsyncSession,
    redis: Redis,
    user_id: UUID,
    service_id: UUID,
    start_time: datetime,
) -> dict:
    start_time = _utc(start_time)

    service = await ServiceRepository(db).get_by_id(service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    end_time = start_time + timedelta(minutes=service.duration_minutes)
    key = slot_hold_key(service_id, start_time)

    # Per-user cooldown: prevent immediately rebooking a slot the user just cancelled.
    cooldown_key = slot_cooldown_key(user_id, service_id, start_time)
    if await redis.exists(cooldown_key):
        remaining = await redis.ttl(cooldown_key)
        mins = max(1, remaining // 60)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You recently cancelled this slot. Please wait {mins} minute{'s' if mins != 1 else ''} before rebooking it.",
        )

    # Check DB first so we give a clear error if the slot is already confirmed.
    if await BookingRepository(db).has_overlap(start_time, end_time):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is already booked")

    # Atomic SET NX — only succeeds if the key doesn't exist yet, eliminating the
    # check-then-set race condition in the original code.
    acquired = await redis.set(key, str(user_id), nx=True, ex=settings.SLOT_HOLD_TTL_SECONDS)
    if not acquired:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is already held")

    logger.info("slot_held", user_id=str(user_id), service_id=str(service_id), start=start_time.isoformat())

    room = start_time.date().isoformat()
    await manager.broadcast(room, {
        "type": "slot_update",
        "start_time": start_time.isoformat(),
        "status": "held",
    })

    return {
        "start_time": start_time,
        "end_time": end_time,
        "expires_in_seconds": settings.SLOT_HOLD_TTL_SECONDS,
    }


async def release_hold(
    redis: Redis,
    user_id: UUID,
    service_id: UUID,
    start_time: datetime,
) -> None:
    start_time = _utc(start_time)
    key = slot_hold_key(service_id, start_time)
    holder = await redis.get(key)
    if holder == str(user_id):
        await redis.delete(key)
        room = start_time.date().isoformat()
        await manager.broadcast(room, {
            "type": "slot_update",
            "start_time": start_time.isoformat(),
            "status": "available",
        })


async def create_booking(
    db: AsyncSession,
    redis: Redis,
    user_id: UUID,
    service_id: UUID,
    start_time: datetime,
    notes: str | None = None,
) -> Booking:
    start_time = _utc(start_time)

    existing = await BookingRepository(db).count_confirmed_for_user_on_date(user_id, start_time.date())
    if existing > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a booking on this day. Please cancel it before making a new one.",
        )

    cooldown_key = slot_cooldown_key(user_id, service_id, start_time)
    if await redis.exists(cooldown_key):
        remaining = await redis.ttl(cooldown_key)
        mins = max(1, remaining // 60)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You recently cancelled this slot. Please wait {mins} minute{'s' if mins != 1 else ''} before rebooking it.",
        )

    cancel_key = _cancel_count_key(user_id)
    cancel_count = await redis.get(cancel_key)
    if cancel_count and int(cancel_count) >= settings.CANCELLATION_LIMIT_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You have reached today's booking limit. Try again tomorrow.",
        )

    service = await ServiceRepository(db).get_by_id(service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    end_time = start_time + timedelta(minutes=service.duration_minutes)
    key = slot_hold_key(service_id, start_time)
    holder = await redis.get(key)

    if holder and holder != str(user_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is held by another user")

    # Fast-fail before the insert — the DB exclusion constraint is the authoritative
    # guard, but this gives a clearer error message in the common case.
    if await BookingRepository(db).has_overlap(start_time, end_time):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is no longer available")

    repo = BookingRepository(db)
    try:
        raw = await repo.create_booking(
            user_id=user_id,
            service_id=service_id,
            start_time=start_time,
            end_time=end_time,
            notes=notes,
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is no longer available")

    # Re-fetch with eagerly loaded relationships so FastAPI can serialize the response
    # without hitting the MissingGreenlet error from lazy-loading inside the ASGI stack.
    booking = await repo.get_with_details(raw.id)

    await redis.delete(key)

    logger.info(
        "booking_created",
        booking_id=str(booking.id),
        user_id=str(user_id),
        service_id=str(service_id),
        start=start_time.isoformat(),
    )

    room = start_time.date().isoformat()
    await manager.broadcast(room, {
        "type": "slot_update",
        "start_time": start_time.isoformat(),
        "status": "booked",
    })

    user = await UserRepository(db).get_by_id(user_id)
    if user:
        await notify_booking_confirmed(
            BookingInfo(
                booking_id=str(booking.id),
                customer_name=user.name,
                customer_email=user.email,
                customer_phone=user.phone,
                service_name=service.name,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=service.duration_minutes,
            )
        )

    return booking


async def cancel_booking(
    db: AsyncSession,
    redis: Redis,
    booking_id: UUID,
    user_id: UUID,
    reason: str | None = None,
    is_admin: bool = False,
) -> Booking:
    repo = BookingRepository(db)
    booking = await repo.get_by_id(booking_id)

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if not is_admin and booking.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")

    if booking.status != BookingStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking is already {booking.status.value}",
        )

    if not is_admin:
        now = datetime.now(timezone.utc)
        window = timedelta(hours=settings.CANCELLATION_WINDOW_HOURS)
        if _utc(booking.start_time) - now < window:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cancellations require at least {settings.CANCELLATION_WINDOW_HOURS}h notice",
            )

        cancel_key = _cancel_count_key(booking.user_id)
        current_count = await redis.get(cancel_key)
        if current_count and int(current_count) >= settings.CANCELLATION_LIMIT_PER_DAY:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Daily cancellation limit of {settings.CANCELLATION_LIMIT_PER_DAY} reached. Try again tomorrow.",
            )

    # Save scalar FKs before commit — the session expires all attributes on commit,
    # and accessing them afterwards would trigger a lazy load (MissingGreenlet).
    cancelled_user_id = booking.user_id
    cancelled_service_id = booking.service_id
    cancelled_start = _utc(booking.start_time)

    booking.status = BookingStatus.CANCELLED
    booking.cancellation_reason = reason
    await db.commit()

    if not is_admin:
        # Increment the daily counter. INCR creates the key at 0 then returns 1 on
        # first call, so we only set the TTL on that first write to avoid resetting it.
        cancel_key = _cancel_count_key(cancelled_user_id)
        count = await redis.incr(cancel_key)
        if count == 1:
            await redis.expire(cancel_key, 86_400)

        # Block this user from rebooking the same slot during the cooldown window.
        cooldown_key = slot_cooldown_key(cancelled_user_id, cancelled_service_id, cancelled_start)
        await redis.set(cooldown_key, 1, ex=settings.SLOT_COOLDOWN_SECONDS)

    # Re-fetch with eager relationships for response serialization and notifications.
    booking = await repo.get_with_details(booking_id)

    logger.info(
        "booking_cancelled",
        booking_id=str(booking_id),
        user_id=str(user_id),
        is_admin=is_admin,
    )

    room = _utc(booking.start_time).date().isoformat()
    await manager.broadcast(room, {
        "type": "slot_update",
        "start_time": _utc(booking.start_time).isoformat(),
        "status": "available",
    })

    if booking.user and booking.service:
        await notify_booking_cancelled(
            BookingInfo(
                booking_id=str(booking.id),
                customer_name=booking.user.name,
                customer_email=booking.user.email,
                customer_phone=booking.user.phone,
                service_name=booking.service.name,
                start_time=_utc(booking.start_time),
                end_time=_utc(booking.end_time),
                duration_minutes=booking.service.duration_minutes,
                cancellation_reason=reason,
            )
        )

    return booking
