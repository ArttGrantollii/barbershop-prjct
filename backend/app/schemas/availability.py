import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class SlotStatus(str, Enum):
    AVAILABLE = "available"
    HELD = "held"
    BOOKED = "booked"


class TimeSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    status: SlotStatus


class HoldRequest(BaseModel):
    service_id: uuid.UUID
    start_time: datetime


class HoldResponse(BaseModel):
    start_time: datetime
    end_time: datetime
    expires_in_seconds: int


class ReleaseRequest(BaseModel):
    service_id: uuid.UUID
    start_time: datetime
