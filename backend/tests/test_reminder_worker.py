"""Tests for the 24h reminder worker.

These mock AsyncSessionLocal to avoid a live DB. The worker's contract is
narrow: claim due bookings with `reminder_attempted_at`, send, then set
`reminder_sent_at` only on successful delivery.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.reminders import send_due_reminders

MODULE = "app.workers.reminders"


def _booking_mock(start_in_hours: float = 24, reminder_sent_at=None) -> MagicMock:
    """Construct a minimally-populated Booking mock."""
    b = MagicMock()
    b.id = uuid.uuid4()
    b.start_time = datetime.now(timezone.utc) + timedelta(hours=start_in_hours)
    b.end_time = b.start_time + timedelta(minutes=30)
    b.reminder_attempted_at = None
    b.reminder_sent_at = reminder_sent_at
    b.reminder_error = None
    b.user = MagicMock()
    b.user.name = "Test"
    b.user.email = "test@example.com"
    b.user.phone = None
    b.customer_name = "Guest"
    b.customer_email = "guest@example.com"
    b.customer_phone = None
    b.service = MagicMock()
    b.service.name = "Haircut"
    b.service.duration_minutes = 30
    return b


@pytest.fixture
def mock_session_factory():
    """Patch the worker's AsyncSessionLocal so each call yields a mock session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)
    with patch(f"{MODULE}.AsyncSessionLocal", factory):
        yield session


class TestSendDueReminders:
    async def test_sends_for_due_bookings_and_marks_reminder_sent_at(self, mock_session_factory):
        bookings = [_booking_mock(start_in_hours=24), _booking_mock(start_in_hours=24)]
        scalars = MagicMock()
        scalars.all.return_value = bookings
        result = MagicMock()
        result.scalars.return_value = scalars
        mock_session_factory.execute = AsyncMock(return_value=result)

        with patch(f"{MODULE}.notify_booking_reminder", new_callable=AsyncMock, return_value=True) as notify:
            sent = await send_due_reminders()

        assert sent == 2
        assert notify.await_count == 2
        for booking in bookings:
            assert booking.reminder_attempted_at is not None
            assert booking.reminder_sent_at is not None
            assert booking.reminder_error is None
        assert mock_session_factory.commit.await_count == 2

    async def test_no_due_bookings_is_a_noop(self, mock_session_factory):
        scalars = MagicMock()
        scalars.all.return_value = []
        result = MagicMock()
        result.scalars.return_value = scalars
        mock_session_factory.execute = AsyncMock(return_value=result)

        with patch(f"{MODULE}.notify_booking_reminder", new_callable=AsyncMock) as notify:
            sent = await send_due_reminders()

        assert sent == 0
        notify.assert_not_called()
        mock_session_factory.commit.assert_not_called()

    async def test_send_exception_marks_attempt_but_not_sent(self, mock_session_factory):
        booking = _booking_mock()
        scalars = MagicMock()
        scalars.all.return_value = [booking]
        result = MagicMock()
        result.scalars.return_value = scalars
        mock_session_factory.execute = AsyncMock(return_value=result)

        with patch(
            f"{MODULE}.notify_booking_reminder",
            new_callable=AsyncMock,
            side_effect=RuntimeError("ses down"),
        ):
            sent = await send_due_reminders()

        assert sent == 0
        assert booking.reminder_attempted_at is not None
        assert booking.reminder_sent_at is None
        assert "ses down" in booking.reminder_error
        assert mock_session_factory.commit.await_count == 2

    async def test_backend_false_marks_attempt_but_not_sent(self, mock_session_factory):
        booking = _booking_mock()
        scalars = MagicMock()
        scalars.all.return_value = [booking]
        result = MagicMock()
        result.scalars.return_value = scalars
        mock_session_factory.execute = AsyncMock(return_value=result)

        with patch(f"{MODULE}.notify_booking_reminder", new_callable=AsyncMock, return_value=False):
            sent = await send_due_reminders()

        assert sent == 0
        assert booking.reminder_attempted_at is not None
        assert booking.reminder_sent_at is None
        assert booking.reminder_error == "notification backend returned failure"
        assert mock_session_factory.commit.await_count == 2

    async def test_skips_booking_with_missing_relations(self, mock_session_factory):
        booking = _booking_mock()
        booking.user = None
        booking.customer_name = None
        booking.customer_email = None
        scalars = MagicMock()
        scalars.all.return_value = [booking]
        result = MagicMock()
        result.scalars.return_value = scalars
        mock_session_factory.execute = AsyncMock(return_value=result)

        with patch(f"{MODULE}.notify_booking_reminder", new_callable=AsyncMock) as notify:
            sent = await send_due_reminders()

        assert sent == 0
        notify.assert_not_called()
        assert booking.reminder_attempted_at is not None
        assert booking.reminder_sent_at is None
        assert booking.reminder_error == "missing customer or service relation"
        assert mock_session_factory.commit.await_count == 2

    async def test_sends_guest_booking_reminder_from_snapshot(self, mock_session_factory):
        booking = _booking_mock()
        booking.user = None
        scalars = MagicMock()
        scalars.all.return_value = [booking]
        result = MagicMock()
        result.scalars.return_value = scalars
        mock_session_factory.execute = AsyncMock(return_value=result)

        with patch(f"{MODULE}.notify_booking_reminder", new_callable=AsyncMock, return_value=True) as notify:
            sent = await send_due_reminders()

        assert sent == 1
        payload = notify.await_args.args[0]
        assert payload.customer_name == "Guest"
        assert payload.customer_email == "guest@example.com"
        assert booking.reminder_sent_at is not None
