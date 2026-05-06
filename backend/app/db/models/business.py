import uuid
from datetime import date as date_t, time as time_t

from sqlalchemy import Boolean, Date, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class BusinessHours(Base, TimestampMixin):
    __tablename__ = "business_hours"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0 = Monday, 6 = Sunday
    open_time: Mapped[time_t] = mapped_column(Time)
    close_time: Mapped[time_t] = mapped_column(Time)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)


class BlockedDate(Base, TimestampMixin):
    __tablename__ = "blocked_dates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    date: Mapped[date_t] = mapped_column(Date, unique=True, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
