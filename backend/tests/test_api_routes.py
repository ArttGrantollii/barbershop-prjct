import uuid
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.api.v1.endpoints import admin, auth, availability, bookings
from app.core.dependencies import (
    get_current_active_user,
    get_current_admin,
    get_current_customer,
    get_current_verified_customer,
)
from app.db.models.booking import AuditActorRole, BookingStatus, WaitlistStatus
from app.db.models.user import UserRole
from app.db.redis import get_redis
from app.db.session import get_db
from app.main import app


def _user(*, role: UserRole = UserRole.CUSTOMER, verified: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="Route Tester",
        email=f"{uuid.uuid4()}@example.com",
        phone="1234567890",
        hashed_password="hashed",
        role=role,
        is_active=True,
        is_email_verified=verified,
        created_at=datetime.now(timezone.utc),
    )


def _service(service_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=service_id or uuid.uuid4(),
        name="Haircut",
        duration_minutes=30,
        price="25.00",
    )


def _staff(staff_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=staff_id or uuid.uuid4(), name="Main Chair", photo_url=None)


def _booking(
    *,
    booking_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    service_id: uuid.UUID | None = None,
    staff_id: uuid.UUID | None = None,
    status: BookingStatus = BookingStatus.CONFIRMED,
) -> SimpleNamespace:
    sid = service_id or uuid.uuid4()
    stid = staff_id or uuid.uuid4()
    start = datetime.now(timezone.utc) + timedelta(days=2)
    return SimpleNamespace(
        id=booking_id or uuid.uuid4(),
        user_id=user_id,
        service_id=sid,
        staff_id=stid,
        customer_name="Route Tester",
        customer_email="route@example.com",
        customer_phone="1234567890",
        start_time=start,
        end_time=start + timedelta(minutes=30),
        status=status,
        notes="quiet chair",
        cancellation_reason=None,
        created_at=datetime.now(timezone.utc),
        service=_service(sid),
        user=None,
        staff=_staff(stid),
    )


def _waitlist_entry(
    *,
    entry_id: uuid.UUID | None = None,
    service_id: uuid.UUID | None = None,
    staff_id: uuid.UUID | None = None,
    booking_id: uuid.UUID | None = None,
    status: WaitlistStatus = WaitlistStatus.ACTIVE,
) -> SimpleNamespace:
    sid = service_id or uuid.uuid4()
    stid = staff_id or uuid.uuid4()
    return SimpleNamespace(
        id=entry_id or uuid.uuid4(),
        user_id=None,
        service_id=sid,
        staff_id=stid,
        booking_id=booking_id,
        customer_name="Wait List",
        customer_email="wait@example.com",
        customer_phone="1234567890",
        preferred_date=datetime.now(timezone.utc).date(),
        notes="first opening",
        status=status,
        created_at=datetime.now(timezone.utc),
        service=_service(sid),
        user=None,
        staff=_staff(stid),
    )


