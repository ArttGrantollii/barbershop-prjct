import boto3

from app.core.config import settings
from app.notifications.schemas import BookingInfo


def _ses_client():
    return boto3.client(
        "ses",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def _sns_client():
    return boto3.client(
        "sns",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def _send_email(to: str, subject: str, html: str, text: str) -> None:
    _ses_client().send_email(
        Source=settings.AWS_SES_FROM_EMAIL,
        Destination={"ToAddresses": [to]},
        Message={
            "Subject": {"Data": subject},
            "Body": {
                "Html": {"Data": html},
                "Text": {"Data": text},
            },
        },
    )


def _send_sms(phone: str, message: str) -> None:
    _sns_client().publish(PhoneNumber=phone, Message=message)


def send_booking_confirmed(info: BookingInfo) -> None:
    date_str = info.start_time.strftime("%A, %B %-d at %-I:%M %p")
    subject = f"Your appointment at Vendos Salon is confirmed"
    html = f"""
    <h2>Booking Confirmed</h2>
    <p>Hi {info.customer_name},</p>
    <p>Your appointment has been confirmed:</p>
    <ul>
      <li><strong>Service:</strong> {info.service_name}</li>
      <li><strong>Date &amp; Time:</strong> {date_str}</li>
      <li><strong>Duration:</strong> {info.duration_minutes} minutes</li>
      <li><strong>Booking ID:</strong> {info.booking_id}</li>
    </ul>
    <p>To cancel, please do so at least 2 hours before your appointment.</p>
    <p>See you soon!<br>Vendos Salon</p>
    """
    text = (
        f"Booking confirmed at Vendos Salon.\n"
        f"Service: {info.service_name}\n"
        f"Time: {date_str}\n"
        f"Booking ID: {info.booking_id}"
    )
    _send_email(info.customer_email, subject, html, text)

    if info.customer_phone:
        _send_sms(
            info.customer_phone,
            f"Vendos Salon: Booking confirmed for {info.service_name} on {date_str}. ID: {info.booking_id}",
        )


def send_booking_reminder(info: BookingInfo) -> None:
    date_str = info.start_time.strftime("%A, %B %-d at %-I:%M %p")
    subject = f"Reminder: your Vendos Salon appointment tomorrow"
    html = f"""
    <h2>Your appointment is tomorrow</h2>
    <p>Hi {info.customer_name},</p>
    <p>This is a friendly reminder that you have an appointment booked:</p>
    <ul>
      <li><strong>Service:</strong> {info.service_name}</li>
      <li><strong>Date &amp; Time:</strong> {date_str}</li>
      <li><strong>Duration:</strong> {info.duration_minutes} minutes</li>
      <li><strong>Booking ID:</strong> {info.booking_id}</li>
    </ul>
    <p>If you need to reschedule or cancel, please do so at least 2 hours in advance.</p>
    <p>See you soon!<br>Vendos Salon</p>
    """
    text = (
        f"Reminder: Vendos Salon appointment tomorrow.\n"
        f"Service: {info.service_name}\n"
        f"Time: {date_str}\n"
        f"Booking ID: {info.booking_id}"
    )
    _send_email(info.customer_email, subject, html, text)

    if info.customer_phone:
        _send_sms(
            info.customer_phone,
            f"Vendos Salon reminder: {info.service_name} tomorrow on {date_str}.",
        )


def send_booking_cancelled(info: BookingInfo) -> None:
    subject = "Your Vendos Salon appointment has been cancelled"
    reason_line = f"<p><strong>Reason:</strong> {info.cancellation_reason}</p>" if info.cancellation_reason else ""
    html = f"""
    <h2>Booking Cancelled</h2>
    <p>Hi {info.customer_name},</p>
    <p>Your appointment (ID: {info.booking_id}) for <strong>{info.service_name}</strong> has been cancelled.</p>
    {reason_line}
    <p>You can book a new appointment at any time.</p>
    <p>Vendos Salon</p>
    """
    text = (
        f"Your Vendos Salon appointment ({info.booking_id}) for {info.service_name} has been cancelled."
    )
    _send_email(info.customer_email, subject, html, text)

    if info.customer_phone:
        _send_sms(
            info.customer_phone,
            f"Vendos Salon: Your appointment ({info.booking_id}) has been cancelled.",
        )
