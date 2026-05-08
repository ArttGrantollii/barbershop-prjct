"""Tests for availability_service.py — covers slot calculation logic."""
import uuid
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.availability_service import get_slots

MODULE = "app.services.availability_service"


def _make_hours(open_h: int = 9, close_h: int = 18, is_closed: bool = False) -> MagicMock:
    hours = MagicMock()
    hours.open_time = time(open_h, 0)
    hours.close_time = time(close_h, 0)
    hours.is_closed = is_closed
    return hours


def _make_service(duration_minutes: int = 60) -> MagicMock:
    svc = MagicMock()
    svc.id = uuid.uuid4()
    svc.duration_minutes = duration_minutes
    return svc


def _make_staff() -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.name = "Main Chair"
    s.is_active = True
    s.display_order = 0
    return s


def _patch_staff_repo(MockStaffRepo, staff: MagicMock) -> None:
    """Configure StaffRepository so get_slots finds `staff` for any service."""
    MockStaffRepo.return_value.get_active_for_service = AsyncMock(return_value=[staff])


class TestGetSlots:
    async def test_blocked_date_returns_empty(self, mock_db, mock_redis):
        target = date(2026, 6, 15)

        with patch(f"{MODULE}.BusinessRepository") as MockBizRepo:
            MockBizRepo.return_value.is_date_blocked = AsyncMock(return_value=True)

            result = await get_slots(mock_db, mock_redis, _make_service(), target)

        assert result == []

    async def test_closed_day_returns_empty(self, mock_db, mock_redis):
        target = date(2026, 6, 15)

        with patch(f"{MODULE}.BusinessRepository") as MockBizRepo:
            MockBizRepo.return_value.is_date_blocked = AsyncMock(return_value=False)
            MockBizRepo.return_value.get_hours_for_day = AsyncMock(
                return_value=_make_hours(is_closed=True)
            )

            result = await get_slots(mock_db, mock_redis, _make_service(), target)

        assert result == []

    async def test_no_hours_configured_returns_empty(self, mock_db, mock_redis):
        target = date(2026, 6, 15)

        with patch(f"{MODULE}.BusinessRepository") as MockBizRepo:
            MockBizRepo.return_value.is_date_blocked = AsyncMock(return_value=False)
            MockBizRepo.return_value.get_hours_for_day = AsyncMock(return_value=None)

            result = await get_slots(mock_db, mock_redis, _make_service(), target)

        assert result == []

    async def test_correct_number_of_slots_generated(self, mock_db, mock_redis):
        """9 AM–6 PM with 60-min slots → 9 slots."""
        # Use tomorrow so all slots are in the future.
        target = (datetime.now(timezone.utc) + timedelta(days=1)).date()
        service = _make_service(duration_minutes=60)

        with (
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            _patch_staff_repo(MockStaffRepo, _make_staff())
            MockBizRepo.return_value.is_date_blocked = AsyncMock(return_value=False)
            MockBizRepo.return_value.get_hours_for_day = AsyncMock(
                return_value=_make_hours(open_h=9, close_h=18)
            )
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)
            mock_redis.get.return_value = None

            result = await get_slots(mock_db, mock_redis, service, target)

        assert len(result) == 9
        assert all(s["status"] == "available" for s in result)

    async def test_past_slots_are_excluded(self, mock_db, mock_redis):
        """Slots before now must not appear, even on today's date."""
        target = datetime.now(timezone.utc).date()
        service = _make_service(duration_minutes=60)

        with (
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            _patch_staff_repo(MockStaffRepo, _make_staff())
            MockBizRepo.return_value.is_date_blocked = AsyncMock(return_value=False)
            MockBizRepo.return_value.get_hours_for_day = AsyncMock(
                return_value=_make_hours(open_h=0, close_h=23)
            )
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)
            mock_redis.get.return_value = None

            result = await get_slots(mock_db, mock_redis, service, target)

        now = datetime.now(timezone.utc)
        for slot in result:
            assert slot["start_time"] > now, "Past slot leaked into results"

    async def test_redis_held_slots_marked_as_held(self, mock_db, mock_redis):
        target = (datetime.now(timezone.utc) + timedelta(days=1)).date()
        service = _make_service(duration_minutes=60)

        # All Redis lookups return a holder → all slots are "held".
        mock_redis.get.return_value = str(uuid.uuid4())

        with (
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            _patch_staff_repo(MockStaffRepo, _make_staff())
            MockBizRepo.return_value.is_date_blocked = AsyncMock(return_value=False)
            MockBizRepo.return_value.get_hours_for_day = AsyncMock(
                return_value=_make_hours(open_h=9, close_h=18)
            )

            result = await get_slots(mock_db, mock_redis, service, target)

        assert len(result) == 9
        assert all(s["status"] == "held" for s in result)

    async def test_booked_slots_marked_as_booked(self, mock_db, mock_redis):
        target = (datetime.now(timezone.utc) + timedelta(days=1)).date()
        service = _make_service(duration_minutes=60)
        mock_redis.get.return_value = None  # No Redis holds

        with (
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            _patch_staff_repo(MockStaffRepo, _make_staff())
            MockBizRepo.return_value.is_date_blocked = AsyncMock(return_value=False)
            MockBizRepo.return_value.get_hours_for_day = AsyncMock(
                return_value=_make_hours(open_h=9, close_h=18)
            )
            # All slots overlap with an existing booking.
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=True)

            result = await get_slots(mock_db, mock_redis, service, target)

        assert len(result) == 9
        assert all(s["status"] == "booked" for s in result)

    async def test_mixed_slot_statuses(self, mock_db, mock_redis):
        """First slot held in Redis, second booked in DB, rest available."""
        target = (datetime.now(timezone.utc) + timedelta(days=1)).date()
        service = _make_service(duration_minutes=60)

        call_count = 0

        async def redis_get_side_effect(key: str) -> str | None:
            nonlocal call_count
            call_count += 1
            return "some-user-id" if call_count == 1 else None

        mock_redis.get.side_effect = redis_get_side_effect

        db_call_count = 0

        async def has_overlap_side_effect(*_args, **_kwargs) -> bool:
            nonlocal db_call_count
            db_call_count += 1
            return db_call_count == 1  # First DB check → booked

        with (
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            _patch_staff_repo(MockStaffRepo, _make_staff())
            MockBizRepo.return_value.is_date_blocked = AsyncMock(return_value=False)
            MockBizRepo.return_value.get_hours_for_day = AsyncMock(
                return_value=_make_hours(open_h=9, close_h=18)
            )
            MockBookingRepo.return_value.has_overlap = AsyncMock(
                side_effect=has_overlap_side_effect
            )

            result = await get_slots(mock_db, mock_redis, service, target)

        statuses = [s["status"] for s in result]
        assert statuses[0] == "held"
        assert statuses[1] == "booked"
        assert all(s == "available" for s in statuses[2:])

    async def test_slot_end_times_are_correct(self, mock_db, mock_redis):
        target = (datetime.now(timezone.utc) + timedelta(days=1)).date()
        service = _make_service(duration_minutes=30)
        mock_redis.get.return_value = None

        with (
            patch(f"{MODULE}.BusinessRepository") as MockBizRepo,
            patch(f"{MODULE}.BookingRepository") as MockBookingRepo,
            patch(f"{MODULE}.StaffRepository") as MockStaffRepo,
        ):
            _patch_staff_repo(MockStaffRepo, _make_staff())
            MockBizRepo.return_value.is_date_blocked = AsyncMock(return_value=False)
            MockBizRepo.return_value.get_hours_for_day = AsyncMock(
                return_value=_make_hours(open_h=9, close_h=11)
            )
            MockBookingRepo.return_value.has_overlap = AsyncMock(return_value=False)

            result = await get_slots(mock_db, mock_redis, service, target)

        # 9:00–11:00 with 30-min slots → 4 slots
        assert len(result) == 4
        for slot in result:
            delta = slot["end_time"] - slot["start_time"]
            assert delta == timedelta(minutes=30)