@pytest.fixture
def route_state():
    db = AsyncMock()
    redis = AsyncMock()
    customer = _user()
    admin_user = _user(role=UserRole.ADMIN)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_current_active_user] = lambda: customer
    app.dependency_overrides[get_current_customer] = lambda: customer
    app.dependency_overrides[get_current_verified_customer] = lambda: customer
    app.dependency_overrides[get_current_admin] = lambda: admin_user
    try:
        yield SimpleNamespace(db=db, redis=redis, customer=customer, admin=admin_user)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def client(route_state):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestAuthRoutes:
    async def test_register_route_creates_user_and_sends_verification(self, client):
        created = _user(verified=False)
        with (
            patch.object(auth, "UserRepository") as MockRepo,
            patch.object(auth, "get_password_hash", return_value="hashed") as hash_password,
            patch.object(auth, "send_email_verification", new_callable=AsyncMock) as send_verification,
        ):
            MockRepo.return_value.get_by_email = AsyncMock(return_value=None)
            MockRepo.return_value.create = AsyncMock(return_value=created)

            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "name": created.name,
                    "email": created.email,
                    "phone": created.phone,
                    "password": "Password123",
                },
            )

        assert response.status_code == 201
        assert response.json()["email"] == created.email
        hash_password.assert_called_once_with("Password123")
        send_verification.assert_awaited_once()

    async def test_login_route_returns_rotating_tokens(self, client):
        existing = _user()
        with (
            patch.object(auth, "UserRepository") as MockRepo,
            patch.object(auth, "verify_password", return_value=True),
            patch.object(auth, "create_access_token", return_value="access-token"),
            patch.object(auth, "create_refresh_token", return_value="refresh-token"),
        ):
            MockRepo.return_value.get_by_email = AsyncMock(return_value=existing)

            response = await client.post(
                "/api/v1/auth/login",
                data={"username": existing.email, "password": "Password123"},
            )

        assert response.status_code == 200
        assert response.json() == {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
        }

    async def test_refresh_route_blacklists_consumed_refresh_token(self, client, route_state):
        existing = _user()
        exp = int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp())
        with (
            patch.object(auth, "decode_token", return_value={
                "type": "refresh",
                "jti": "old-refresh-jti",
                "sub": str(existing.id),
                "exp": exp,
            }),
            patch.object(auth, "is_token_blacklisted", new_callable=AsyncMock, return_value=False),
            patch.object(auth, "blacklist_token", new_callable=AsyncMock) as blacklist,
            patch.object(auth, "UserRepository") as MockRepo,
            patch.object(auth, "create_access_token", return_value="new-access"),
            patch.object(auth, "create_refresh_token", return_value="new-refresh"),
        ):
            MockRepo.return_value.get_by_id = AsyncMock(return_value=existing)

            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "old-refresh"},
            )

        assert response.status_code == 200
        assert response.json()["access_token"] == "new-access"
        blacklist.assert_awaited_once()

    async def test_logout_route_revokes_access_and_refresh_tokens(self, client):
        exp = int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp())
        with (
            patch.object(auth, "decode_token", side_effect=[
                {"type": "access", "jti": "access-jti", "exp": exp},
                {"type": "refresh", "jti": "refresh-jti", "sub": str(uuid.uuid4()), "exp": exp},
            ]),
            patch.object(auth, "blacklist_token", new_callable=AsyncMock) as blacklist,
        ):
            response = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": "Bearer access"},
                json={"refresh_token": "refresh"},
            )

        assert response.status_code == 204
        assert blacklist.await_count == 2


