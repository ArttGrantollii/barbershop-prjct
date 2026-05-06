import logging

from app.notifications.schemas import BookingInfo

logger = logging.getLogger(__name__)


def send_booking_confirmed(info: BookingInfo) -> None:
    logger.info(
        "[EMAIL] Booking confirmed | to=%s | booking=%s | service=%s | time=%s",
        info.customer_email,
        info.booking_id,
        info.service_name,
        info.start_time.strftime("%Y-%m-%d %H:%M"),
    )
    if info.customer_phone:
        logger.info(
            "[SMS] Booking confirmed | to=%s | booking=%s | time=%s",
            info.customer_phone,
            info.booking_id,
            info.start_time.strftime("%Y-%m-%d %H:%M"),
        )


def send_booking_cancelled(info: BookingInfo) -> None:
    logger.info(
        "[EMAIL] Booking cancelled | to=%s | booking=%s | reason=%s",
        info.customer_email,
        info.booking_id,
        info.cancellation_reason or "—",
    )
    if info.customer_phone:
        logger.info(
            "[SMS] Booking cancelled | to=%s | booking=%s",
            info.customer_phone,
            info.booking_id,
        )
