import uuid
from typing import TYPE_CHECKING

from datetime import datetime, time as time_t

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.booking import Booking
    from app.db.models.service import Service


# Many-to-many between services and staff. Defined as a Table (not a model)
# because there's no business data on the link itself — just (service_id,
# staff_id) presence. SQLAlchemy can use it via `relationship.secondary`.
service_staff = Table(
    "service_staff",
    Base.metadata,
    Column("service_id", ForeignKey("services.id", ondelete="CASCADE"), primary_key=True),
    Column("staff_id", ForeignKey("staff.id", ondelete="CASCADE"), primary_key=True),
)


class Staff(Base, TimestampMixin):
    __tablename__ = "staff"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Manual ordering knob for the customer-facing stylist list. Two staff at
    # the same value sort by created_at as a stable tiebreaker.
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    services: Mapped[list["Service"]] = relationship(
        secondary=service_staff, back_populates="staff_members"
    )
    bookings: Mapped[list["Booking"]] = relationship(back_populates="staff")
    working_hours: Mapped[list["StaffWorkingHours"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )
    blocked_times: Mapped[list["StaffBlockedTime"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )


class StaffWorkingHours(Base, TimestampMixin):
    __tablename__ = "staff_working_hours"
    __table_args__ = (
        UniqueConstraint("staff_id", "day_of_week", name="uq_staff_working_hours_staff_day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", ondelete="CASCADE"), index=True)
    day_of_week: Mapped[int] = mapped_column(Integer)
    open_time: Mapped[time_t] = mapped_column(Time)
    close_time: Mapped[time_t] = mapped_column(Time)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)

    staff: Mapped["Staff"] = relationship(back_populates="working_hours")


class StaffBlockedTime(Base, TimestampMixin):
    __tablename__ = "staff_blocked_times"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_staff_blocked_times_valid_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", ondelete="CASCADE"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    staff: Mapped["Staff"] = relationship(back_populates="blocked_times")
