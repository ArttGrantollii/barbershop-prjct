"""Add 'no_show' to bookingstatus enum and reminder_sent_at column

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-08

PostgreSQL 12+ allows ALTER TYPE ... ADD VALUE inside a transaction (the new
value just can't be used until the transaction commits). The bookings.reminder_sent_at
column is purely additive and nullable so existing rows pass without backfill.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend the enum. IF NOT EXISTS makes the migration safely re-runnable
    # — needed because Postgres rejects re-adding an existing enum value.
    op.execute("ALTER TYPE bookingstatus ADD VALUE IF NOT EXISTS 'no_show'")

    # Track when (and whether) the 24h reminder fired so the worker is
    # idempotent — sending twice is a worse outcome than missing one.
    op.add_column(
        "bookings",
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bookings", "reminder_sent_at")
    # Postgres has no DROP VALUE for enums — recreating the type would
    # require rewriting every booking row. Leave 'no_show' in place; rolling
    # back the schema doesn't require removing already-stored enum values.
