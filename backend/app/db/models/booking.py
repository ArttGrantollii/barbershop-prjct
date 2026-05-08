import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class BookingStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"))
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[BookingStatus] = mapped_column(
        SQLEnum(BookingStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=BookingStatus.CONFIRMED,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set by the reminder worker after a 24h-before notification fires.
    # Null means a reminder is still owed (or the worker hasn't reached it).
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="bookings")
    service: Mapped["Service"] = relationship("Service", back_populates="bookings")
    staff: Mapped["Staff"] = relationship("Staff", back_populates="bookings")
