from datetime import date, datetime, time as time_t, timedelta, timezone
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
from app.db.repositories.staff_repository import StaffRepository
from app.db.repositories.user_repository import UserRepository
from app.notifications.schemas import BookingInfo
from app.notifications.service import notify_booking_cancelled, notify_booking_confirmed
from app.services.availability_service import slot_cooldown_key, slot_hold_key

logger = structlog.get_logger(__name__)

USER_HOLD_PREFIX = "user_active_hold"


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _salon_date(dt: datetime) -> date:
    """Return the calendar date of `dt` as observed in the salon's local timezone."""
    return _utc(dt).astimezone(ZoneInfo(settings.SALON_TIMEZONE)).date()


def _wall_time(target_date: date, value: time_t) -> datetime:
    salon_tz = ZoneInfo(settings.SALON_TIMEZONE)
    return datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        value.hour,
        value.minute,
        tzinfo=salon_tz,
    )


async def _staff_is_working(
    staff_repo: StaffRepository,
    business_repo: BusinessRepository,
    staff_id: UUID,
    start_time: datetime,
    end_time: datetime,
) -> bool:
    salon_day = _salon_date(start_time)
    if await business_repo.is_date_blocked(salon_day):
        return False

    staff_hours = await staff_repo.get_hours_for_day(staff_id, salon_day.weekday())
    global_hours = await business_repo.get_hours_for_day(salon_day.weekday()) if staff_hours is None else None
    effective_hours = staff_hours or global_hours
    if not effective_hours or effective_hours.is_closed:
        return False

    open_at = _wall_time(salon_day, effective_hours.open_time)
    close_at = _wall_time(salon_day, effective_hours.close_time)
    if start_time < open_at or end_time > close_at:
        return False

    if await staff_repo.has_blocked_overlap(staff_id, start_time, end_time):
        return False
    return True


async def _resolve_staff_id(
    db: AsyncSession,
    redis: Redis,
    booking_repo: BookingRepository,
    service_id: UUID,
    start_time: datetime,
    end_time: datetime,
    preferred_staff_id: UUID | None = None,
) -> UUID:
    """Pick the staff member to assign to this hold/booking.

    With `preferred_staff_id` set: validate that staff offers the service and
    is free at the requested time, return them. Without: walk the active
    staff who offer the service in display order and return the first free
    one. Raises 4xx HTTPException when no staff fits.

    Honoring caller preference rather than blindly auto-picking matters once
    the customer-facing "pick your stylist" UI ships — the same code path
    serves both modes.
    """
    staff_repo = StaffRepository(db)
    business_repo = BusinessRepository(db)

    if preferred_staff_id is not None:
        if not await staff_repo.staff_offers_service(preferred_staff_id, service_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That stylist does not offer this service.",
            )
        if not await _staff_is_working(staff_repo, business_repo, preferred_staff_id, start_time, end_time):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That stylist is not working at this time.",
            )
        if await redis.get(slot_hold_key(preferred_staff_id, start_time)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That stylist is currently held at this time.",
            )
        if await booking_repo.has_overlap(start_time, end_time, staff_id=preferred_staff_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That stylist is already booked at this time.",
            )
        return preferred_staff_id

    eligible = await staff_repo.get_active_for_service(service_id)
    if not eligible:
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
            detail="No stylists are configured for this service.",
        )
    for staff in eligible:
        if not await _staff_is_working(staff_repo, business_repo, staff.id, start_time, end_time):
            continue
        if await redis.get(slot_hold_key(staff.id, start_time)):
            continue
        if await booking_repo.has_overlap(start_time, end_time, staff_id=staff.id):
            continue
        return staff.id
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="No stylist is available at this time.",
    )


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


def _user_hold_key(user_id: UUID) -> str:
    return f"{USER_HOLD_PREFIX}:{user_id}"


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


