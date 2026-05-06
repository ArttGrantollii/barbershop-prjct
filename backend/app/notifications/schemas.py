from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BookingInfo:
    booking_id: str
    customer_name: str
    customer_email: str
    customer_phone: str | None
    service_name: str
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    cancellation_reason: str | None = field(default=None)
