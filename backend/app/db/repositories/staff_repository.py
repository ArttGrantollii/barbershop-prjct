import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.service import Service
from app.db.models.staff import Staff, service_staff
from app.db.repositories.base import BaseRepository


class StaffRepository(BaseRepository[Staff]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Staff, db)

    async def get_by_id(self, id: uuid.UUID) -> Staff | None:  # type: ignore[override]
        result = await self.db.execute(select(Staff).where(Staff.id == id))
        return result.scalar_one_or_none()

    async def get_with_services(self, id: uuid.UUID) -> Staff | None:
        result = await self.db.execute(
            select(Staff).where(Staff.id == id).options(selectinload(Staff.services))
        )
        return result.scalar_one_or_none()

    async def get_active(self) -> list[Staff]:
        result = await self.db.execute(
            select(Staff)
            .where(Staff.is_active == True)  # noqa: E712
            .order_by(Staff.display_order, Staff.created_at)
        )
        return list(result.scalars().all())

    async def get_all_with_services(self) -> list[Staff]:
        """Admin listing — includes inactive staff and eagerly loads each
        staff member's services so the admin UI can render the assignment
        matrix without an N+1."""
        result = await self.db.execute(
            select(Staff)
            .options(selectinload(Staff.services))
            .order_by(Staff.display_order, Staff.created_at)
        )
        return list(result.scalars().all())

    async def get_active_for_service(self, service_id: uuid.UUID) -> list[Staff]:
        """Active staff who offer the given service, ordered the way the
        customer-facing list expects."""
        result = await self.db.execute(
            select(Staff)
            .join(service_staff, service_staff.c.staff_id == Staff.id)
            .where(
                service_staff.c.service_id == service_id,
                Staff.is_active == True,  # noqa: E712
            )
            .order_by(Staff.display_order, Staff.created_at)
        )
        return list(result.scalars().all())

    async def staff_offers_service(self, staff_id: uuid.UUID, service_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(service_staff)
            .where(
                service_staff.c.staff_id == staff_id,
                service_staff.c.service_id == service_id,
            )
        )
        return result.first() is not None

    async def create(
        self,
        name: str,
        phone: str | None = None,
        photo_url: str | None = None,
        display_order: int = 0,
    ) -> Staff:
        return await self.save(
            Staff(name=name, phone=phone, photo_url=photo_url, display_order=display_order)
        )

    async def update(self, staff: Staff, **kwargs) -> Staff:
        for key, value in kwargs.items():
            setattr(staff, key, value)
        return await self.save(staff)

    async def set_services(self, staff: Staff, service_ids: list[uuid.UUID]) -> Staff:
        """Replace the staff member's service assignments with the given set.
        Loads `services` first so SQLAlchemy can diff and emit minimal
        INSERT/DELETE on the join table — much cheaper than dropping all
        rows and re-inserting."""
        # Ensure relationship is loaded; otherwise assigning to it triggers
        # a lazy load mid-write which fails in async.
        await self.db.refresh(staff, attribute_names=["services"])
        if service_ids:
            result = await self.db.execute(
                select(Service).where(Service.id.in_(service_ids))
            )
            services = list(result.scalars().all())
        else:
            services = []
        staff.services = services
        await self.db.commit()
        await self.db.refresh(staff, attribute_names=["services"])
        return staff
