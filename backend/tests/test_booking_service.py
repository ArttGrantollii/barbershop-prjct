"""Tests for booking_service.py — covers the critical booking lifecycle paths."""
import uuid
from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.models.booking import BookingStatus
from app.services.booking_service import (
    cancel_booking,
    create_admin_booking,
    create_booking,
    hold_slot,
    reschedule_booking,
)

MODULE = "app.services.booking_service"


@pytest.fixture(autouse=True)
def mock_audit_recorder():
    with patch(f"{MODULE}.record_booking_audit", new_callable=AsyncMock) as recorder:
        yield recorder


# ---------------------------------------------------------------------------
# Mock helpers — module-level so every test class can use them
# ---------------------------------------------------------------------------

def _mock_business_repo_clear(MockBizRepo) -> None:
    """Sensible defaults: no blocked dates and wide working hours."""
    hours = MagicMock()
    hours.open_time = time(0, 0)
    hours.close_time = time(23, 59)
    hours.is_closed = False
    MockBizRepo.return_value.is_date_blocked = AsyncMock(return_value=False)
    MockBizRepo.return_value.get_hours_for_day = AsyncMock(return_value=hours)


def _mock_booking_repo_clear(MockBookingRepo) -> None:
    """Sensible defaults: user has no other bookings today, slot is free."""
    MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)
    MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)


def _mock_staff_repo_resolves_to(MockStaffRepo, staff) -> None:
    """Configure StaffRepository so the resolver finds `staff` and accepts
    any (staff, service) pair as valid."""
    MockStaffRepo.return_value.get_active_for_service = AsyncMock(return_value=[staff])
    MockStaffRepo.return_value.staff_offers_service = AsyncMock(return_value=True)
    MockStaffRepo.return_value.get_hours_for_day = AsyncMock(return_value=None)
    MockStaffRepo.return_value.has_blocked_overlap = AsyncMock(return_value=False)


# ---------------------------------------------------------------------------
# hold_slot
# ---------------------------------------------------------------------------

class TestHoldSlot:
    async def test_success(self, mock_db, mock_redis, mock_service, mock_staff, user_id, future_start):
        mock_redis.set.return_value = True  # SET NX succeeded

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
            patch(f"{MODULE}.manager") as mock_manager,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_staff)
            mock_manager.broadcast = AsyncMock()

            result = await hold_slot(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert "start_time" in result
        assert "expires_in_seconds" in result
        assert result["staff_id"] == mock_staff.id  # response now echoes the assignment
        assert any(call.kwargs.get("nx") is True for call in mock_redis.set.call_args_list)

    async def test_slot_already_booked_in_db(self, mock_db, mock_redis, mock_service, mock_staff, user_id, future_start):
        # Resolver walks staff and rejects each one whose has_overlap is True.
        # With one staff and overlap, resolver runs out of candidates.
        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=True)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_staff)

            with pytest.raises(HTTPException) as exc:
                await hold_slot(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409

    async def test_rejects_when_user_already_has_active_hold(
        self, mock_db, mock_redis, mock_service, user_id, future_start
    ):
        mock_redis.set.return_value = None

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)

            with pytest.raises(HTTPException) as exc:
                await hold_slot(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409
        assert "already have a slot on hold" in exc.value.detail

    async def test_slot_already_held_in_redis(self, mock_db, mock_redis, mock_service, mock_staff, user_id, future_start):
        mock_redis.set.side_effect = [True, None, None, None]

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_staff)

            with pytest.raises(HTTPException) as exc:
                await hold_slot(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409
        assert "held" in exc.value.detail

    async def test_rejects_when_staff_is_not_working(
        self, mock_db, mock_redis, mock_service, mock_staff, user_id, future_start
    ):
        mock_redis.set.return_value = True
        closed_hours = MagicMock()
        closed_hours.open_time = time(9, 0)
        closed_hours.close_time = time(17, 0)
        closed_hours.is_closed = True

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_staff)
            MockStaffRepo.return_value.get_hours_for_day = AsyncMock(return_value=closed_hours)

            with pytest.raises(HTTPException) as exc:
                await hold_slot(
                    mock_db,
                    mock_redis,
                    user_id,
                    mock_service.id,
                    future_start,
                    staff_id=mock_staff.id,
                )

        assert exc.value.status_code == 409
        assert "not working" in exc.value.detail

    async def test_blocks_when_user_already_has_booking_today(
        self, mock_db, mock_redis, mock_service, user_id, future_start
    ):
        """The same-day single-booking rule fires at hold time, not just at confirm."""
        # No StaffRepository mock needed — same-day check rejects before resolution.
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

    async def test_rejects_inside_lead_window(
        self, mock_db, mock_redis, mock_service, user_id, monkeypatch
    ):
        monkeypatch.setattr(settings, "MIN_LEAD_MINUTES", 60)
        near_future = datetime.now(timezone.utc) + timedelta(minutes=15)

        with pytest.raises(HTTPException) as exc:
            await hold_slot(mock_db, mock_redis, user_id, mock_service.id, near_future)

        assert exc.value.status_code == 400
        assert "60 minutes in advance" in exc.value.detail

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

