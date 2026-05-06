import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.booking import Booking, BookingStatus
from app.db.repositories.base import BaseRepository


class BookingRepository(BaseRepository[Booking]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Booking, db)

    async def get_by_id(self, id: uuid.UUID) -> Booking | None:  # type: ignore[override]
        result = await self.db.execute(select(Booking).where(Booking.id == id))
        return result.scalars().one_or_none()

    async def get_for_date(self, target_date: date) -> list[Booking]:
        day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        result = await self.db.execute(
            select(Booking).where(
                and_(
                    Booking.start_time >= day_start,
                    Booking.start_time < day_end,
                    Booking.status == BookingStatus.CONFIRMED,
                )
            )
        )
        return list(result.scalars().all())

    async def has_overlap(
        self,
        start_time: datetime,
        end_time: datetime,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        q = select(Booking).where(
            and_(
                Booking.status == BookingStatus.CONFIRMED,
                Booking.start_time < end_time,
                Booking.end_time > start_time,
            )
        )
        if exclude_id is not None:
            q = q.where(Booking.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def get_by_user(self, user_id: uuid.UUID) -> list[Booking]:
        result = await self.db.execute(
            select(Booking)
            .where(Booking.user_id == user_id)
            .options(selectinload(Booking.service))
            .order_by(Booking.start_time.desc())
        )
        return list(result.scalars().all())

    async def get_all_with_details(self, limit: int = 100, offset: int = 0) -> list[Booking]:
        result = await self.db.execute(
            select(Booking)
            .options(selectinload(Booking.user), selectinload(Booking.service))
            .order_by(Booking.start_time.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create_booking(
        self,
        user_id: uuid.UUID,
        service_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        notes: str | None = None,
    ) -> Booking:
        return await self.save(
            Booking(
                user_id=user_id,
                service_id=service_id,
                start_time=start_time,
                end_time=end_time,
                notes=notes,
            )
        )
