import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.db.models.booking import BookingStatus
from app.db.models.user import User
from app.db.redis import get_redis
from app.db.repositories.booking_repository import BookingRepository
from app.db.repositories.business_repository import BusinessRepository
from app.db.repositories.service_repository import ServiceRepository
from app.db.session import get_db
from app.schemas.booking import BookingDetailResponse, BookingPage
from app.schemas.business import (
    BlockedDateCreate,
    BlockedDateResponse,
    BusinessHoursResponse,
    BusinessHoursUpdate,
)
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate
from app.services.booking_service import cancel_booking

router = APIRouter(prefix="/admin", tags=["admin"])

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


# ── Bookings ──────────────────────────────────────────────────────────────────


@router.get("/bookings", response_model=BookingPage)
async def list_bookings(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: BookingStatus | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> BookingPage:
    repo = BookingRepository(db)
    items = await repo.get_all_with_details(limit=limit, offset=offset, status=status)
    total = await repo.count_all(status=status)
    return BookingPage(items=items, total=total, limit=limit, offset=offset)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingDetailResponse)
async def admin_cancel(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    admin: User = Depends(get_current_admin),
):
    return await cancel_booking(db, redis, booking_id, admin.id, is_admin=True)


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