class TestCreateBooking:
    async def test_success(
        self, mock_db, mock_redis, mock_service, mock_user, mock_booking, mock_staff, user_id, future_start,
        mock_audit_recorder
    ):
        mock_redis.get.return_value = None  # No hold on slot

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
            patch(f"{MODULE}.UserRepository") as MockUserRepo,
            patch(f"{MODULE}.manager") as mock_manager,
            patch(f"{MODULE}.notify_booking_confirmed") as mock_notify,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_staff)
            MockBookingRepo.return_value.create_booking = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.get_with_details = AsyncMock(return_value=mock_booking)
            MockUserRepo.return_value.get_by_id = AsyncMock(return_value=mock_user)
            mock_manager.broadcast = AsyncMock()
            mock_notify.return_value = None

            result = await create_booking(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert result is mock_booking
        MockBookingRepo.return_value.create_booking.assert_awaited_once()
        assert mock_audit_recorder.await_args.kwargs["action"] == "created"

    async def test_slot_held_by_another_user(
        self, mock_db, mock_redis, mock_service, mock_staff, user_id, future_start
    ):
        other_user_id = uuid.uuid4()

        async def redis_get(key: str) -> str | None:
            return str(other_user_id) if key.startswith("slot_hold:") else None

        mock_redis.get.side_effect = redis_get

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_staff)

            with pytest.raises(HTTPException) as exc:
                await create_booking(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409

    async def test_overlap_detected_before_insert(
        self, mock_db, mock_redis, mock_service, mock_staff, user_id, future_start
    ):
        mock_redis.get.return_value = None

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_staff)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=True)

            with pytest.raises(HTTPException) as exc:
                await create_booking(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert exc.value.status_code == 409

    async def test_db_exclusion_constraint_triggers_409(
        self, mock_db, mock_redis, mock_service, mock_staff, mock_user, user_id, future_start
    ):
        """Concurrent booking slips past the overlap check but is caught by the
        DB exclusion constraint — IntegrityError must become a 409."""
        mock_redis.get.return_value = None

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
            patch(f"{MODULE}.UserRepository") as MockUserRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_staff)
            MockUserRepo.return_value.get_by_id = AsyncMock(return_value=mock_user)
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

    async def test_rejects_inside_lead_window(self, mock_db, mock_redis, user_id, monkeypatch):
        monkeypatch.setattr(settings, "MIN_LEAD_MINUTES", 90)
        near_future = datetime.now(timezone.utc) + timedelta(minutes=30)

        with pytest.raises(HTTPException) as exc:
            await create_booking(mock_db, mock_redis, user_id, uuid.uuid4(), near_future)

        assert exc.value.status_code == 400
        assert "90 minutes in advance" in exc.value.detail

    async def test_rejects_past_start_time(self, mock_db, mock_redis, user_id):
        past = datetime.now(timezone.utc) - timedelta(minutes=5)

        with pytest.raises(HTTPException) as exc:
            await create_booking(mock_db, mock_redis, user_id, uuid.uuid4(), past)

        assert exc.value.status_code == 400
        assert "future" in exc.value.detail

    async def test_own_held_slot_is_accepted(
        self, mock_db, mock_redis, mock_service, mock_user, mock_booking, mock_staff, user_id, future_start
    ):
        """The user who holds the slot should be able to confirm it."""
        async def redis_get(key: str) -> str | None:
            return str(user_id) if key.startswith("slot_hold:") else None

        mock_redis.get.side_effect = redis_get

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
            patch(f"{MODULE}.UserRepository") as MockUserRepo,
            patch(f"{MODULE}.manager") as mock_manager,
            patch(f"{MODULE}.notify_booking_confirmed"),
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_staff)
            MockBookingRepo.return_value.create_booking = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.get_with_details = AsyncMock(return_value=mock_booking)
            MockUserRepo.return_value.get_by_id = AsyncMock(return_value=mock_user)
            mock_manager.broadcast = AsyncMock()

            result = await create_booking(mock_db, mock_redis, user_id, mock_service.id, future_start)

        assert result is mock_booking


