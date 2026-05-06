from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.websocket_manager import manager
from app.db.models.booking import Booking, BookingStatus
from app.db.repositories.booking_repository import BookingRepository
from app.db.repositories.service_repository import ServiceRepository
from app.db.repositories.user_repository import UserRepository
from app.notifications.schemas import BookingInfo
from app.notifications.service import notify_booking_cancelled, notify_booking_confirmed
from app.services.availability_service import slot_hold_key


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


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

    if await redis.get(key):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is already held")

    if await BookingRepository(db).has_overlap(start_time, end_time):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is already booked")

    await redis.setex(key, settings.SLOT_HOLD_TTL_SECONDS, str(user_id))

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

    service = await ServiceRepository(db).get_by_id(service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    end_time = start_time + timedelta(minutes=service.duration_minutes)
    key = slot_hold_key(service_id, start_time)
    holder = await redis.get(key)

    if holder and holder != str(user_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is held by another user")

    if await BookingRepository(db).has_overlap(start_time, end_time):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is no longer available")

    booking = await BookingRepository(db).create_booking(
        user_id=user_id,
        service_id=service_id,
        start_time=start_time,
        end_time=end_time,
        notes=notes,
    )

    await redis.delete(key)

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
        time_until = _utc(booking.start_time) - now
        if time_until < window:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cancellations require at least {settings.CANCELLATION_WINDOW_HOURS}h notice",
            )

    booking.status = BookingStatus.CANCELLED
    booking.cancellation_reason = reason
    await db.commit()
    await db.refresh(booking)

    room = _utc(booking.start_time).date().isoformat()
    await manager.broadcast(room, {
        "type": "slot_update",
        "start_time": _utc(booking.start_time).isoformat(),
        "status": "available",
    })

    user = await UserRepository(db).get_by_id(booking.user_id)
    service = await ServiceRepository(db).get_by_id(booking.service_id)
    if user and service:
        await notify_booking_cancelled(
            BookingInfo(
                booking_id=str(booking.id),
                customer_name=user.name,
                customer_email=user.email,
                customer_phone=user.phone,
                service_name=service.name,
                start_time=_utc(booking.start_time),
                end_time=_utc(booking.end_time),
                duration_minutes=service.duration_minutes,
                cancellation_reason=reason,
            )
        )

    return booking
