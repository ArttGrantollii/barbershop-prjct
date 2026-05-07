from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/business-info", tags=["business"])


class BusinessInfoResponse(BaseModel):
    name: str
    timezone: str


@router.get("", response_model=BusinessInfoResponse)
async def get_business_info() -> BusinessInfoResponse:
    """Public metadata the frontend needs to render times in the salon's
    local timezone instead of the visitor's browser timezone."""
    return BusinessInfoResponse(
        name=settings.PROJECT_NAME,
        timezone=settings.SALON_TIMEZONE,
    )
