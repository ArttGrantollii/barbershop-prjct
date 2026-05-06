"""Shared fixtures for booking and availability tests."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models.booking import Booking, BookingStatus
from app.db.models.service import Service
from app.db.models.user import User, UserRole


@pytest.fixture
def mock_db() -> AsyncMock:
    session = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    redis.delete.return_value = 1
    redis.exists.return_value = 0
    redis.setex.return_value = True
    return redis


@pytest.fixture
def service_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_service(service_id: uuid.UUID) -> MagicMock:
    svc = MagicMock(spec=Service)
    svc.id = service_id
    svc.name = "Haircut"
    svc.duration_minutes = 30
    svc.price = Decimal("25.00")
    svc.is_active = True
    return svc


@pytest.fixture
def mock_user(user_id: uuid.UUID) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = user_id
    user.name = "Test User"
    user.email = "test@example.com"
    user.phone = "1234567890"
    user.role = UserRole.CUSTOMER
    user.is_active = True
    return user


@pytest.fixture
def future_start() -> datetime:
    """A start time safely in the future."""
    from datetime import timedelta
    return datetime.now(timezone.utc) + timedelta(hours=2)


@pytest.fixture
def mock_booking(user_id: uuid.UUID, service_id: uuid.UUID, future_start: datetime) -> MagicMock:
    from datetime import timedelta
    booking = MagicMock(spec=Booking)
    booking.id = uuid.uuid4()
    booking.user_id = user_id
    booking.service_id = service_id
    booking.start_time = future_start
    booking.end_time = future_start + timedelta(minutes=30)
    booking.status = BookingStatus.CONFIRMED
    booking.notes = None
    booking.cancellation_reason = None
    return booking
