import re
import uuid

from pydantic import BaseModel, field_validator


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
