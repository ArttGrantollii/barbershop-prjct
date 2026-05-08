"""Database integration tests for booking capacity invariants.

These tests use a separate Postgres database and run Alembic migrations against
it. They intentionally verify behavior the mock-heavy unit tests cannot: the
actual database exclusion constraint that protects same-staff overlapping
bookings under concurrency.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import get_password_hash
from app.db.models.booking import Booking
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.user import User


TEST_DB_NAME = "vendos_salon_integration_test"


def _base_database_url() -> str:
    return os.environ["DATABASE_URL"]


def _test_database_url() -> str:
    return _base_database_url().rsplit("/", 1)[0] + f"/{TEST_DB_NAME}"


def _asyncpg_url(database: str = "postgres") -> str:
    return _base_database_url().replace("postgresql+asyncpg://", "postgresql://").rsplit("/", 1)[0] + f"/{database}"


async def _reset_test_database() -> None:
    conn = await asyncpg.connect(_asyncpg_url())
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


async def _drop_test_database() -> None:
    conn = await asyncpg.connect(_asyncpg_url())
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
    finally:
        await conn.close()


def _run_migrations(database_url: str) -> None:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


@pytest.fixture()
def migrated_database_url():
    asyncio.run(_reset_test_database())
    database_url = _test_database_url()
    _run_migrations(database_url)
    try:
        yield database_url
    finally:
        asyncio.run(_drop_test_database())


async def _seed_booking_graph(session, start: datetime, staff: Staff | None = None) -> tuple[User, Service, Staff, Booking]:
    user = User(
        name=f"Customer {uuid.uuid4()}",
        email=f"{uuid.uuid4()}@example.com",
        hashed_password=get_password_hash("password123"),
    )
    service = Service(
        name=f"Service {uuid.uuid4()}",
        description=None,
        duration_minutes=30,
        price=Decimal("25.00"),
    )
    staff = staff or Staff(name=f"Staff {uuid.uuid4()}", display_order=0)
    booking = Booking(
        user=user,
        service=service,
        staff=staff,
        start_time=start,
        end_time=start + timedelta(minutes=30),
    )
    session.add_all([user, service, staff, booking])
    await session.commit()
    return user, service, staff, booking


async def test_same_staff_overlapping_confirmed_bookings_are_rejected(migrated_database_url):
    engine = create_async_engine(migrated_database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    start = datetime.now(timezone.utc) + timedelta(days=7)

    async with Session() as session:
        _, service, staff, _ = await _seed_booking_graph(session, start)
        second_user = User(
            name="Second Customer",
            email=f"{uuid.uuid4()}@example.com",
            hashed_password=get_password_hash("password123"),
        )
        session.add(
            Booking(
                user=second_user,
                service=service,
                staff=staff,
                start_time=start + timedelta(minutes=10),
                end_time=start + timedelta(minutes=40),
            )
        )

        with pytest.raises(IntegrityError):
            await session.commit()

    await engine.dispose()


async def test_different_staff_overlapping_confirmed_bookings_are_allowed(migrated_database_url):
    engine = create_async_engine(migrated_database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    start = datetime.now(timezone.utc) + timedelta(days=7)

    async with Session() as session:
        _, service, _, _ = await _seed_booking_graph(session, start)
        second_staff = Staff(name="Second Staff", display_order=1)
        second_user = User(
            name="Second Customer",
            email=f"{uuid.uuid4()}@example.com",
            hashed_password=get_password_hash("password123"),
        )
        session.add(
            Booking(
                user=second_user,
                service=service,
                staff=second_staff,
                start_time=start + timedelta(minutes=10),
                end_time=start + timedelta(minutes=40),
            )
        )
        await session.commit()

    await engine.dispose()
