import inspect

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import availability, bookings
from app.core.dependencies import get_current_verified_customer


async def test_verified_customer_dependency_accepts_verified_customer(mock_user):
    mock_user.is_email_verified = True

    assert await get_current_verified_customer(mock_user) is mock_user


async def test_verified_customer_dependency_rejects_unverified_customer(mock_user):
    mock_user.is_email_verified = False

    with pytest.raises(HTTPException) as exc:
        await get_current_verified_customer(mock_user)

    assert exc.value.status_code == 403
    assert "verify your email" in exc.value.detail


def test_booking_creation_routes_require_verified_customer():
    assert inspect.signature(bookings.book).parameters["current_user"].default.dependency is get_current_verified_customer
    assert inspect.signature(bookings.reschedule).parameters["current_user"].default.dependency is get_current_verified_customer
    assert inspect.signature(availability.hold).parameters["current_user"].default.dependency is get_current_verified_customer
