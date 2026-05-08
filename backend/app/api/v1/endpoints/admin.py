import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_admin
from app.db.models.booking import BookingStatus
from app.db.models.user import User
from app.db.redis import get_redis
from app.db.repositories.booking_repository import BookingRepository
from app.db.repositories.business_repository import BusinessRepository
from app.db.repositories.service_repository import ServiceRepository
from app.db.repositories.staff_repository import StaffRepository
from app.db.session import get_db
from app.schemas.booking import (
    AdminDashboardResponse,
    BookingCancelRequest,
    BookingDetailResponse,
    BookingPage,
    BookingRescheduleRequest,
)
from app.schemas.business import (
    BlockedDateCreate,
    BlockedDateResponse,
    BusinessHoursResponse,
    BusinessHoursUpdate,
)
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate
from app.schemas.staff import (
    StaffBlockedTimeCreate,
    StaffBlockedTimeResponse,
    StaffCreate,
    StaffResponse,
    StaffServicesUpdate,
    StaffUpdate,
    StaffWorkingHoursResponse,
    StaffWorkingHoursUpdate,
    StaffWithServicesResponse,
)
from app.services.booking_service import cancel_booking, reschedule_booking

router = APIRouter(prefix="/admin", tags=["admin"])


def _salon_day_bounds(target_date: date) -> tuple[datetime, datetime]:
    tz = ZoneInfo(settings.SALON_TIMEZONE)
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=tz)
    return day_start, day_start + timedelta(days=1)


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> AdminDashboardResponse:
    """Aggregate dashboard metrics in the backend so the admin UI never
    derives business totals from a capped bookings page."""
    repo = BookingRepository(db)
    now = datetime.now(timezone.utc)
    salon_today = now.astimezone(ZoneInfo(settings.SALON_TIMEZONE)).date()
    today_start, today_end = _salon_day_bounds(salon_today)
    week_end = now + timedelta(days=7)

    today_schedule = await repo.get_between_with_details(
        today_start,
        today_end,
        status=BookingStatus.CONFIRMED,
    )
    today_revenue = await repo.revenue_between(
        today_start,
        today_end,
        status=BookingStatus.CONFIRMED,
    )
    week_bookings_count = await repo.count_between(
        now,
        week_end,
        status=BookingStatus.CONFIRMED,
    )
    confirmed_total = await repo.count_all(status=BookingStatus.CONFIRMED)
    cancelled_total = await repo.count_all(status=BookingStatus.CANCELLED)

    return AdminDashboardResponse(
        today_bookings_count=len(today_schedule),
        today_revenue=today_revenue,
        week_bookings_count=week_bookings_count,
        confirmed_total=confirmed_total,
        cancelled_total=cancelled_total,
        today_schedule=today_schedule,
    )

# ── Services ──────────────────────────────────────────────────────────────────


@router.get("/services", response_model=list[ServiceResponse])
async def list_services(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin)):
    return await ServiceRepository(db).get_all()


@router.post("/services", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    body: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await ServiceRepository(db).create(
        name=body.name,
        description=body.description,
        duration_minutes=body.duration_minutes,
        price=body.price,
    )


@router.put("/services/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: uuid.UUID,
    body: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    repo = ServiceRepository(db)
    service = await repo.get_by_id(service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return await repo.update(service, **body.model_dump(exclude_none=True))


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    # Refuse hard delete when bookings reference the service — the FK would
    # eventually catch this with a 500, but a clear 409 is friendlier and lets
    # the admin make a deliberate choice (deactivate vs. delete history too).
    booking_count = await BookingRepository(db).count_for_service(service_id)
    if booking_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete this service: it has {booking_count} booking"
                f"{'s' if booking_count != 1 else ''} referencing it. "
                "Deactivate it instead to hide it from new bookings while preserving history."
            ),
        )
    if not await ServiceRepository(db).delete(service_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")


# ── Business Hours ────────────────────────────────────────────────────────────


@router.get("/business-hours", response_model=list[BusinessHoursResponse])
async def get_business_hours(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin)):
    return await BusinessRepository(db).get_all_hours()


@router.put("/business-hours/{day_of_week}", response_model=BusinessHoursResponse)
async def update_business_hours(
    day_of_week: int,
    body: BusinessHoursUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    if not 0 <= day_of_week <= 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="day_of_week must be 0–6")
    repo = BusinessRepository(db)
    current = await repo.get_hours_for_day(day_of_week)
    if not current:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hours configured for this day")
    patch = body.model_dump(exclude_none=True)
    return await repo.upsert_hours(
        day_of_week=day_of_week,
        open_time=patch.get("open_time", current.open_time),
        close_time=patch.get("close_time", current.close_time),
        is_closed=patch.get("is_closed", current.is_closed),
    )


# ── Blocked Dates ─────────────────────────────────────────────────────────────


@router.get("/blocked-dates", response_model=list[BlockedDateResponse])
async def get_blocked_dates(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin)):
    return await BusinessRepository(db).get_blocked_dates()


