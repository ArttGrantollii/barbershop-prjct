"""Track reminder attempts separately from successful sends

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-08

`reminder_sent_at` now means the notification provider accepted the send.
`reminder_attempted_at` records that the worker claimed and tried the reminder,
and `reminder_error` stores why it did not become a successful send.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("reminder_attempted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("bookings", sa.Column("reminder_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "reminder_error")
    op.drop_column("bookings", "reminder_attempted_at")