async def hold_slot(
    db: AsyncSession,
    redis: Redis,
    user_id: UUID,
    service_id: UUID,
    start_time: datetime,
    staff_id: UUID | None = None,
) -> dict:
    start_time = _utc(start_time)
    _check_min_lead(start_time)

    service = await ServiceRepository(db).get_by_id(service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    end_time = start_time + timedelta(minutes=service.duration_minutes)

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
    booking_repo = BookingRepository(db)
    if await booking_repo.count_confirmed_for_user_on_date(user_id, _salon_date(start_time)) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a booking on this day. Please cancel it before holding another slot.",
        )

    user_hold_key = _user_hold_key(user_id)
    active_hold = await redis.set(
        user_hold_key,
        "pending",
        nx=True,
        ex=settings.SLOT_HOLD_TTL_SECONDS,
    )
    if not active_hold:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a slot on hold. Release it or wait for it to expire before holding another.",
        )

    # Resolve the stylist. Concurrent callers can pick the same one between
    # the resolver's check and our SET NX — re-resolve on failure so the
    # second caller still gets a stylist if any others are free.
    last_exc: HTTPException | None = None
    try:
        for _ in range(3):
            resolved_staff_id = await _resolve_staff_id(
                db, redis, booking_repo, service_id, start_time, end_time, preferred_staff_id=staff_id,
            )
            key = slot_hold_key(resolved_staff_id, start_time)
            acquired = await redis.set(key, str(user_id), nx=True, ex=settings.SLOT_HOLD_TTL_SECONDS)
            if acquired:
                await redis.set(user_hold_key, key, ex=settings.SLOT_HOLD_TTL_SECONDS)
                break
            last_exc = HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Slot is already held",
            )
            if staff_id is not None:
                # Caller asked for a specific stylist; don't substitute.
                raise last_exc
        else:
            raise last_exc or HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not reserve a stylist. Please try again.",
            )
    except Exception:
        await redis.delete(user_hold_key)
        raise

    logger.info(
        "slot_held",
        user_id=str(user_id),
        service_id=str(service_id),
        staff_id=str(resolved_staff_id),
        start=start_time.isoformat(),
    )

    room = start_time.date().isoformat()
    await manager.broadcast(room, {
        "type": "slot_update",
        "start_time": start_time.isoformat(),
        "staff_id": str(resolved_staff_id),
        "status": "held",
    })

    return {
        "start_time": start_time,
        "end_time": end_time,
        "staff_id": resolved_staff_id,
        "expires_in_seconds": settings.SLOT_HOLD_TTL_SECONDS,
    }


async def release_hold(
    db: AsyncSession,
    redis: Redis,
    user_id: UUID,
    service_id: UUID,
    start_time: datetime,
    staff_id: UUID | None = None,
) -> None:
    """Release the user's hold for this service+time.

    Hold keys are per-staff. When the caller knows which stylist the hold
    was placed against (the hold response includes `staff_id`), this is a
    single key lookup. When they don't — i.e. the legacy frontend that
    didn't track the resolved staff — we walk the eligible staff and
    release whichever key is owned by this user. Either way the operation
    is idempotent: callers always get 204 on success."""
    start_time = _utc(start_time)

    if staff_id is not None:
        candidate_ids = [staff_id]
    else:
        staff_repo = StaffRepository(db)
        eligible = await staff_repo.get_active_for_service(service_id)
        candidate_ids = [s.id for s in eligible]

    for sid in candidate_ids:
        key = slot_hold_key(sid, start_time)
        holder = await redis.get(key)
        if holder == str(user_id):
            await redis.delete(key)
            await redis.delete(_user_hold_key(user_id))
            room = start_time.date().isoformat()
            await manager.broadcast(room, {
                "type": "slot_update",
                "start_time": start_time.isoformat(),
                "staff_id": str(sid),
                "status": "available",
            })
            return  # one hold per (user, service, time); first match wins


