import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum as SQLEnum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class BookingStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class WaitlistStatus(str, enum.Enum):
    ACTIVE = "active"
    BOOKED = "booked"
    CANCELLED = "cancelled"


class AuditActorRole(str, enum.Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    SYSTEM = "system"


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"))
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id"), index=True)
    customer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[BookingStatus] = mapped_column(
        SQLEnum(BookingStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=BookingStatus.CONFIRMED,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when the reminder worker claims this booking for a send attempt.
    reminder_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set only after the notification backend accepts the reminder.
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Last terminal reason a reminder attempt did not become a successful send.
    reminder_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="bookings")
    service: Mapped["Service"] = relationship("Service", back_populates="bookings")
    staff: Mapped["Staff"] = relationship("Staff", back_populates="bookings")


class WaitlistEntry(Base, TimestampMixin):
    __tablename__ = "waitlist_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"), index=True)
    staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff.id"), index=True, nullable=True)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(100))
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[WaitlistStatus] = mapped_column(
        SQLEnum(WaitlistStatus, values_callable=lambda obj: [e.value for e in obj]),
        index=True,
        default=WaitlistStatus.ACTIVE,
    )

    user: Mapped["User"] = relationship("User")
    service: Mapped["Service"] = relationship("Service")
    staff: Mapped["Staff"] = relationship("Staff")
    booking: Mapped["Booking"] = relationship("Booking")


class BookingAuditEvent(Base, TimestampMixin):
    __tablename__ = "booking_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    actor_role: Mapped[AuditActorRole] = mapped_column(
        SQLEnum(AuditActorRole, values_callable=lambda obj: [e.value for e in obj]),
    )
    action: Mapped[str] = mapped_column(String(50), index=True)
    previous_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    booking: Mapped["Booking"] = relationship("Booking")
    actor: Mapped["User"] = relationship("User")
