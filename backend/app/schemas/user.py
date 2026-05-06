import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.db.models.user import UserRole


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        digits = re.sub(r"\D", "", v)
        if not 7 <= len(digits) <= 15:
            raise ValueError("Invalid phone number")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    email: str
    phone: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
