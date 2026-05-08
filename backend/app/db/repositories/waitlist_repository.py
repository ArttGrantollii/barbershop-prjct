import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.booking import WaitlistEntry, WaitlistStatus
from app.db.repositories.base import BaseRepository


class WaitlistRepository(BaseRepository[WaitlistEntry]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(WaitlistEntry, db)

    async def get_by_id(self, id: uuid.UUID) -> WaitlistEntry | None:  # type: ignore[override]
        result = await self.db.execute(select(WaitlistEntry).where(WaitlistEntry.id == id))
        return result.scalars().one_or_none()

    async def get_with_details(self, id: uuid.UUID) -> WaitlistEntry | None:
        result = await self.db.execute(
            select(WaitlistEntry)
            .where(WaitlistEntry.id == id)
            .options(
                selectinload(WaitlistEntry.user),
                selectinload(WaitlistEntry.service),
                selectinload(WaitlistEntry.staff),
            )
        )
        return result.scalars().one_or_none()

    async def get_all_with_details(
        self,
        status: WaitlistStatus | None = WaitlistStatus.ACTIVE,
    ) -> list[WaitlistEntry]:
        stmt = (
            select(WaitlistEntry)
            .options(
                selectinload(WaitlistEntry.user),
                selectinload(WaitlistEntry.service),
                selectinload(WaitlistEntry.staff),
            )
            .order_by(WaitlistEntry.created_at.desc())
        )
        if status is not None:
            stmt = stmt.where(WaitlistEntry.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_entry(
        self,
        *,
        service_id: uuid.UUID,
        customer_name: str,
        staff_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        customer_email: str | None = None,
        customer_phone: str | None = None,
        preferred_date=None,
        notes: str | None = None,
    ) -> WaitlistEntry:
        return await self.save(
            WaitlistEntry(
                user_id=user_id,
                service_id=service_id,
                staff_id=staff_id,
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                preferred_date=preferred_date,
                notes=notes,
            )
        )

    async def update_status(
        self,
        entry: WaitlistEntry,
        status: WaitlistStatus,
        booking_id: uuid.UUID | None = None,
    ) -> WaitlistEntry:
        entry.status = status
        if booking_id is not None:
            entry.booking_id = booking_id
        return await self.save(entry)
