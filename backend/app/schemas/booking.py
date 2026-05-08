import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.db.models.booking import BookingStatus


class BookingCreate(BaseModel):
    service_id: uuid.UUID
    start_time: datetime
    notes: str | None = None
    staff_id: uuid.UUID | None = None


class AdminBookingCreate(BaseModel):
    service_id: uuid.UUID
    staff_id: uuid.UUID
    start_time: datetime
    status: BookingStatus = BookingStatus.CONFIRMED
    user_id: uuid.UUID | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    notes: str | None = None


class BookingCancelRequest(BaseModel):
    reason: str | None = None


class BookingRescheduleRequest(BaseModel):
    start_time: datetime
    staff_id: uuid.UUID | None = None


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


class StaffSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    photo_url: str | None = None


class BookingResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID | None
    service_id: uuid.UUID
    staff_id: uuid.UUID
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    notes: str | None
    cancellation_reason: str | None
    created_at: datetime


class BookingDetailResponse(BookingResponse):
    service: ServiceSummary | None = None
    user: UserSummary | None = None
    staff: StaffSummary | None = None


class BookingPage(BaseModel):
    items: list[BookingDetailResponse]
    total: int
    limit: int
    offset: int


class AdminDashboardResponse(BaseModel):
    today_bookings_count: int
    today_revenue: Decimal
    week_bookings_count: int
    confirmed_total: int
    cancelled_total: int
    today_schedule: list[BookingDetailResponse]