async def create_booking(
    db: AsyncSession,
    redis: Redis,
    user_id: UUID,
    service_id: UUID,
    start_time: datetime,
    notes: str | None = None,
    staff_id: UUID | None = None,
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

    booking_repo = BookingRepository(db)
    existing = await booking_repo.count_confirmed_for_user_on_date(user_id, salon_day)
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

    # Pick the stylist. If the caller pre-held a slot, that hold's key tells us
    # which staff was assigned — we look for a hold owned by this user across
    # the eligible staff and prefer that one. Otherwise (no prior hold or the
    # caller wants to override) the resolver auto-picks.
    resolved_staff_id: UUID | None = staff_id
    if resolved_staff_id is None:
        staff_repo = StaffRepository(db)
        eligible = await staff_repo.get_active_for_service(service_id)
        for staff in eligible:
            holder = await redis.get(slot_hold_key(staff.id, start_time))
            if holder == str(user_id):
                resolved_staff_id = staff.id
                break

    if resolved_staff_id is None:
        # No pre-held slot — let the resolver pick a free stylist.
        resolved_staff_id = await _resolve_staff_id(
            db, redis, booking_repo, service_id, start_time, end_time,
            preferred_staff_id=None,
        )
    else:
        # Caller-specified or hold-derived staff_id: still validate the
        # combination (offers service, not booked under us). We don't check
        # "held" here because the user's own hold is fine to consume.
        staff_repo = StaffRepository(db)
        if not await staff_repo.staff_offers_service(resolved_staff_id, service_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That stylist does not offer this service.",
            )
        if not await _staff_is_working(staff_repo, BusinessRepository(db), resolved_staff_id, start_time, end_time):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That stylist is not working at this time.",
            )
        held_by = await redis.get(slot_hold_key(resolved_staff_id, start_time))
        if held_by and held_by != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That stylist is currently held by another customer.",
            )
        if await booking_repo.has_overlap(start_time, end_time, staff_id=resolved_staff_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That stylist is no longer available at this time.",
            )

    user = await UserRepository(db).get_by_id(user_id)
    try:
        raw = await booking_repo.create_booking(
            user_id=user_id,
            service_id=service_id,
            staff_id=resolved_staff_id,
            start_time=start_time,
            end_time=end_time,
            notes=notes,
            customer_name=user.name if user else None,
            customer_email=user.email if user else None,
            customer_phone=user.phone if user else None,
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is no longer available")

    # Re-fetch with eagerly loaded relationships so FastAPI can serialize the response
    # without hitting the MissingGreenlet error from lazy-loading inside the ASGI stack.
    booking = await booking_repo.get_with_details(raw.id)

    # Consume our hold (if any). Whichever staff we landed on, that's the
    # hold key to free.
    await redis.delete(slot_hold_key(resolved_staff_id, start_time))
    await redis.delete(_user_hold_key(user_id))

    logger.info(
        "booking_created",
        booking_id=str(booking.id),
        user_id=str(user_id),
        service_id=str(service_id),
        staff_id=str(resolved_staff_id),
        start=start_time.isoformat(),
    )

    room = start_time.date().isoformat()
    await manager.broadcast(room, {
        "type": "slot_update",
        "start_time": start_time.isoformat(),
        "staff_id": str(resolved_staff_id),
        "status": "booked",
    })

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


async def create_admin_booking(
    db: AsyncSession,
    redis: Redis,
    admin_id: UUID,
    service_id: UUID,
    staff_id: UUID,
    start_time: datetime,
    booking_status: BookingStatus = BookingStatus.CONFIRMED,
    user_id: UUID | None = None,
    customer_name: str | None = None,
    customer_email: str | None = None,
    customer_phone: str | None = None,
    notes: str | None = None,
) -> Booking:
    start_time = _utc(start_time)
    if booking_status not in {BookingStatus.CONFIRMED, BookingStatus.COMPLETED}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin-created bookings can only be confirmed or completed.",
        )

    service = await ServiceRepository(db).get_by_id(service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    user = None
    if user_id is not None:
        user = await UserRepository(db).get_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    customer_name = _clean(customer_name) or (user.name if user else None)
    customer_email = _clean(customer_email) or (user.email if user else None)
    customer_phone = _clean(customer_phone) or (user.phone if user else None)
    if not customer_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer name is required for guest or walk-in bookings.",
        )

    end_time = start_time + timedelta(minutes=service.duration_minutes)
    booking_repo = BookingRepository(db)
    staff_repo = StaffRepository(db)
    business_repo = BusinessRepository(db)

    if not await staff_repo.staff_offers_service(staff_id, service_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That stylist does not offer this service.",
        )

    if booking_status == BookingStatus.CONFIRMED:
        if start_time <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Confirmed bookings must start in the future.",
            )
        salon_day = _salon_date(start_time)
        if await business_repo.is_date_blocked(salon_day):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This date is not available for bookings.",
            )
        if not await _staff_is_working(staff_repo, business_repo, staff_id, start_time, end_time):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That stylist is not working at this time.",
            )
        holder = await redis.get(slot_hold_key(staff_id, start_time))
        if holder:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That time is currently held by a customer.",
            )
        if await booking_repo.has_overlap(start_time, end_time, staff_id=staff_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That stylist is already booked at this time.",
            )
    elif start_time > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed walk-ins cannot be scheduled in the future.",
        )

    try:
        raw = await booking_repo.create_booking(
            user_id=user_id,
            service_id=service_id,
            staff_id=staff_id,
            start_time=start_time,
            end_time=end_time,
            notes=notes,
            status=booking_status,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot is no longer available")

    booking = await booking_repo.get_with_details(raw.id)
    logger.info(
        "admin_booking_created",
        booking_id=str(booking.id),
        admin_id=str(admin_id),
        user_id=str(user_id) if user_id else None,
        service_id=str(service_id),
        staff_id=str(staff_id),
        status=booking_status.value,
        start=start_time.isoformat(),
    )

    if booking_status == BookingStatus.CONFIRMED:
        await manager.broadcast(
            start_time.date().isoformat(),
            {
                "type": "slot_update",
                "start_time": start_time.isoformat(),
                "staff_id": str(staff_id),
                "status": "booked",
            },
        )
        if customer_email:
            await notify_booking_confirmed(
                BookingInfo(
                    booking_id=str(booking.id),
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
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
    new_staff_id: UUID | None = None,
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
    if booking.user_id is not None:
        other_same_day = await repo.count_confirmed_for_user_on_date(
            booking.user_id, new_salon_day, exclude_id=booking_id
        )
        if other_same_day > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have another booking on this day. Cancel it first or pick a different day.",
            )

    # Default to keeping the same stylist. Callers may override (e.g. an
    # admin moving a booking onto a different chair) by passing new_staff_id.
    target_staff_id = new_staff_id or booking.staff_id
    staff_repo = StaffRepository(db)
    if new_staff_id is not None:
        if not await staff_repo.staff_offers_service(new_staff_id, booking.service_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That stylist does not offer this service.",
            )
    if not await _staff_is_working(staff_repo, BusinessRepository(db), target_staff_id, new_start_time, new_end_time):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That stylist is not working at this time.",
        )

    # Quick-fail before the UPDATE — friendlier 409 than the integrity error
    # we'd otherwise get from the EXCLUDE constraint at commit time. Scope
    # the overlap check to the target stylist so two stylists can be busy at
    # the same time without colliding.
    if await repo.has_overlap(
        new_start_time, new_end_time, staff_id=target_staff_id, exclude_id=booking_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The new time conflicts with another booking.",
        )

    # If someone is currently *holding* the new slot for the target stylist
    # (other than this booking's owner), respect that hold.
    hold_key = slot_hold_key(target_staff_id, new_start_time)
    holder = await redis.get(hold_key)
    if holder and (booking.user_id is None or holder != str(booking.user_id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That time is held by another customer.",
        )

    old_start = _utc(booking.start_time)

    booking.start_time = new_start_time
    booking.end_time = new_end_time
    if target_staff_id != booking.staff_id:
        booking.staff_id = target_staff_id
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
    if booking.user_id is not None and holder == str(booking.user_id):
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

    customer_name = refreshed.user.name if refreshed and refreshed.user else refreshed.customer_name if refreshed else None
    customer_email = refreshed.user.email if refreshed and refreshed.user else refreshed.customer_email if refreshed else None
    customer_phone = refreshed.user.phone if refreshed and refreshed.user else refreshed.customer_phone if refreshed else None
    if refreshed and refreshed.service and customer_name and customer_email:
        await notify_booking_confirmed(
            BookingInfo(
                booking_id=str(refreshed.id),
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
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

    customer_name = booking.user.name if booking.user else booking.customer_name
    customer_email = booking.user.email if booking.user else booking.customer_email
    customer_phone = booking.user.phone if booking.user else booking.customer_phone
    if booking.service and customer_name and customer_email:
        await notify_booking_cancelled(
            BookingInfo(
                booking_id=str(booking.id),
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                service_name=booking.service.name,
                start_time=_utc(booking.start_time),
                end_time=_utc(booking.end_time),
                duration_minutes=booking.service.duration_minutes,
                cancellation_reason=reason,
            )
        )

    return booking
