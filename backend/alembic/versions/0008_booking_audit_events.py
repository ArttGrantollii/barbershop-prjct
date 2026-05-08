"""Booking audit events

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "booking_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "actor_role",
            sa.Enum("customer", "admin", "system", name="auditactorrole"),
            nullable=False,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("previous_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_booking_audit_events_booking_id", "booking_audit_events", ["booking_id"])
    op.create_index("ix_booking_audit_events_actor_id", "booking_audit_events", ["actor_id"])
    op.create_index("ix_booking_audit_events_action", "booking_audit_events", ["action"])


def downgrade() -> None:
    op.drop_index("ix_booking_audit_events_action", table_name="booking_audit_events")
    op.drop_index("ix_booking_audit_events_actor_id", table_name="booking_audit_events")
    op.drop_index("ix_booking_audit_events_booking_id", table_name="booking_audit_events")
    op.drop_table("booking_audit_events")
    op.execute("DROP TYPE IF EXISTS auditactorrole")
