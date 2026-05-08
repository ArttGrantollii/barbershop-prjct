"""Background worker that fires the 24h-before booking reminder.

Design notes:

- Runs in-process inside the FastAPI event loop (started/stopped via the app
  lifespan). Due rows are selected with `FOR UPDATE SKIP LOCKED`, so parallel
  workers do not claim the same reminder rows.

- Reminder attempts and successful sends are tracked separately. The worker
  claims due rows by setting `reminder_attempted_at` and committing before it
  attempts to send. It sets `reminder_sent_at` only after the notification
  backend reports success. Failed attempts are visible via `reminder_error`
  instead of being mislabeled as sent.

- The match window is `[now + lead - tol, now + lead + tol]`. With a 5min
  tick interval and a 60min tolerance, a booking gets exactly one chance to
  match before its window closes, but the tolerance gives room for clock skew
  and missed ticks.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models.booking import Booking, BookingStatus
from app.db.session import AsyncSessionLocal
from app.notifications.schemas import BookingInfo
from app.notifications.service import notify_booking_reminder

logger = structlog.get_logger(__name__)


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def send_due_reminders() -> int:
    """Run one pass of the reminder loop. Returns successfully sent reminders."""
    now = datetime.now(timezone.utc)
    lead = timedelta(hours=settings.REMINDER_LEAD_HOURS)
    tol = timedelta(minutes=settings.REMINDER_TOLERANCE_MINUTES)
    window_start = now + lead - tol
    window_end = now + lead + tol

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking)
            .options(selectinload(Booking.user), selectinload(Booking.service))
            .where(
                Booking.status == BookingStatus.CONFIRMED,
                Booking.start_time >= window_start,
                Booking.start_time <= window_end,
                Booking.reminder_sent_at.is_(None),
                Booking.reminder_attempted_at.is_(None),
            )
            .with_for_update(skip_locked=True)
        )
        bookings = list(result.scalars().all())
        if not bookings:
            return 0

        # Claim everyone in one commit while row locks are held. This marks an
        # attempt, not successful delivery.
        for booking in bookings:
            booking.reminder_attempted_at = now
            booking.reminder_error = None
        await db.commit()

        sent = 0
        for booking in bookings:
            customer_name = booking.user.name if booking.user else booking.customer_name
            customer_email = booking.user.email if booking.user else booking.customer_email
            customer_phone = booking.user.phone if booking.user else booking.customer_phone
            if not booking.service or not customer_name or not customer_email:
                booking.reminder_error = "missing customer or service relation"
                logger.warning("reminder_skipped_missing_relation", booking_id=str(booking.id))
                continue
            try:
                delivered = await notify_booking_reminder(
                    BookingInfo(
                        booking_id=str(booking.id),
                        customer_name=customer_name,
                        customer_email=customer_email,
                        customer_phone=customer_phone,
                        service_name=booking.service.name,
                        start_time=_utc(booking.start_time),
                        end_time=_utc(booking.end_time),
                        duration_minutes=booking.service.duration_minutes,
                    )
                )
                if not delivered:
                    booking.reminder_error = "notification backend returned failure"
                    logger.warning("reminder_send_failed", booking_id=str(booking.id))
                    continue
                booking.reminder_sent_at = datetime.now(timezone.utc)
                booking.reminder_error = None
                sent += 1
                logger.info("reminder_sent", booking_id=str(booking.id))
            except Exception as exc:
                booking.reminder_error = str(exc) or exc.__class__.__name__
                logger.exception("reminder_send_failed", booking_id=str(booking.id))
        await db.commit()
        return sent


async def reminder_loop() -> None:
    """Forever-loop wrapper. Catches per-iteration errors so a transient DB
    blip doesn't kill the worker for the lifetime of the process."""
    interval = settings.REMINDER_INTERVAL_SECONDS
    logger.info("reminder_loop_started", interval_seconds=interval)
    while True:
        try:
            count = await send_due_reminders()
            if count:
                logger.info("reminder_pass_complete", sent=count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("reminder_loop_iteration_failed")
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise


def start_reminder_loop() -> asyncio.Task | None:
    """Schedule the reminder loop on the running event loop. Returns the task
    so the lifespan handler can cancel it on shutdown. Returns None if
    reminders are disabled, keeping the call site clean of the conditional."""
    if not settings.REMINDERS_ENABLED:
        logger.info("reminder_loop_disabled")
        return None
    return asyncio.create_task(reminder_loop(), name="reminder_loop")
