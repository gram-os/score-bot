"""Add message_text to submissions

Revision ID: s1t2u3v4w5x6
Revises: r0s1t2u3v4w5
Create Date: 2026-04-29

"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision = "s1t2u3v4w5x6"
down_revision: Union[str, None] = "r0s1t2u3v4w5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("message_text", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "message_text")
