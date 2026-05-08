import asyncio
import logging

from app.core.config import settings
from app.notifications.schemas import BookingInfo

logger = logging.getLogger(__name__)


async def notify_booking_confirmed(info: BookingInfo) -> bool:
    try:
        if settings.NOTIFICATIONS_BACKEND == "aws":
            from app.notifications import aws
            await asyncio.to_thread(aws.send_booking_confirmed, info)
        else:
            from app.notifications import console
            console.send_booking_confirmed(info)
        return True
    except Exception:
        logger.exception("Failed to send booking-confirmed notification for %s", info.booking_id)
        return False


async def notify_booking_cancelled(info: BookingInfo) -> bool:
    try:
        if settings.NOTIFICATIONS_BACKEND == "aws":
            from app.notifications import aws
            await asyncio.to_thread(aws.send_booking_cancelled, info)
        else:
            from app.notifications import console
            console.send_booking_cancelled(info)
        return True
    except Exception:
        logger.exception("Failed to send booking-cancelled notification for %s", info.booking_id)
        return False


async def notify_booking_reminder(info: BookingInfo) -> bool:
    try:
        if settings.NOTIFICATIONS_BACKEND == "aws":
            from app.notifications import aws
            await asyncio.to_thread(aws.send_booking_reminder, info)
        else:
            from app.notifications import console
            console.send_booking_reminder(info)
        return True
    except Exception:
        logger.exception("Failed to send booking-reminder notification for %s", info.booking_id)
        return False
