import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.db.models.booking import WaitlistStatus
from app.schemas.booking import BookingDetailResponse, ServiceSummary, StaffSummary, UserSummary


class WaitlistEntryCreate(BaseModel):
    service_id: uuid.UUID
    staff_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    preferred_date: date | None = None
    notes: str | None = None


class WaitlistEntryUpdate(BaseModel):
    status: WaitlistStatus


class WaitlistEntryBookRequest(BaseModel):
    start_time: datetime
    staff_id: uuid.UUID | None = None
    notes: str | None = None


class WaitlistEntryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID | None
    service_id: uuid.UUID
    staff_id: uuid.UUID | None
    booking_id: uuid.UUID | None
    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    preferred_date: date | None
    notes: str | None
    status: WaitlistStatus
    created_at: datetime
    service: ServiceSummary | None = None
    user: UserSummary | None = None
    staff: StaffSummary | None = None


class WaitlistEntryBookedResponse(BaseModel):
    waitlist_entry: WaitlistEntryResponse
    booking: BookingDetailResponse
