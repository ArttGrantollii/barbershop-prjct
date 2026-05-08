import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.booking import AuditActorRole
from app.db.repositories.booking_audit_repository import BookingAuditRepository

logger = structlog.get_logger(__name__)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


async def record_booking_audit(
    db: AsyncSession,
    *,
    booking_id: uuid.UUID,
    action: str,
    actor_role: AuditActorRole,
    actor_id: uuid.UUID | None = None,
    previous_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
) -> None:
    await BookingAuditRepository(db).create_event(
        booking_id=booking_id,
        action=action,
        actor_role=actor_role,
        actor_id=actor_id,
        previous_values=_jsonable(previous_values) if previous_values is not None else None,
        new_values=_jsonable(new_values) if new_values is not None else None,
    )
    logger.info(
        "booking_audit_recorded",
        booking_id=str(booking_id),
        action=action,
        actor_role=actor_role.value,
        actor_id=str(actor_id) if actor_id else None,
    )
