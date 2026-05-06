import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.service import Service
from app.db.repositories.base import BaseRepository


class ServiceRepository(BaseRepository[Service]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Service, db)

    async def get_by_id(self, id: uuid.UUID) -> Service | None:  # type: ignore[override]
        result = await self.db.execute(
            select(Service).where(Service.id == id)
        )
        return result.scalars().one_or_none()

    async def get_active(self) -> list[Service]:
        result = await self.db.execute(
            select(Service).where(Service.is_active == True).order_by(Service.name)  # noqa: E712
        )
        return list(result.scalars().all())

    async def create(
        self,
        name: str,
        description: str | None,
        duration_minutes: int,
        price: Decimal,
    ) -> Service:
        return await self.save(
            Service(name=name, description=description, duration_minutes=duration_minutes, price=price)
        )

    async def update(self, service: Service, **kwargs) -> Service:
        for key, value in kwargs.items():
            setattr(service, key, value)
        return await self.save(service)