# ---------------------------------------------------------------------------
# create_admin_booking
# ---------------------------------------------------------------------------

class TestCreateAdminBooking:
    async def test_guest_booking_uses_same_staff_rules(
        self, mock_db, mock_redis, mock_service, mock_booking, mock_staff, future_start, mock_audit_recorder
    ):
        mock_redis.get.return_value = None

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
            patch(f"{MODULE}.manager") as mock_manager,
            patch(f"{MODULE}.notify_booking_confirmed"),
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_staff)
            MockBookingRepo.return_value.create_booking = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.get_with_details = AsyncMock(return_value=mock_booking)
            mock_manager.broadcast = AsyncMock()

            result = await create_admin_booking(
                mock_db,
                mock_redis,
                uuid.uuid4(),
                mock_service.id,
                mock_staff.id,
                future_start,
                customer_name="Walk In",
                customer_phone="123",
            )

        assert result is mock_booking
        MockBookingRepo.return_value.create_booking.assert_awaited_once()
        kwargs = MockBookingRepo.return_value.create_booking.await_args.kwargs
        assert kwargs["user_id"] is None
        assert kwargs["customer_name"] == "Walk In"
        assert mock_audit_recorder.await_args.kwargs["action"] == "admin_created"

    async def test_guest_booking_rejects_overlap(
        self, mock_db, mock_redis, mock_service, mock_staff, future_start
    ):
        mock_redis.get.return_value = None

        with (
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_booking_repo_clear(MockBookingRepo)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_staff)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=True)

            with pytest.raises(HTTPException) as exc:
                await create_admin_booking(
                    mock_db,
                    mock_redis,
                    uuid.uuid4(),
                    mock_service.id,
                    mock_staff.id,
                    future_start,
                    customer_name="Walk In",
                )

        assert exc.value.status_code == 409


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


# ---------------------------------------------------------------------------
# reschedule_booking
# ---------------------------------------------------------------------------

