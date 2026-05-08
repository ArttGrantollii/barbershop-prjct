import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_current_customer
from app.db.models.user import User, UserRole
from app.db.redis import get_redis
from app.db.repositories.booking_repository import BookingRepository
from app.db.session import get_db
from app.schemas.booking import (
    BookingCancelRequest,
    BookingCreate,
    BookingDetailResponse,
    BookingRescheduleRequest,
)
from app.services.booking_service import cancel_booking, create_booking, reschedule_booking

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("/my", response_model=list[BookingDetailResponse])
async def my_bookings(
    current_user: User = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
) -> list:
    return await BookingRepository(db).get_by_user(current_user.id)


@router.post("", response_model=BookingDetailResponse, status_code=status.HTTP_201_CREATED)
async def book(
    body: BookingCreate,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_customer),
):
    return await create_booking(
        db, redis, current_user.id, body.service_id, body.start_time, body.notes,
        staff_id=body.staff_id,
    )


@router.get("/{booking_id}", response_model=BookingDetailResponse)
async def get_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Fetch a single booking. Owners can view their own; admins can view any.
    Used by the confirmation page on refresh and could power a future
    public share / reschedule page."""
    booking = await BookingRepository(db).get_with_details(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if current_user.role != UserRole.ADMIN and booking.user_id != current_user.id:
        # Mask existence so a customer can't enumerate other users' booking ids.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingDetailResponse)
async def cancel(
    booking_id: uuid.UUID,
    body: BookingCancelRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_customer),
):
    return await cancel_booking(db, redis, booking_id, current_user.id, body.reason, is_admin=False)


@router.post("/{booking_id}/reschedule", response_model=BookingDetailResponse)
async def reschedule(
    booking_id: uuid.UUID,
    body: BookingRescheduleRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_customer),
):
    return await reschedule_booking(
        db, redis, booking_id, current_user.id, body.start_time,
        is_admin=False, new_staff_id=body.staff_id,
    )
