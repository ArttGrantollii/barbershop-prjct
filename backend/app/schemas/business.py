import uuid
from datetime import date, time

from pydantic import BaseModel


class BusinessHoursUpdate(BaseModel):
    open_time: time | None = None
    close_time: time | None = None
    is_closed: bool | None = None


class BusinessHoursResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    day_of_week: int
    open_time: time
    close_time: time
    is_closed: bool


class BlockedDateCreate(BaseModel):
    date: date
    reason: str | None = None


class BlockedDateResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    date: date
    reason: str | None
