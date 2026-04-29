"""Add monthly_rank_snapshots table

Revision ID: t2u3v4w5x6y7
Revises: s1t2u3v4w5x6
Create Date: 2026-04-29

"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision = "t2u3v4w5x6y7"
down_revision: Union[str, None] = "s1t2u3v4w5x6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monthly_rank_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("submission_count", sa.Integer(), nullable=False),
        sa.Column("player_count", sa.Integer(), nullable=False),
        sa.Column("snapshotted_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "year", "month"),
    )


def downgrade() -> None:
    op.drop_table("monthly_rank_snapshots")
