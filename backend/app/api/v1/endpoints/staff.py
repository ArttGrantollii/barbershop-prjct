"""Public staff listing — anyone (including unauthenticated browsers) can see
the active stylists. Used by the customer-facing booking flow when the user
wants to pick a specific stylist."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.staff_repository import StaffRepository
from app.db.session import get_db
from app.schemas.staff import StaffResponse

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("", response_model=list[StaffResponse])
async def list_active_staff(db: AsyncSession = Depends(get_db)) -> list:
    return await StaffRepository(db).get_active()


@router.get("/by-service/{service_id}", response_model=list[StaffResponse])
async def list_staff_for_service(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list:
    """Stylists who offer a specific service. Powers the per-service stylist
    picker in the booking flow."""
    return await StaffRepository(db).get_active_for_service(service_id)
