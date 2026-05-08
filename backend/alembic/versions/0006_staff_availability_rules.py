"""Staff-specific availability rules

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staff_working_hours",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=False),
        sa.Column("close_time", sa.Time(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("staff_id", "day_of_week", name="uq_staff_working_hours_staff_day"),
    )
    op.create_index("ix_staff_working_hours_staff_id", "staff_working_hours", ["staff_id"])

    op.create_table(
        "staff_blocked_times",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("end_time > start_time", name="ck_staff_blocked_times_valid_range"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_blocked_times_staff_id", "staff_blocked_times", ["staff_id"])
    op.create_index("ix_staff_blocked_times_start_time", "staff_blocked_times", ["start_time"])
    op.create_index("ix_staff_blocked_times_end_time", "staff_blocked_times", ["end_time"])


def downgrade() -> None:
    op.drop_index("ix_staff_blocked_times_end_time", table_name="staff_blocked_times")
    op.drop_index("ix_staff_blocked_times_start_time", table_name="staff_blocked_times")
    op.drop_index("ix_staff_blocked_times_staff_id", table_name="staff_blocked_times")
    op.drop_table("staff_blocked_times")
    op.drop_index("ix_staff_working_hours_staff_id", table_name="staff_working_hours")
    op.drop_table("staff_working_hours")
