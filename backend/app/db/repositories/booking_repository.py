import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models.booking import Booking, BookingStatus
from app.db.models.service import Service
from app.db.models.user import User
from app.db.repositories.base import BaseRepository


def _salon_day_bounds(target_date: date) -> tuple[datetime, datetime]:
    """Return [start, end) UTC instants that bound `target_date` *in the salon's
    local timezone*. Used wherever 'on this day' means a salon calendar day,
    not a UTC calendar day — otherwise users can double-book by crossing the
    UTC midnight boundary inside a single salon day."""
    tz = ZoneInfo(settings.SALON_TIMEZONE)
    day_start = datetime(
        target_date.year, target_date.month, target_date.day, tzinfo=tz
    )
    return day_start, day_start + timedelta(days=1)



class BookingRepository(BaseRepository[Booking]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Booking, db)

    async def get_by_id(self, id: uuid.UUID) -> Booking | None:  # type: ignore[override]
        result = await self.db.execute(select(Booking).where(Booking.id == id))
        return result.scalars().one_or_none()

    async def get_with_details(self, id: uuid.UUID) -> Booking | None:
        result = await self.db.execute(
            select(Booking)
            .where(Booking.id == id)
            .options(
                selectinload(Booking.service),
                selectinload(Booking.user),
                selectinload(Booking.staff),
            )
        )
        return result.scalars().one_or_none()

    async def get_for_date(self, target_date: date) -> list[Booking]:
        day_start, day_end = _salon_day_bounds(target_date)
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
        staff_id: uuid.UUID | None = None,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """True if any confirmed booking overlaps the [start, end) range.
        When `staff_id` is provided, the check is scoped to that staff —
        which is the right semantics post-Phase-5: two confirmed bookings
        may overlap iff they're with different staff. With `staff_id=None`
        (legacy callers), the check spans the whole shop (single-chair
        semantics)."""
        q = select(Booking).where(
            and_(
                Booking.status == BookingStatus.CONFIRMED,
                Booking.start_time < end_time,
                Booking.end_time > start_time,
            )
        )
        if staff_id is not None:
            q = q.where(Booking.staff_id == staff_id)
        if exclude_id is not None:
            q = q.where(Booking.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def get_by_user(self, user_id: uuid.UUID) -> list[Booking]:
        result = await self.db.execute(
            select(Booking)
            .where(Booking.user_id == user_id)
            .options(selectinload(Booking.service), selectinload(Booking.staff))
            .order_by(Booking.start_time.desc())
        )
        return list(result.scalars().all())

    async def count_confirmed_for_user_on_date(
        self,
        user_id: uuid.UUID | None,
        target_date: date,
        exclude_id: uuid.UUID | None = None,
    ) -> int:
        """`target_date` is interpreted as a salon-local calendar day. Set
        `exclude_id` when checking whether a *new* time would violate the
        same-day rule for a booking that's being moved — it lets the booking
        not count against itself."""
        day_start, day_end = _salon_day_bounds(target_date)
        clauses = [
            Booking.user_id == user_id,
            Booking.status == BookingStatus.CONFIRMED,
            Booking.start_time >= day_start,
            Booking.start_time < day_end,
        ]
        if exclude_id is not None:
            clauses.append(Booking.id != exclude_id)
        result = await self.db.execute(
            select(func.count()).select_from(Booking).where(and_(*clauses))
        )
        return result.scalar_one()

    def _admin_filter_clauses(
        self,
        status: BookingStatus | None,
        q: str | None,
        start_from: date | None,
        start_to: date | None,
    ):
        """Build the WHERE clauses shared by `count_all` and `get_all_with_details`
        so the count and the page always reflect the same filter set."""
        clauses = []
        if status is not None:
            clauses.append(Booking.status == status)
        if q:
            term = f"%{q.lower()}%"
            clauses.append(
                or_(
                    func.lower(User.name).like(term),
                    func.lower(User.email).like(term),
                    func.lower(Booking.customer_name).like(term),
                    func.lower(Booking.customer_email).like(term),
                    func.lower(Booking.customer_phone).like(term),
                )
            )
        if start_from is not None:
            tz = ZoneInfo(settings.SALON_TIMEZONE)
            day_start = datetime(start_from.year, start_from.month, start_from.day, tzinfo=tz)
            clauses.append(Booking.start_time >= day_start)
        if start_to is not None:
            tz = ZoneInfo(settings.SALON_TIMEZONE)
            # `start_to` is inclusive — so the upper bound is the next day's
            # midnight in salon-local time.
            day_end = datetime(start_to.year, start_to.month, start_to.day, tzinfo=tz) + timedelta(days=1)
            clauses.append(Booking.start_time < day_end)
        return clauses

    async def count_all(
        self,
        status: BookingStatus | None = None,
        q: str | None = None,
        start_from: date | None = None,
        start_to: date | None = None,
    ) -> int:
        clauses = self._admin_filter_clauses(status, q, start_from, start_to)
        stmt = select(func.count()).select_from(Booking)
        if q:
            stmt = stmt.outerjoin(User, User.id == Booking.user_id)
        if clauses:
            stmt = stmt.where(*clauses)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def count_between(
        self,
        start_time: datetime,
        end_time: datetime,
        status: BookingStatus | None = None,
    ) -> int:
        clauses = [
            Booking.start_time >= start_time,
            Booking.start_time < end_time,
        ]
        if status is not None:
            clauses.append(Booking.status == status)
        result = await self.db.execute(
            select(func.count()).select_from(Booking).where(and_(*clauses))
        )
        return result.scalar_one()

    async def revenue_between(
        self,
        start_time: datetime,
        end_time: datetime,
        status: BookingStatus = BookingStatus.CONFIRMED,
    ) -> Decimal:
        result = await self.db.execute(
            select(func.coalesce(func.sum(Service.price), 0))
            .select_from(Booking)
            .join(Service, Service.id == Booking.service_id)
            .where(
                Booking.status == status,
                Booking.start_time >= start_time,
                Booking.start_time < end_time,
            )
        )
        return result.scalar_one()

    async def get_between_with_details(
        self,
        start_time: datetime,
        end_time: datetime,
        status: BookingStatus | None = None,
    ) -> list[Booking]:
        clauses = [
            Booking.start_time >= start_time,
            Booking.start_time < end_time,
        ]
        if status is not None:
            clauses.append(Booking.status == status)
        result = await self.db.execute(
            select(Booking)
            .where(and_(*clauses))
            .options(
                selectinload(Booking.user),
                selectinload(Booking.service),
                selectinload(Booking.staff),
            )
            .order_by(Booking.start_time.asc())
        )
        return list(result.scalars().all())

    async def count_for_service(self, service_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Booking)
            .where(Booking.service_id == service_id)
        )
        return result.scalar_one()

    async def count_for_staff(self, staff_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Booking)
            .where(Booking.staff_id == staff_id)
        )
        return result.scalar_one()

    async def get_all_with_details(
        self,
        limit: int = 50,
        offset: int = 0,
        status: BookingStatus | None = None,
        q: str | None = None,
        start_from: date | None = None,
        start_to: date | None = None,
    ) -> list[Booking]:
        clauses = self._admin_filter_clauses(status, q, start_from, start_to)
        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.user),
                selectinload(Booking.service),
                selectinload(Booking.staff),
            )
            .order_by(Booking.start_time.desc())
            .limit(limit)
            .offset(offset)
        )
        if q:
            stmt = stmt.outerjoin(User, User.id == Booking.user_id)
        if clauses:
            stmt = stmt.where(*clauses)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_booking(
        self,
        user_id: uuid.UUID,
        service_id: uuid.UUID,
        staff_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        notes: str | None = None,
        status: BookingStatus = BookingStatus.CONFIRMED,
        customer_name: str | None = None,
        customer_email: str | None = None,
        customer_phone: str | None = None,
    ) -> Booking:
        return await self.save(
            Booking(
                user_id=user_id,
                service_id=service_id,
                staff_id=staff_id,
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                start_time=start_time,
                end_time=end_time,
                status=status,
                notes=notes,
            )
        )