@router.post("/blocked-dates", response_model=BlockedDateResponse, status_code=status.HTTP_201_CREATED)
async def add_blocked_date(
    body: BlockedDateCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await BusinessRepository(db).create_blocked_date(body.date, body.reason)


@router.delete("/blocked-dates/{blocked_date_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_blocked_date(
    blocked_date_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    if not await BusinessRepository(db).delete_blocked_date(blocked_date_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blocked date not found")


# ── Staff ─────────────────────────────────────────────────────────────────────


def _staff_payload(staff) -> StaffWithServicesResponse:
    """Flatten the relationship into the wire shape — `service_ids` instead
    of nested `services` so the admin UI can drive checkbox state directly."""
    return StaffWithServicesResponse(
        id=staff.id,
        name=staff.name,
        phone=staff.phone,
        photo_url=staff.photo_url,
        is_active=staff.is_active,
        display_order=staff.display_order,
        service_ids=[s.id for s in (staff.services or [])],
    )


@router.get("/staff", response_model=list[StaffWithServicesResponse])
async def list_staff(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin)):
    rows = await StaffRepository(db).get_all_with_services()
    return [_staff_payload(s) for s in rows]


@router.post("/staff", response_model=StaffWithServicesResponse, status_code=status.HTTP_201_CREATED)
async def create_staff(
    body: StaffCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    repo = StaffRepository(db)
    staff = await repo.create(
        name=body.name,
        phone=body.phone,
        photo_url=body.photo_url,
        display_order=body.display_order,
    )
    if body.service_ids:
        staff = await repo.set_services(staff, body.service_ids)
    else:
        # Re-fetch with the (empty) services collection populated so the
        # response payload is consistent shape-wise with the assignment case.
        staff = await repo.get_with_services(staff.id)
    return _staff_payload(staff)


@router.patch("/staff/{staff_id}", response_model=StaffWithServicesResponse)
async def update_staff(
    staff_id: uuid.UUID,
    body: StaffUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    repo = StaffRepository(db)
    staff = await repo.get_with_services(staff_id)
    if not staff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")
    patch = body.model_dump(exclude_unset=True)
    if patch:
        staff = await repo.update(staff, **patch)
    return _staff_payload(staff)


@router.put("/staff/{staff_id}/services", response_model=StaffWithServicesResponse)
async def set_staff_services(
    staff_id: uuid.UUID,
    body: StaffServicesUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    repo = StaffRepository(db)
    staff = await repo.get_with_services(staff_id)
    if not staff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")
    staff = await repo.set_services(staff, body.service_ids)
    return _staff_payload(staff)


@router.get("/staff/{staff_id}/working-hours", response_model=list[StaffWorkingHoursResponse])
async def get_staff_working_hours(
    staff_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    repo = StaffRepository(db)
    if not await repo.get_by_id(staff_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")
    return await repo.get_all_hours(staff_id)


@router.put("/staff/{staff_id}/working-hours/{day_of_week}", response_model=StaffWorkingHoursResponse)
async def update_staff_working_hours(
    staff_id: uuid.UUID,
    day_of_week: int,
    body: StaffWorkingHoursUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    if not 0 <= day_of_week <= 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="day_of_week must be 0-6")
    repo = StaffRepository(db)
    if not await repo.get_by_id(staff_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")
    current = await repo.get_hours_for_day(staff_id, day_of_week)
    patch = body.model_dump(exclude_none=True)
    open_time = patch.get("open_time") or (current.open_time if current else datetime.strptime("09:00", "%H:%M").time())
    close_time = patch.get("close_time") or (current.close_time if current else datetime.strptime("17:00", "%H:%M").time())
    if not patch.get("is_closed", current.is_closed if current else False) and close_time <= open_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="close_time must be after open_time")
    return await repo.upsert_hours(
        staff_id=staff_id,
        day_of_week=day_of_week,
        open_time=open_time,
        close_time=close_time,
        is_closed=patch.get("is_closed", current.is_closed if current else False),
    )


@router.get("/staff/{staff_id}/blocked-times", response_model=list[StaffBlockedTimeResponse])
async def get_staff_blocked_times(
    staff_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    repo = StaffRepository(db)
    if not await repo.get_by_id(staff_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")
    return await repo.get_blocked_times(staff_id)


@router.post("/staff/{staff_id}/blocked-times", response_model=StaffBlockedTimeResponse, status_code=status.HTTP_201_CREATED)
async def create_staff_blocked_time(
    staff_id: uuid.UUID,
    body: StaffBlockedTimeCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    repo = StaffRepository(db)
    if not await repo.get_by_id(staff_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")
    return await repo.create_blocked_time(staff_id, body.start_time, body.end_time, body.reason)


@router.delete("/staff/{staff_id}/blocked-times/{blocked_time_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff_blocked_time(
    staff_id: uuid.UUID,
    blocked_time_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    if not await StaffRepository(db).delete_blocked_time(staff_id, blocked_time_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blocked time not found")


@router.delete("/staff/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff(
    staff_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Same pattern as service delete: refuse a hard delete when bookings
    reference the staff. Admins can deactivate (PATCH is_active=false) to
    keep them out of new bookings without losing history."""
    booking_count = await BookingRepository(db).count_for_staff(staff_id)
    if booking_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete this stylist: {booking_count} booking"
                f"{'s' if booking_count != 1 else ''} reference them. "
                "Deactivate instead to remove them from new bookings while preserving history."
            ),
        )
    if not await StaffRepository(db).delete(staff_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")


# ── Bookings ──────────────────────────────────────────────────────────────────


@router.get("/bookings", response_model=BookingPage)
async def list_bookings(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: BookingStatus | None = None,
    q: str | None = Query(None, max_length=100, description="Search across customer name and email"),
    start_from: date | None = Query(None, description="Filter bookings starting on or after this salon-local date"),
    start_to: date | None = Query(None, description="Filter bookings starting on or before this salon-local date (inclusive)"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> BookingPage:
    if start_from and start_to and start_from > start_to:
        # Can't reference status.HTTP_400_BAD_REQUEST here — the `status`
        # parameter shadows the fastapi module import inside this function body.
        raise HTTPException(status_code=400, detail="start_from must be on or before start_to")
    repo = BookingRepository(db)
    items = await repo.get_all_with_details(
        limit=limit, offset=offset, status=status, q=q, start_from=start_from, start_to=start_to,
    )
    total = await repo.count_all(status=status, q=q, start_from=start_from, start_to=start_to)
    return BookingPage(items=items, total=total, limit=limit, offset=offset)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingDetailResponse)
async def admin_cancel(
    booking_id: uuid.UUID,
    body: BookingCancelRequest = BookingCancelRequest(),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    admin: User = Depends(get_current_admin),
):
    return await cancel_booking(db, redis, booking_id, admin.id, reason=body.reason, is_admin=True)


@router.post("/bookings/{booking_id}/reschedule", response_model=BookingDetailResponse)
async def admin_reschedule(
    booking_id: uuid.UUID,
    body: BookingRescheduleRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    admin: User = Depends(get_current_admin),
):
    return await reschedule_booking(
        db,
        redis,
        booking_id,
        admin.id,
        body.start_time,
        is_admin=True,
        new_staff_id=body.staff_id,
    )


@router.post("/bookings/{booking_id}/complete", response_model=BookingDetailResponse)
async def admin_complete(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    repo = BookingRepository(db)
    booking = await repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status != BookingStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking is already {booking.status.value}",
        )
    booking.status = BookingStatus.COMPLETED
    await db.commit()
    return await BookingRepository(db).get_with_details(booking_id)


@router.post("/bookings/{booking_id}/no-show", response_model=BookingDetailResponse)
async def admin_no_show(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Mark a booking as a no-show. Only valid on confirmed bookings whose
    start time has passed — marking a future booking as no-show would be a
    data-quality bug, so we surface it as 400 instead of letting it through."""
    repo = BookingRepository(db)
    booking = await repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status != BookingStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking is already {booking.status.value}",
        )
    start = booking.start_time if booking.start_time.tzinfo else booking.start_time.replace(tzinfo=timezone.utc)
    if start > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot mark a future booking as no-show.",
        )
    booking.status = BookingStatus.NO_SHOW
    await db.commit()
    return await BookingRepository(db).get_with_details(booking_id)
