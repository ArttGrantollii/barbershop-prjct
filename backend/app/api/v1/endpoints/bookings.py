import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user
from app.db.models.user import User
from app.db.redis import get_redis
from app.db.repositories.booking_repository import BookingRepository
from app.db.session import get_db
from app.schemas.booking import BookingCancelRequest, BookingCreate, BookingDetailResponse
from app.services.booking_service import cancel_booking, create_booking

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("/my", response_model=list[BookingDetailResponse])
async def my_bookings(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list:
    return await BookingRepository(db).get_by_user(current_user.id)


@router.post("", response_model=BookingDetailResponse, status_code=status.HTTP_201_CREATED)
async def book(
    body: BookingCreate,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_active_user),
):
    return await create_booking(db, redis, current_user.id, body.service_id, body.start_time, body.notes)


@router.post("/{booking_id}/cancel", response_model=BookingDetailResponse)
async def cancel(
    booking_id: uuid.UUID,
    body: BookingCancelRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_active_user),
):
    return await cancel_booking(db, redis, booking_id, current_user.id, body.reason, is_admin=False)
