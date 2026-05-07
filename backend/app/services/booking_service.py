from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.websocket_manager import manager
from app.db.models.booking import Booking, BookingStatus
from app.db.repositories.booking_repository import BookingRepository
from app.db.repositories.business_repository import BusinessRepository
from app.db.repositories.service_repository import ServiceRepository
from app.db.repositories.user_repository import UserRepository
from app.notifications.schemas import BookingInfo
from app.notifications.service import notify_booking_cancelled, notify_booking_confirmed
from app.services.availability_service import slot_cooldown_key, slot_hold_key

logger = structlog.get_logger(__name__)


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _salon_date(dt: datetime) -> date:
    """Return the calendar date of `dt` as observed in the salon's local timezone."""
    return _utc(dt).astimezone(ZoneInfo(settings.SALON_TIMEZONE)).date()


def _check_min_lead(start_time: datetime) -> None:
    """Reject bookings/holds that start inside the configured lead window.
    Raised at the service layer so both hold_slot and create_booking enforce
    it identically — a stale availability grid can't slip a too-soon slot
    past the hold step."""
    lead = timedelta(minutes=settings.MIN_LEAD_MINUTES)
    if lead <= timedelta(0):
        # Even with zero lead, a booking must still be in the future.
        if start_time <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking start time must be in the future.",
            )
        return
    if start_time - datetime.now(timezone.utc) < lead:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bookings must be at least {settings.MIN_LEAD_MINUTES} minutes in advance.",
        )


def _cancel_count_key(user_id: UUID) -> str:
    """Daily cancel counter rolls over at salon midnight, not UTC midnight."""
    today = datetime.now(ZoneInfo(settings.SALON_TIMEZONE)).date().isoformat()
    return f"cancel_count:{user_id}:{today}"


async def hold_slot(
    db: AsyncSession,
    redis: Redis,
    user_id: UUID,
    service_id: UUID,
    start_time: datetime,
) -> dict:
    start_time = _utc(start_time)
    _check_min_lead(start_time)

    service = await ServiceRepository(db).get_by_id(service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    end_time = start_time + timedelta(minutes=service.duration_minutes)
    key = slot_hold_key(service_id, start_time)

    # Per-user cooldown: prevent immediately rebooking a slot the user just cancelled.
    cooldown_key = slot_cooldown_key(user_id, start_time)
    if await redis.exists(cooldown_key):
        remaining = await redis.ttl(cooldown_key)
        mins = max(1, remaining // 60)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You recently cancelled this slot. Please wait {mins} minute{'s' if mins != 1 else ''} before rebooking it.",
        )

    # Same-day single-booking rule: enforce here too so the user fails fast at
    # hold time instead of after filling out the confirm step.
    if await BookingRepository(db).count_confirmed_for_user_on_date(user_id, _salon_date(start_time)) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a booking on this day. Please cancel it before holding another slot.",
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

    # Reject bookings inside the lead window (subsumes "must be in the future").
    _check_min_lead(start_time)

    # Reject bookings on blocked dates. Compare in salon-local time so a UTC
    # booking instant on the boundary still maps to the right salon calendar day.
    salon_day = _salon_date(start_time)
    if await BusinessRepository(db).is_date_blocked(salon_day):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This date is not available for bookings.",
        )

    existing = await BookingRepository(db).count_confirmed_for_user_on_date(user_id, salon_day)
    if existing > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a booking on this day. Please cancel it before making a new one.",
        )

    cooldown_key = slot_cooldown_key(user_id, start_time)
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


