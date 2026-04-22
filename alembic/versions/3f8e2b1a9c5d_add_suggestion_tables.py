"""add suggestion tables

Revision ID: 3f8e2b1a9c5d
Revises: eb1a7c45644e
Create Date: 2026-04-21 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "3f8e2b1a9c5d"
down_revision: Union[str, None] = "eb1a7c45644e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_polls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("is_yes_no", sa.Boolean(), nullable=False),
        sa.Column("notified", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "game_suggestions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("game_name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("suggested_at", sa.DateTime(), nullable=False),
        sa.Column("poll_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["poll_id"], ["daily_polls.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("game_suggestions")
    op.drop_table("daily_polls")
