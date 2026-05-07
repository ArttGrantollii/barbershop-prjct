"""Tests for booking_service.py — covers the critical booking lifecycle paths."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.db.models.booking import BookingStatus
from app.services.booking_service import cancel_booking, create_booking, hold_slot

MODULE = "app.services.booking_service"


# ---------------------------------------------------------------------------
# hold_slot
# ---------------------------------------------------------------------------

class TestHoldSlot:
    async def test_success(self, mock_db, mock_redis, mock_service, user_id, future_start):
        mock_redis.set.return_value = True  # SET NX succeeded

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.manager") as mock_manager,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)
            mock_manager.broadcast = AsyncMock()

            result = await hold_slot(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert "start_time" in result
        assert "expires_in_seconds" in result
        mock_redis.set.assert_called_once()
        # Verify SET NX flag is used
        call_kwargs = mock_redis.set.call_args.kwargs
        assert call_kwargs.get("nx") is True

    async def test_slot_already_booked_in_db(self, mock_db, mock_redis, mock_service, user_id, future_start):
        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=True)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)

            with pytest.raises(HTTPException) as exc:
                await hold_slot(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409
        assert "booked" in exc.value.detail

    async def test_slot_already_held_in_redis(self, mock_db, mock_redis, mock_service, user_id, future_start):
        mock_redis.set.return_value = None  # SET NX failed — key already exists

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)

            with pytest.raises(HTTPException) as exc:
                await hold_slot(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409
        assert "held" in exc.value.detail

    async def test_blocks_when_user_already_has_booking_today(
        self, mock_db, mock_redis, mock_service, user_id, future_start
    ):
        """The same-day single-booking rule fires at hold time, not just at confirm."""
        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=1)

            with pytest.raises(HTTPException) as exc:
                await hold_slot(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409
        assert "already have a booking" in exc.value.detail

    async def test_service_not_found(self, mock_db, mock_redis, user_id, future_start):
        with patch(f"{MODULE}.ServiceRepository") as MockSvcRepo:
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc:
                await hold_slot(mock_db, mock_redis, user_id, uuid.uuid4(), future_start)

        assert exc.value.status_code == 404

    async def test_inactive_service_rejected(self, mock_db, mock_redis, mock_service, user_id, future_start):
        mock_service.is_active = False

        with patch(f"{MODULE}.ServiceRepository") as MockSvcRepo:
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)

            with pytest.raises(HTTPException) as exc:
                await hold_slot(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# create_booking
# ---------------------------------------------------------------------------

def _mock_business_repo_clear(MockBizRepo) -> None:
    """Sensible defaults: no blocked dates, no booking conflicts."""
    MockBizRepo.return_value.is_date_blocked = AsyncMock(return_value=False)


def _mock_booking_repo_clear(MockBookingRepo) -> None:
    """Sensible defaults: user has no other bookings today, slot is free."""
    MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)
    MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)


class TestCreateBooking:
    async def test_success(
        self, mock_db, mock_redis, mock_service, mock_user, mock_booking, user_id, future_start
    ):
        mock_redis.get.return_value = None  # No hold on slot

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.UserRepository") as MockUserRepo,
            patch(f"{MODULE}.manager") as mock_manager,
            patch(f"{MODULE}.notify_booking_confirmed") as mock_notify,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            MockBookingRepo.return_value.create_booking = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.get_with_details = AsyncMock(return_value=mock_booking)
            MockUserRepo.return_value.get_by_id = AsyncMock(return_value=mock_user)
            mock_manager.broadcast = AsyncMock()
            mock_notify.return_value = None

            result = await create_booking(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert result is mock_booking
        MockBookingRepo.return_value.create_booking.assert_awaited_once()

    async def test_slot_held_by_another_user(
        self, mock_db, mock_redis, mock_service, user_id, future_start
    ):
        other_user_id = uuid.uuid4()

        async def redis_get(key: str) -> str | None:
            return str(other_user_id) if key.startswith("slot_hold:") else None

        mock_redis.get.side_effect = redis_get

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)

            with pytest.raises(HTTPException) as exc:
                await create_booking(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409
        assert "another user" in exc.value.detail

    async def test_overlap_detected_before_insert(
        self, mock_db, mock_redis, mock_service, user_id, future_start
    ):
        mock_redis.get.return_value = None

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=True)

            with pytest.raises(HTTPException) as exc:
                await create_booking(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409

    async def test_db_exclusion_constraint_triggers_409(
        self, mock_db, mock_redis, mock_service, user_id, future_start
    ):
        """Concurrent booking slips past the overlap check but is caught by the
        DB exclusion constraint — IntegrityError must become a 409."""
        mock_redis.get.return_value = None

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            MockBookingRepo.return_value.create_booking = AsyncMock(
                side_effect=IntegrityError("INSERT", {}, Exception("exclusion constraint"))
            )

            with pytest.raises(HTTPException) as exc:
                await create_booking(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409
        mock_db.rollback.assert_awaited_once()

    async def test_blocks_when_user_already_has_booking_today(
        self, mock_db, mock_redis, mock_service, user_id, future_start
    ):
        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=1)

            with pytest.raises(HTTPException) as exc:
                await create_booking(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409
        assert "already have a booking" in exc.value.detail

    async def test_blocks_when_date_is_blocked(
        self, mock_db, mock_redis, mock_service, user_id, future_start
    ):
        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            MockBizRepo.return_value.is_date_blocked = AsyncMock(return_value=True)
            _mock_booking_repo_clear(MockBookingRepo)

            with pytest.raises(HTTPException) as exc:
                await create_booking(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409
        assert "not available" in exc.value.detail

    async def test_own_held_slot_is_accepted(
        self, mock_db, mock_redis, mock_service, mock_user, mock_booking, user_id, future_start
    ):
        """The user who holds the slot should be able to confirm it."""
        async def redis_get(key: str) -> str | None:
            return str(user_id) if key.startswith("slot_hold:") else None

        mock_redis.get.side_effect = redis_get

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.UserRepository") as MockUserRepo,
            patch(f"{MODULE}.manager") as mock_manager,
            patch(f"{MODULE}.notify_booking_confirmed"),
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            MockBookingRepo.return_value.create_booking = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.get_with_details = AsyncMock(return_value=mock_booking)
            MockUserRepo.return_value.get_by_id = AsyncMock(return_value=mock_user)
            mock_manager.broadcast = AsyncMock()

            result = await create_booking(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert result is mock_booking


# ---------------------------------------------------------------------------
# cancel_booking
# ---------------------------------------------------------------------------

class TestCancelBooking:
    async def test_success(self, mock_db, mock_redis, mock_booking, user_id):
        # Push start_time well past the 2h cancellation window — the future_start
        # fixture sits exactly on the boundary, which is racy under any latency.
        mock_booking.start_time = datetime.now(timezone.utc) + timedelta(hours=4)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with (
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.UserRepository") as MockUserRepo,
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.manager") as mock_manager,
            patch(f"{MODULE}.notify_booking_cancelled"),
        ):
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.get_with_details = AsyncMock(return_value=mock_booking)
            MockUserRepo.return_value.get_by_id = AsyncMock(return_value=None)
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=None)
            mock_manager.broadcast = AsyncMock()

            await cancel_booking(mock_db, mock_redis, mock_booking.id, user_id)

        assert mock_booking.status == BookingStatus.CANCELLED
        mock_db.commit.assert_awaited_once()

    async def test_not_owners_booking_raises_403(self, mock_db, mock_redis, mock_booking):
        other_user = uuid.uuid4()

        with patch(f"{MODULE}.BookingRepository") as MockBookingRepo:
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)

            with pytest.raises(HTTPException) as exc:
                await cancel_booking(mock_db, mock_redis, mock_booking.id, other_user)

        assert exc.value.status_code == 403

    async def test_already_cancelled_raises_400(self, mock_db, mock_redis, mock_booking, user_id):
        mock_booking.status = BookingStatus.CANCELLED

        with patch(f"{MODULE}.BookingRepository") as MockBookingRepo:
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)

            with pytest.raises(HTTPException) as exc:
                await cancel_booking(mock_db, mock_redis, mock_booking.id, user_id)

        assert exc.value.status_code == 400

    async def test_too_close_to_start_raises_400(self, mock_db, mock_redis, mock_booking, user_id):
        # Move the booking start to 30 minutes from now (inside the 2-hour window).
        mock_booking.start_time = datetime.now(timezone.utc) + timedelta(minutes=30)

        with patch(f"{MODULE}.BookingRepository") as MockBookingRepo:
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)

            with pytest.raises(HTTPException) as exc:
                await cancel_booking(mock_db, mock_redis, mock_booking.id, user_id)

        assert exc.value.status_code == 400
        assert "notice" in exc.value.detail

    async def test_admin_can_cancel_any_booking(self, mock_db, mock_redis, mock_booking):
        admin_id = uuid.uuid4()
        # Booking belongs to a different user but admin should still succeed.
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with (
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.UserRepository") as MockUserRepo,
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.manager") as mock_manager,
            patch(f"{MODULE}.notify_booking_cancelled"),
        ):
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.get_with_details = AsyncMock(return_value=mock_booking)
            MockUserRepo.return_value.get_by_id = AsyncMock(return_value=None)
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=None)
            mock_manager.broadcast = AsyncMock()

            await cancel_booking(mock_db, mock_redis, mock_booking.id, admin_id, is_admin=True)

        assert mock_booking.status == BookingStatus.CANCELLED

    async def test_booking_not_found_raises_404(self, mock_db, mock_redis, user_id):
        with patch(f"{MODULE}.BookingRepository") as MockBookingRepo:
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc:
                await cancel_booking(mock_db, mock_redis, uuid.uuid4(), user_id)

        assert exc.value.status_code == 404
