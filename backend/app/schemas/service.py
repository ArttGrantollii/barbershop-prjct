import uuid
from decimal import Decimal

from pydantic import BaseModel, field_validator


class ServiceCreate(BaseModel):
    name: str
    description: str | None = None
    duration_minutes: int
    price: Decimal

    @field_validator("duration_minutes")
    @classmethod
    def positive_duration(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("duration_minutes must be positive")
        return v


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    price: Decimal | None = None
    is_active: bool | None = None


class ServiceResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    duration_minutes: int
    price: Decimal
    is_active: bool
