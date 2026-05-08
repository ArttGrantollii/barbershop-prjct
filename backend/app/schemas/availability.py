import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class SlotStatus(str, Enum):
    AVAILABLE = "available"
    HELD = "held"
    BOOKED = "booked"
    COOLDOWN = "cooldown"


class TimeSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    status: SlotStatus


class HoldRequest(BaseModel):
    service_id: uuid.UUID
    start_time: datetime
    # Optional: caller can pin the hold to a specific stylist. Omitted by
    # the legacy single-staff frontend; the resolver auto-picks then.
    staff_id: uuid.UUID | None = None


class HoldResponse(BaseModel):
    start_time: datetime
    end_time: datetime
    # Echo back the assigned stylist so the client can pass it to /bookings
    # and DELETE /availability/hold without re-resolving.
    staff_id: uuid.UUID
    expires_in_seconds: int


class ReleaseRequest(BaseModel):
    service_id: uuid.UUID
    start_time: datetime
    staff_id: uuid.UUID | None = None
