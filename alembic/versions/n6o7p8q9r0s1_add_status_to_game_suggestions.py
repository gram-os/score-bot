"""add status to game_suggestions

Revision ID: n6o7p8q9r0s1
Revises: m5n6o7p8q9r0
Create Date: 2026-04-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "n6o7p8q9r0s1"
down_revision: Union[str, None] = "m5n6o7p8q9r0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "game_suggestions",
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
    )
    op.execute(
        "UPDATE game_suggestions SET status = 'polled' WHERE poll_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("game_suggestions", "status")
