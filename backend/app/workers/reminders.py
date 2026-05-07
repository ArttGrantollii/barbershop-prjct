"""Background worker that fires the 24h-before booking reminder.

Design notes:

- Runs in-process inside the FastAPI event loop (started/stopped via the app
  lifespan). For a single uvicorn worker this is the simplest reliable
  setup; for a multi-worker deployment, switch to a dedicated worker
  process or take a DB / Redis lock here so only one instance does the work.

- "Already reminded" is tracked on the booking row (`reminder_sent_at`).
  The worker claims due rows by setting that column and committing *before*
  attempting to send — so a process crash between commit and send loses a
  reminder rather than producing duplicates. Customers losing one reminder
  is preferable to spamming them.

- The match window is `[now + lead - tol, now + lead + tol]`. With a 5min
  tick interval and a 60min tolerance, a booking gets exactly one chance to
  match before its window closes — but the tolerance gives plenty of room
  for clock skew and missed ticks.
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
    """Run one pass of the reminder loop. Returns the number of reminders sent."""
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
            )
        )
        bookings = list(result.scalars().all())
        if not bookings:
            return 0

        # Claim everyone in one commit so a re-entry of this loop (or a second
        # worker, if someone runs more than one) cannot pick them up.
        for b in bookings:
            b.reminder_sent_at = now
        await db.commit()

        sent = 0
        for booking in bookings:
            if not booking.user or not booking.service:
                # User or service rows missing — nothing useful to send.
                logger.warning("reminder_skipped_missing_relation", booking_id=str(booking.id))
                continue
            try:
                await notify_booking_reminder(
                    BookingInfo(
                        booking_id=str(booking.id),
                        customer_name=booking.user.name,
                        customer_email=booking.user.email,
                        customer_phone=booking.user.phone,
                        service_name=booking.service.name,
                        start_time=_utc(booking.start_time),
                        end_time=_utc(booking.end_time),
                        duration_minutes=booking.service.duration_minutes,
                    )
                )
                sent += 1
                logger.info("reminder_sent", booking_id=str(booking.id))
            except Exception:
                # We've already marked the row as sent; don't re-attempt.
                # Log so an on-call engineer can investigate persistent failures.
                logger.exception("reminder_send_failed", booking_id=str(booking.id))
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
    reminders are disabled — keeping the call site clean of the conditional."""
    if not settings.REMINDERS_ENABLED:
        logger.info("reminder_loop_disabled")
        return None
    return asyncio.create_task(reminder_loop(), name="reminder_loop")
