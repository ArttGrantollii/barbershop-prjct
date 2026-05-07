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
        if len(v) < 10:
            raise ValueError("Password must be at least 10 characters")
        # bcrypt silently truncates beyond 72 bytes — reject explicitly so users
        # don't end up authenticating with only the first 72 bytes of what they typed.
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain both letters and numbers")
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
