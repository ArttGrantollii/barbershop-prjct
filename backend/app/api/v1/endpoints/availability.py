from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_customer, get_current_verified_customer, get_optional_user
from app.db.models.user import User
from app.db.redis import get_redis
from app.db.repositories.service_repository import ServiceRepository
from app.db.session import get_db
from app.schemas.availability import HoldRequest, HoldResponse, ReleaseRequest, TimeSlot
from app.services.availability_service import get_slots
from app.services.booking_service import hold_slot, release_hold

router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("", response_model=list[TimeSlot])
async def get_availability(
    slot_date: Annotated[date, Query(alias="date")],
    service_id: UUID,
    staff_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User | None = Depends(get_optional_user),
) -> list:
    service = await ServiceRepository(db).get_by_id(service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return await get_slots(
        db,
        redis,
        service,
        slot_date,
        user_id=current_user.id if current_user else None,
        staff_id=staff_id,
    )


@router.post("/hold", response_model=HoldResponse)
async def hold(
    body: HoldRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_verified_customer),
) -> dict:
    return await hold_slot(
        db, redis, current_user.id, body.service_id, body.start_time, staff_id=body.staff_id,
    )


@router.delete("/hold", status_code=status.HTTP_204_NO_CONTENT)
async def release(
    body: ReleaseRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_customer),
) -> None:
    await release_hold(
        db, redis, current_user.id, body.service_id, body.start_time, staff_id=body.staff_id,
    )