async def reschedule_booking(
    db: AsyncSession,
    redis: Redis,
    booking_id: UUID,
    user_id: UUID,
    new_start_time: datetime,
    is_admin: bool = False,
) -> Booking:
    """Atomically move a confirmed booking to a new start_time. Avoids the
    cancel-then-rebook flow so the user isn't punished by the cooldown for a
    legitimate reschedule. The DB EXCLUDE constraint is the authoritative
    guard against landing on top of someone else's booking."""
    new_start_time = _utc(new_start_time)
    _check_min_lead(new_start_time)

    repo = BookingRepository(db)
    booking = await repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if not is_admin and booking.user_id != user_id:
        # Mirror the GET endpoint: hide the booking's existence from non-owners.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.status != BookingStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reschedule a {booking.status.value} booking",
        )

    if not is_admin:
        # Same notice window as cancel — rescheduling a few minutes before the
        # appointment is effectively a no-show for the staff who'd already
        # blocked the time.
        now = datetime.now(timezone.utc)
        window = timedelta(hours=settings.CANCELLATION_WINDOW_HOURS)
        if _utc(booking.start_time) - now < window:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Reschedules require at least {settings.CANCELLATION_WINDOW_HOURS}h notice",
            )

    # Need the service for duration. It must still exist and be active —
    # rescheduling onto a deactivated service would be a confusing path.
    service = await ServiceRepository(db).get_by_id(booking.service_id)
    if not service or not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service is no longer available; please book a different one.",
        )

    new_end_time = new_start_time + timedelta(minutes=service.duration_minutes)
    new_salon_day = _salon_date(new_start_time)

    # Blocked dates apply to reschedules too.
    if await BusinessRepository(db).is_date_blocked(new_salon_day):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This date is not available for bookings.",
        )

    # Same-day single-booking — but exclude THIS booking from the count, since
    # we're moving it (not adding a second one).
    other_same_day = await repo.count_confirmed_for_user_on_date(
        booking.user_id, new_salon_day, exclude_id=booking_id
    )
    if other_same_day > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have another booking on this day. Cancel it first or pick a different day.",
        )

    # Quick-fail before the UPDATE — friendlier 409 than the integrity error
    # we'd otherwise get from the EXCLUDE constraint at commit time.
    if await repo.has_overlap(new_start_time, new_end_time, exclude_id=booking_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The new time conflicts with another booking.",
        )

    # If someone is currently *holding* the new slot (other than this booking's
    # owner), respect that hold — same semantics as create_booking.
    hold_key = slot_hold_key(booking.service_id, new_start_time)
    holder = await redis.get(hold_key)
    if holder and holder != str(booking.user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That time is held by another customer.",
        )

    old_start = _utc(booking.start_time)

    booking.start_time = new_start_time
    booking.end_time = new_end_time
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The new time was just taken. Please pick another.",
        )

    # If this user was holding the new slot themselves (e.g. they reserved it
    # in a fresh BookPage flow before deciding to reschedule instead), free
    # the hold now that the booking has been confirmed onto it.
    if holder == str(booking.user_id):
        await redis.delete(hold_key)

    refreshed = await repo.get_with_details(booking_id)

    logger.info(
        "booking_rescheduled",
        booking_id=str(booking_id),
        user_id=str(booking.user_id),
        old_start=old_start.isoformat(),
        new_start=new_start_time.isoformat(),
        is_admin=is_admin,
    )

    # Free the old slot in everyone's UI and mark the new one as taken.
    await manager.broadcast(
        old_start.date().isoformat(),
        {"type": "slot_update", "start_time": old_start.isoformat(), "status": "available"},
    )
    await manager.broadcast(
        new_start_time.date().isoformat(),
        {"type": "slot_update", "start_time": new_start_time.isoformat(), "status": "booked"},
    )

    if refreshed and refreshed.user and refreshed.service:
        await notify_booking_confirmed(
            BookingInfo(
                booking_id=str(refreshed.id),
                customer_name=refreshed.user.name,
                customer_email=refreshed.user.email,
                customer_phone=refreshed.user.phone,
                service_name=refreshed.service.name,
                start_time=_utc(refreshed.start_time),
                end_time=_utc(refreshed.end_time),
                duration_minutes=refreshed.service.duration_minutes,
            )
        )

    return refreshed


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

        # Block this user from rebooking the same time slot during the cooldown
        # window — applies regardless of which service they pick.
        cooldown_key = slot_cooldown_key(cancelled_user_id, cancelled_start)
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
