from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.service_repository import ServiceRepository
from app.db.session import get_db
from app.schemas.service import ServiceResponse

router = APIRouter(prefix="/services", tags=["services"])


@router.get("", response_model=list[ServiceResponse])
async def list_services(db: AsyncSession = Depends(get_db)) -> list:
    return await ServiceRepository(db).get_active()
