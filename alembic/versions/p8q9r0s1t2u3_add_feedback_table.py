"""add_feedback_table

Revision ID: p8q9r0s1t2u3
Revises: o7p8q9r0s1t2
Create Date: 2026-04-26

"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision = "p8q9r0s1t2u3"
down_revision: Union[str, None] = "o7p8q9r0s1t2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("feedback")
