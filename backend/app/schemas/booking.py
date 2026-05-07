import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.db.models.booking import BookingStatus


class BookingCreate(BaseModel):
    service_id: uuid.UUID
    start_time: datetime
    notes: str | None = None


class BookingCancelRequest(BaseModel):
    reason: str | None = None


class BookingRescheduleRequest(BaseModel):
    start_time: datetime


class ServiceSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    duration_minutes: int
    price: Decimal


class UserSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    email: str
    phone: str | None


class BookingResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    service_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    notes: str | None
    cancellation_reason: str | None
    created_at: datetime


class BookingDetailResponse(BookingResponse):
    service: ServiceSummary | None = None
    user: UserSummary | None = None


class BookingPage(BaseModel):
    items: list[BookingDetailResponse]
    total: int
    limit: int
    offset: int
