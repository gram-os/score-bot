"""add_homunculus_upgrade_table

Revision ID: l4m5n6o7p8q9
Revises: k3l4m5n6o7p8
Create Date: 2026-04-25

"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision = "l4m5n6o7p8q9"
down_revision: Union[str, None] = "k3l4m5n6o7p8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "homunculus_upgrades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("upgrade_text", sa.String(), nullable=False),
        sa.Column("vote_count", sa.Integer(), nullable=False),
        sa.Column("poll_question", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=False, unique=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("homunculus_upgrades")
