"""Guest bookings and waitlist entries

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("customer_name", sa.String(100), nullable=True))
    op.add_column("bookings", sa.Column("customer_email", sa.String(255), nullable=True))
    op.add_column("bookings", sa.Column("customer_phone", sa.String(20), nullable=True))
    op.execute(
        """
        UPDATE bookings b
        SET
            customer_name = u.name,
            customer_email = u.email,
            customer_phone = u.phone
        FROM users u
        WHERE b.user_id = u.id
        """
    )
    op.alter_column("bookings", "user_id", existing_type=sa.Uuid(), nullable=True)
    op.create_check_constraint(
        "ck_bookings_customer_identity",
        "bookings",
        "user_id IS NOT NULL OR customer_name IS NOT NULL",
    )

    op.create_table(
        "waitlist_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=True),
        sa.Column("booking_id", sa.Uuid(), nullable=True),
        sa.Column("customer_name", sa.String(100), nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("customer_phone", sa.String(20), nullable=True),
        sa.Column("preferred_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "booked", "cancelled", name="waitliststatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_waitlist_entries_user_id", "waitlist_entries", ["user_id"])
    op.create_index("ix_waitlist_entries_service_id", "waitlist_entries", ["service_id"])
    op.create_index("ix_waitlist_entries_staff_id", "waitlist_entries", ["staff_id"])
    op.create_index("ix_waitlist_entries_status", "waitlist_entries", ["status"])


def downgrade() -> None:
    op.drop_index("ix_waitlist_entries_status", table_name="waitlist_entries")
    op.drop_index("ix_waitlist_entries_staff_id", table_name="waitlist_entries")
    op.drop_index("ix_waitlist_entries_service_id", table_name="waitlist_entries")
    op.drop_index("ix_waitlist_entries_user_id", table_name="waitlist_entries")
    op.drop_table("waitlist_entries")
    op.execute("DROP TYPE IF EXISTS waitliststatus")
    op.drop_constraint("ck_bookings_customer_identity", "bookings", type_="check")
    op.alter_column("bookings", "user_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("bookings", "customer_phone")
    op.drop_column("bookings", "customer_email")
    op.drop_column("bookings", "customer_name")
