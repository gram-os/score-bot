"""add usage_events table

Revision ID: i1j2k3l4m5n6
Revises: h0i1j2k3l4m5
Create Date: 2026-04-23

"""

import sqlalchemy as sa
from alembic import op

revision = "i1j2k3l4m5n6"
down_revision = "h0i1j2k3l4m5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_usage_events_event_type", "usage_events", ["event_type"])
    op.create_index("ix_usage_events_timestamp", "usage_events", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_usage_events_timestamp", "usage_events")
    op.drop_index("ix_usage_events_event_type", "usage_events")
    op.drop_table("usage_events")
