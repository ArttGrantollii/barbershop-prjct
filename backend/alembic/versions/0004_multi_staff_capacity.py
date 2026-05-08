"""Multi-staff capacity model

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-08

Adds the staff capacity dimension. Until now, the booking model was implicitly
single-chair: one confirmed booking blocked the entire shop for that time.
After this migration, capacity is per-staff — N stylists can each take a
booking at the same time as long as they're not the same person.

The migration is constructed to be safe on existing data:

  1. Create the new tables with `staff` empty.
  2. Insert one "Main Chair" staff row so the salon's existing bookings have
     a valid owner. Picking a single backfill target is intentional — it
     preserves today's behavior identically (one stylist = one chair).
  3. Add bookings.staff_id as nullable, backfill it to the new staff row,
     then enforce NOT NULL. Doing this in three steps lets the column land
     even if the table is huge — no full-table rewrite under a write lock.
  4. Link every existing service to the new staff via service_staff so
     bookings can continue to be created without an explicit staff choice.
  5. Replace the old global EXCLUDE constraint with a staff-scoped one. The
     new constraint is satisfied by the backfilled data because every
     existing pair of overlapping confirmed bookings was already rejected
     by the old constraint, and they all now share the same staff_id.

Downgrade restores the original global constraint and drops the new tables.
Existing bookings keep their start/end times; the staff dimension is dropped.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New tables ---------------------------------------------------------
    op.create_table(
        "staff",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "service_staff",
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("service_id", "staff_id"),
    )

    # 2. Default staff ------------------------------------------------------
    # gen_random_uuid() is built into PG 13+ and the docker stack is on PG 16.
    op.execute(
        """
        INSERT INTO staff (id, name, display_order)
        VALUES (gen_random_uuid(), 'Main Chair', 0)
        """
    )

    # 3. bookings.staff_id (nullable -> backfill -> NOT NULL) ---------------
    op.add_column("bookings", sa.Column("staff_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        UPDATE bookings
        SET staff_id = (SELECT id FROM staff ORDER BY display_order, created_at LIMIT 1)
        WHERE staff_id IS NULL
        """
    )
    op.alter_column("bookings", "staff_id", nullable=False)
    op.create_foreign_key(
        "fk_bookings_staff_id",
        "bookings",
        "staff",
        ["staff_id"],
        ["id"],
    )
    op.create_index("ix_bookings_staff_id", "bookings", ["staff_id"])

    # 4. Link every existing service to the default staff -------------------
    op.execute(
        """
        INSERT INTO service_staff (service_id, staff_id)
        SELECT s.id, (SELECT id FROM staff ORDER BY display_order, created_at LIMIT 1)
        FROM services s
        ON CONFLICT DO NOTHING
        """
    )

    # 5. Replace the EXCLUDE constraint with a staff-scoped version ---------
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS no_overlapping_confirmed_bookings")
    op.execute(
        """
        ALTER TABLE bookings
        ADD CONSTRAINT no_overlapping_confirmed_bookings
        EXCLUDE USING gist (
            staff_id WITH =,
            tstzrange(start_time, end_time, '[)') WITH &&
        ) WHERE (status = 'confirmed')
        """
    )


def downgrade() -> None:
    # Reverse-order teardown so foreign keys never reference dropped tables.
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS no_overlapping_confirmed_bookings")
    op.execute(
        """
        ALTER TABLE bookings
        ADD CONSTRAINT no_overlapping_confirmed_bookings
        EXCLUDE USING gist (
            tstzrange(start_time, end_time, '[)') WITH &&
        ) WHERE (status = 'confirmed')
        """
    )
    op.drop_index("ix_bookings_staff_id", table_name="bookings")
    op.drop_constraint("fk_bookings_staff_id", "bookings", type_="foreignkey")
    op.drop_column("bookings", "staff_id")
    op.drop_table("service_staff")
    op.drop_table("staff")
