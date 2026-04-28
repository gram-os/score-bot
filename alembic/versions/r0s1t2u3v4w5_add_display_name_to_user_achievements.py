"""Add display_name to user_achievements

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v4
Create Date: 2026-04-28

"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision = "r0s1t2u3v4w5"
down_revision: Union[str, None] = "q9r0s1t2u3v4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_achievements", sa.Column("display_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_achievements", "display_name")
