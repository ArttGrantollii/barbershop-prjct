"""Focused tests for admin dashboard aggregation endpoint."""
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.api.v1.endpoints.admin import dashboard
from app.db.models.booking import BookingStatus

MODULE = "app.api.v1.endpoints.admin"


async def test_dashboard_returns_backend_aggregates(mock_db, mock_user, mock_booking):
    mock_booking.service = None
    mock_booking.user = None
    mock_booking.staff = None

    with patch(f"{MODULE}.BookingRepository") as MockBookingRepo:
        repo = MockBookingRepo.return_value
        repo.get_between_with_details = AsyncMock(return_value=[mock_booking])
        repo.revenue_between = AsyncMock(return_value=Decimal("25.00"))
        repo.count_between = AsyncMock(return_value=7)
        repo.count_all = AsyncMock(side_effect=[42, 5])

        result = await dashboard(db=mock_db, _=mock_user)

    assert result.today_bookings_count == 1
    assert result.today_revenue == Decimal("25.00")
    assert result.week_bookings_count == 7
    assert result.confirmed_total == 42
    assert result.cancelled_total == 5
    assert len(result.today_schedule) == 1
    assert result.today_schedule[0].id == mock_booking.id
    assert result.today_schedule[0].service is None
    assert result.today_schedule[0].user is None
    assert result.today_schedule[0].staff is None

    repo.get_between_with_details.assert_awaited_once()
    repo.revenue_between.assert_awaited_once()
    repo.count_between.assert_awaited_once()
    repo.count_all.assert_any_await(status=BookingStatus.CONFIRMED)
    repo.count_all.assert_any_await(status=BookingStatus.CANCELLED)
