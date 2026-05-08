import re
import uuid
from datetime import datetime, time

from pydantic import BaseModel, field_validator, model_validator


def _validate_phone(v: str | None) -> str | None:
    """Same lightweight phone shape as user.py — duplicated rather than
    imported to keep the staff schema self-contained."""
    if v is None or v.strip() == "":
        return None
    digits = re.sub(r"\D", "", v)
    if not 7 <= len(digits) <= 15:
        raise ValueError("Invalid phone number")
    return v


class StaffCreate(BaseModel):
    name: str
    phone: str | None = None
    photo_url: str | None = None
    display_order: int = 0
    # Optional initial service assignments. Empty list means "offers nothing"
    # — admin can assign later via PATCH.
    service_ids: list[uuid.UUID] = []

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        if len(v) > 100:
            raise ValueError("Name is too long")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _validate_phone(v)


class StaffUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    photo_url: str | None = None
    is_active: bool | None = None
    display_order: int | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        if len(v) > 100:
            raise ValueError("Name is too long")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _validate_phone(v)


class StaffServicesUpdate(BaseModel):
    """Replace-the-whole-set semantics: the staff member ends up offering
    exactly the services in `service_ids`, no more, no less."""
    service_ids: list[uuid.UUID]


class StaffWorkingHoursUpdate(BaseModel):
    open_time: time | None = None
    close_time: time | None = None
    is_closed: bool | None = None


class StaffBlockedTimeCreate(BaseModel):
    start_time: datetime
    end_time: datetime
    reason: str | None = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class StaffResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    phone: str | None
    photo_url: str | None
    is_active: bool
    display_order: int


class StaffWithServicesResponse(StaffResponse):
    # Returned by admin endpoints so the UI can render the assignment matrix
    # in a single round trip.
    service_ids: list[uuid.UUID] = []


class StaffWorkingHoursResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    staff_id: uuid.UUID
    day_of_week: int
    open_time: time
    close_time: time
    is_closed: bool


class StaffBlockedTimeResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    staff_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    reason: str | None
