import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.db.models.user import UserRole


def _validate_phone(v: str | None) -> str | None:
    """Return a normalized phone string, or None for empty input. Reused by
    UserCreate and UserUpdate so the same rules apply at signup and edit."""
    if v is None or v.strip() == "":
        return None
    digits = re.sub(r"\D", "", v)
    if not 7 <= len(digits) <= 15:
        raise ValueError("Invalid phone number")
    return v


def _validate_password(v: str) -> str:
    """Password policy applied at registration and password-change.
    Min 10 chars, max 72 bytes (bcrypt truncates beyond that), must mix
    letters and digits."""
    if len(v) < 10:
        raise ValueError("Password must be at least 10 characters")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes")
    if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
        raise ValueError("Password must contain both letters and numbers")
    return v


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _validate_phone(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)


class UserUpdate(BaseModel):
    """PATCH-style profile edit. Email is intentionally not editable here —
    changing email needs a verification flow (deferred), so today users keep
    the address they registered with. Password has its own dedicated endpoint."""
    name: str | None = None
    phone: str | None = None

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


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password(v)


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    email: str
    phone: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
