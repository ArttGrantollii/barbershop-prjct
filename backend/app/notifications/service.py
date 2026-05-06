import asyncio
import logging

from app.core.config import settings
from app.notifications.schemas import BookingInfo

logger = logging.getLogger(__name__)


async def notify_booking_confirmed(info: BookingInfo) -> None:
    try:
        if settings.NOTIFICATIONS_BACKEND == "aws":
            from app.notifications import aws
            await asyncio.to_thread(aws.send_booking_confirmed, info)
        else:
            from app.notifications import console
            console.send_booking_confirmed(info)
    except Exception:
        logger.exception("Failed to send booking-confirmed notification for %s", info.booking_id)


async def notify_booking_cancelled(info: BookingInfo) -> None:
    try:
        if settings.NOTIFICATIONS_BACKEND == "aws":
            from app.notifications import aws
            await asyncio.to_thread(aws.send_booking_cancelled, info)
        else:
            from app.notifications import console
            console.send_booking_cancelled(info)
    except Exception:
        logger.exception("Failed to send booking-cancelled notification for %s", info.booking_id)
