import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.booking import AuditActorRole, BookingAuditEvent
from app.db.repositories.base import BaseRepository


class BookingAuditRepository(BaseRepository[BookingAuditEvent]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(BookingAuditEvent, db)

    async def create_event(
        self,
        *,
        booking_id: uuid.UUID,
        action: str,
        actor_role: AuditActorRole,
        actor_id: uuid.UUID | None = None,
        previous_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
    ) -> BookingAuditEvent:
        return await self.save(
            BookingAuditEvent(
                booking_id=booking_id,
                actor_id=actor_id,
                actor_role=actor_role,
                action=action,
                previous_values=previous_values,
                new_values=new_values,
            )
        )

    async def get_for_booking(self, booking_id: uuid.UUID) -> list[BookingAuditEvent]:
        result = await self.db.execute(
            select(BookingAuditEvent)
            .where(BookingAuditEvent.booking_id == booking_id)
            .order_by(BookingAuditEvent.created_at.desc())
        )
        return list(result.scalars().all())
