import logging

from app.notifications.schemas import AccountActionInfo, BookingInfo

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


def send_booking_reminder(info: BookingInfo) -> None:
    when = info.start_time.strftime("%Y-%m-%d %H:%M")
    logger.info(
        "[EMAIL] Reminder: appointment tomorrow | to=%s | booking=%s | service=%s | time=%s",
        info.customer_email,
        info.booking_id,
        info.service_name,
        when,
    )
    if info.customer_phone:
        logger.info(
            "[SMS] Reminder: appointment tomorrow | to=%s | booking=%s | time=%s",
            info.customer_phone,
            info.booking_id,
            when,
        )


def send_email_verification(info: AccountActionInfo) -> None:
    logger.info(
        "[EMAIL] Verify account | to=%s | expires=%sm | url=%s",
        info.customer_email,
        info.expires_minutes,
        info.action_url,
    )


def send_password_reset(info: AccountActionInfo) -> None:
    logger.info(
        "[EMAIL] Password reset | to=%s | expires=%sm | url=%s",
        info.customer_email,
        info.expires_minutes,
        info.action_url,
    )
