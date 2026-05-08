import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
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