class TestRescheduleBooking:
    async def test_success(self, mock_db, mock_redis, mock_booking, mock_service, mock_user, user_id):
        mock_booking.start_time = datetime.now(timezone.utc) + timedelta(hours=24)
        new_start = datetime.now(timezone.utc) + timedelta(hours=48)
        mock_db.commit = AsyncMock()

        with (
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
            patch(f"{MODULE}.UserRepository") as MockUserRepo,
            patch(f"{MODULE}.manager") as mock_manager,
            patch(f"{MODULE}.notify_booking_confirmed"),
        ):
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.get_with_details = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_booking.staff)
            MockUserRepo.return_value.get_by_id = AsyncMock(return_value=mock_user)
            mock_manager.broadcast = AsyncMock()

            result = await reschedule_booking(mock_db, mock_redis, mock_booking.id, user_id, new_start)

        assert result is mock_booking
        assert mock_booking.start_time == new_start
        mock_db.commit.assert_awaited_once()

    async def test_not_owners_booking_raises_404(self, mock_db, mock_redis, mock_booking):
        other_user = uuid.uuid4()
        new_start = datetime.now(timezone.utc) + timedelta(hours=48)

        with patch(f"{MODULE}.BookingRepository") as MockBookingRepo:
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)

            with pytest.raises(HTTPException) as exc:
                await reschedule_booking(mock_db, mock_redis, mock_booking.id, other_user, new_start)

        assert exc.value.status_code == 404

    async def test_cancelled_booking_cannot_reschedule(self, mock_db, mock_redis, mock_booking, user_id):
        mock_booking.status = BookingStatus.CANCELLED
        new_start = datetime.now(timezone.utc) + timedelta(hours=48)

        with patch(f"{MODULE}.BookingRepository") as MockBookingRepo:
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)

            with pytest.raises(HTTPException) as exc:
                await reschedule_booking(mock_db, mock_redis, mock_booking.id, user_id, new_start)

        assert exc.value.status_code == 400
        assert "cancelled" in exc.value.detail

    async def test_too_close_to_start_raises_400(self, mock_db, mock_redis, mock_booking, user_id):
        mock_booking.start_time = datetime.now(timezone.utc) + timedelta(minutes=30)
        new_start = datetime.now(timezone.utc) + timedelta(hours=48)

        with patch(f"{MODULE}.BookingRepository") as MockBookingRepo:
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)

            with pytest.raises(HTTPException) as exc:
                await reschedule_booking(mock_db, mock_redis, mock_booking.id, user_id, new_start)

        assert exc.value.status_code == 400
        assert "notice" in exc.value.detail

    async def test_overlap_detected_raises_409(self, mock_db, mock_redis, mock_booking, mock_service, user_id):
        mock_booking.start_time = datetime.now(timezone.utc) + timedelta(hours=24)
        new_start = datetime.now(timezone.utc) + timedelta(hours=48)

        with (
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=True)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_booking.staff)

            with pytest.raises(HTTPException) as exc:
                await reschedule_booking(mock_db, mock_redis, mock_booking.id, user_id, new_start)

        assert exc.value.status_code == 409
        assert "conflict" in exc.value.detail.lower()

    async def test_held_by_another_user_raises_409(self, mock_db, mock_redis, mock_booking, mock_service, user_id):
        mock_booking.start_time = datetime.now(timezone.utc) + timedelta(hours=24)
        new_start = datetime.now(timezone.utc) + timedelta(hours=48)
        other = uuid.uuid4()

        async def redis_get(key: str) -> str | None:
            return str(other) if key.startswith("slot_hold:") else None
        mock_redis.get.side_effect = redis_get

        with (
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_booking.staff)

            with pytest.raises(HTTPException) as exc:
                await reschedule_booking(mock_db, mock_redis, mock_booking.id, user_id, new_start)

        assert exc.value.status_code == 409
        assert "held" in exc.value.detail.lower()

    async def test_reschedule_to_other_staff_validates_service_offered(
        self, mock_db, mock_redis, mock_booking, mock_service, user_id
    ):
        """When the caller passes new_staff_id, the chosen stylist must
        actually offer this service — otherwise it's a 400."""
        mock_booking.start_time = datetime.now(timezone.utc) + timedelta(hours=24)
        new_start = datetime.now(timezone.utc) + timedelta(hours=48)
        new_staff = uuid.uuid4()

        with (
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            MockStaffRepo.return_value.staff_offers_service = AsyncMock(return_value=False)

            with pytest.raises(HTTPException) as exc:
                await reschedule_booking(
                    mock_db, mock_redis, mock_booking.id, user_id, new_start,
                    new_staff_id=new_staff,
                )

        assert exc.value.status_code == 400
        assert "does not offer" in exc.value.detail

    async def test_admin_can_reschedule_any_booking(self, mock_db, mock_redis, mock_booking, mock_service, mock_user):
        admin_id = uuid.uuid4()
        mock_booking.start_time = datetime.now(timezone.utc) + timedelta(minutes=30)  # admin bypasses notice
        new_start = datetime.now(timezone.utc) + timedelta(hours=48)
        mock_db.commit = AsyncMock()

        with (
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.ServiceRepository") as MockSvcRepo,
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
            patch(f"{MODULE}.UserRepository") as MockUserRepo,
            patch(f"{MODULE}.manager") as mock_manager,
            patch(f"{MODULE}.notify_booking_confirmed"),
        ):
            MockBookingRepo.return_value.get_by_id = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.get_with_details = AsyncMock(return_value=mock_booking)
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)
            MockBookingRepo.return_value.count_confirmed_for_user_on_date = AsyncMock(return_value=0)
            MockSvcRepo.return_value.get_by_id = AsyncMock(return_value=mock_service)
            _mock_business_repo_clear(MockBizRepo)
            _mock_staff_repo_resolves_to(MockStaffRepo, mock_booking.staff)
            MockUserRepo.return_value.get_by_id = AsyncMock(return_value=mock_user)
            mock_manager.broadcast = AsyncMock()

            await reschedule_booking(mock_db, mock_redis, mock_booking.id, admin_id, new_start, is_admin=True)

        assert mock_booking.start_time == new_start
