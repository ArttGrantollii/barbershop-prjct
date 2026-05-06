"""booking overlap exclusion constraint

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-07

Adds a PostgreSQL exclusion constraint that makes overlapping *confirmed*
bookings impossible at the database level, closing the check-then-insert race
condition that application-level overlap checks cannot fully prevent.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # btree_gist is required to build a GiST index over the tstzrange type
    # alongside the equality operator on the status column.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # EXCLUDE USING gist prevents any two CONFIRMED bookings whose time ranges
    # overlap (&&).  The half-open interval '[)' means end_time of one booking
    # may equal start_time of the next — back-to-back bookings are allowed.
    op.execute("""
        ALTER TABLE bookings
        ADD CONSTRAINT no_overlapping_confirmed_bookings
        EXCLUDE USING gist (
            tstzrange(start_time, end_time, '[)') WITH &&
        ) WHERE (status = 'confirmed')
    """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE bookings DROP CONSTRAINT IF EXISTS no_overlapping_confirmed_bookings"
    )