class TestCustomerBookingRoutes:
    async def test_hold_route_calls_booking_hold_service(self, client, route_state):
        service_id = uuid.uuid4()
        staff_id = uuid.uuid4()
        start = datetime.now(timezone.utc) + timedelta(days=2)
        with patch.object(availability, "hold_slot", new_callable=AsyncMock, return_value={
            "start_time": start,
            "end_time": start + timedelta(minutes=30),
            "staff_id": staff_id,
            "expires_in_seconds": 600,
        }) as hold_slot:
            response = await client.post(
                "/api/v1/availability/hold",
                json={"service_id": str(service_id), "start_time": start.isoformat(), "staff_id": str(staff_id)},
            )

        assert response.status_code == 200
        hold_slot.assert_awaited_once()
        assert response.json()["staff_id"] == str(staff_id)

    async def test_booking_route_calls_create_booking_service(self, client, route_state):
        service_id = uuid.uuid4()
        staff_id = uuid.uuid4()
        created = _booking(user_id=route_state.customer.id, service_id=service_id, staff_id=staff_id)
        with patch.object(bookings, "create_booking", new_callable=AsyncMock, return_value=created) as create_booking:
            response = await client.post(
                "/api/v1/bookings",
                json={
                    "service_id": str(service_id),
                    "staff_id": str(staff_id),
                    "start_time": created.start_time.isoformat(),
                    "notes": "quiet chair",
                },
            )

        assert response.status_code == 201
        assert response.json()["id"] == str(created.id)
        create_booking.assert_awaited_once()

    async def test_cancel_route_calls_cancel_service(self, client, route_state):
        cancelled = _booking(user_id=route_state.customer.id, status=BookingStatus.CANCELLED)
        with patch.object(bookings, "cancel_booking", new_callable=AsyncMock, return_value=cancelled) as cancel_booking:
            response = await client.post(
                f"/api/v1/bookings/{cancelled.id}/cancel",
                json={"reason": "plans changed"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        cancel_booking.assert_awaited_once()

    async def test_reschedule_route_calls_reschedule_service(self, client, route_state):
        moved = _booking(user_id=route_state.customer.id)
        new_start = datetime.now(timezone.utc) + timedelta(days=3)
        with patch.object(bookings, "reschedule_booking", new_callable=AsyncMock, return_value=moved) as reschedule:
            response = await client.post(
                f"/api/v1/bookings/{moved.id}/reschedule",
                json={"start_time": new_start.isoformat(), "staff_id": str(moved.staff_id)},
            )

        assert response.status_code == 200
        assert response.json()["id"] == str(moved.id)
        reschedule.assert_awaited_once()


class TestAdminRoutes:
    async def test_admin_rejects_invalid_service_update_values(self, client):
        service_id = uuid.uuid4()

        duration_response = await client.put(
            f"/api/v1/admin/services/{service_id}",
            json={"duration_minutes": 0},
        )
        price_response = await client.put(
            f"/api/v1/admin/services/{service_id}",
            json={"price": -1},
        )

        assert duration_response.status_code == 422
        assert price_response.status_code == 422

    async def test_admin_rejects_invalid_business_hours_range(self, client):
        current = SimpleNamespace(
            id=uuid.uuid4(),
            day_of_week=0,
            open_time=time(9, 0),
            close_time=time(17, 0),
            is_closed=False,
        )
        with patch.object(admin, "BusinessRepository") as MockBusiness:
            MockBusiness.return_value.get_hours_for_day = AsyncMock(return_value=current)

            response = await client.put(
                "/api/v1/admin/business-hours/0",
                json={"open_time": "17:00", "close_time": "09:00", "is_closed": False},
            )

        assert response.status_code == 400
        assert "close_time" in response.json()["detail"]

    async def test_admin_rejects_blocked_date_with_confirmed_bookings(self, client):
        blocked_date = date(2026, 5, 20)
        with (
            patch.object(admin, "BookingRepository") as MockBookings,
            patch.object(admin, "BusinessRepository") as MockBusiness,
        ):
            MockBookings.return_value.get_for_date = AsyncMock(return_value=[_booking()])

            response = await client.post(
                "/api/v1/admin/blocked-dates",
                json={"date": blocked_date.isoformat(), "reason": "Holiday"},
            )

        assert response.status_code == 409
        assert "confirmed booking" in response.json()["detail"]
        MockBusiness.return_value.create_blocked_date.assert_not_called()

    async def test_admin_create_booking_route_calls_admin_service(self, client, route_state):
        service_id = uuid.uuid4()
        staff_id = uuid.uuid4()
        created = _booking(service_id=service_id, staff_id=staff_id)
        with patch.object(admin, "create_admin_booking", new_callable=AsyncMock, return_value=created) as create_admin_booking:
            response = await client.post(
                "/api/v1/admin/bookings",
                json={
                    "service_id": str(service_id),
                    "staff_id": str(staff_id),
                    "start_time": created.start_time.isoformat(),
                    "status": "confirmed",
                    "customer_name": "Walk In",
                },
            )

        assert response.status_code == 201
        assert response.json()["id"] == str(created.id)
        create_admin_booking.assert_awaited_once()

    async def test_admin_can_read_booking_audit_history(self, client):
        booking = _booking()
        event = SimpleNamespace(
            id=uuid.uuid4(),
            booking_id=booking.id,
            actor_id=uuid.uuid4(),
            actor_role=AuditActorRole.ADMIN,
            action="created",
            previous_values=None,
            new_values={"status": "confirmed"},
            created_at=datetime.now(timezone.utc),
        )
        with (
            patch.object(admin, "BookingRepository") as MockBookings,
            patch.object(admin, "BookingAuditRepository") as MockAudit,
        ):
            MockBookings.return_value.get_by_id = AsyncMock(return_value=booking)
            MockAudit.return_value.get_for_booking = AsyncMock(return_value=[event])

            response = await client.get(f"/api/v1/admin/bookings/{booking.id}/audit-events")

        assert response.status_code == 200
        assert response.json()[0]["action"] == "created"

    async def test_admin_can_convert_waitlist_entry_to_booking(self, client, route_state):
        entry = _waitlist_entry()
        booking = _booking(service_id=entry.service_id, staff_id=entry.staff_id)
        booked_entry = _waitlist_entry(
            entry_id=entry.id,
            service_id=entry.service_id,
            staff_id=entry.staff_id,
            booking_id=booking.id,
            status=WaitlistStatus.BOOKED,
        )
        with (
            patch.object(admin, "WaitlistRepository") as MockWaitlist,
            patch.object(admin, "create_admin_booking", new_callable=AsyncMock, return_value=booking),
            patch.object(admin, "record_booking_audit", new_callable=AsyncMock),
        ):
            repo = MockWaitlist.return_value
            repo.get_by_id = AsyncMock(return_value=entry)
            repo.update_status = AsyncMock(return_value=booked_entry)
            repo.get_with_details = AsyncMock(return_value=booked_entry)

            response = await client.post(
                f"/api/v1/admin/waitlist/{entry.id}/book",
                json={"start_time": booking.start_time.isoformat(), "staff_id": str(entry.staff_id)},
            )

        assert response.status_code == 200
        assert response.json()["waitlist_entry"]["status"] == "booked"
        assert response.json()["booking"]["id"] == str(booking.id)
