import uuid
from datetime import date as date_t, time as time_t

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.business import BlockedDate, BusinessHours
from app.db.repositories.base import BaseRepository


class BusinessRepository(BaseRepository[BusinessHours]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(BusinessHours, db)

    async def get_by_id(self, id: uuid.UUID) -> BusinessHours | None:  # type: ignore[override]
        result = await self.db.execute(select(BusinessHours).where(BusinessHours.id == id))
        return result.scalars().one_or_none()

    async def get_hours_for_day(self, day_of_week: int) -> BusinessHours | None:
        result = await self.db.execute(
            select(BusinessHours).where(BusinessHours.day_of_week == day_of_week)
        )
        return result.scalar_one_or_none()

    async def get_all_hours(self) -> list[BusinessHours]:
        result = await self.db.execute(
            select(BusinessHours).order_by(BusinessHours.day_of_week)
        )
        return list(result.scalars().all())

    async def upsert_hours(
        self,
        day_of_week: int,
        open_time: time_t,
        close_time: time_t,
        is_closed: bool = False,
    ) -> BusinessHours:
        existing = await self.get_hours_for_day(day_of_week)
        if existing:
            existing.open_time = open_time
            existing.close_time = close_time
            existing.is_closed = is_closed
            return await self.save(existing)
        return await self.save(
            BusinessHours(
                day_of_week=day_of_week,
                open_time=open_time,
                close_time=close_time,
                is_closed=is_closed,
            )
        )

    async def is_date_blocked(self, target_date: date_t) -> bool:
        result = await self.db.execute(
            select(BlockedDate).where(BlockedDate.date == target_date)
        )
        return result.scalar_one_or_none() is not None

    async def get_blocked_dates(self) -> list[BlockedDate]:
        result = await self.db.execute(select(BlockedDate).order_by(BlockedDate.date))
        return list(result.scalars().all())

    async def get_blocked_date_by_id(self, id: uuid.UUID) -> BlockedDate | None:
        result = await self.db.execute(select(BlockedDate).where(BlockedDate.id == id))
        return result.scalar_one_or_none()

    async def create_blocked_date(self, target_date: date_t, reason: str | None = None) -> BlockedDate:
        bd = BlockedDate(date=target_date, reason=reason)
        self.db.add(bd)
        await self.db.commit()
        await self.db.refresh(bd)
        return bd

    async def delete_blocked_date(self, id: uuid.UUID) -> bool:
        bd = await self.get_blocked_date_by_id(id)
        if bd is None:
            return False
        await self.db.delete(bd)
        await self.db.commit()
        return True
