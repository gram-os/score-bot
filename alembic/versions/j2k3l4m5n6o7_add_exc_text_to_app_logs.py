"""add exc_text to app_logs

Revision ID: j2k3l4m5n6o7
Revises: i1j2k3l4m5n6
Create Date: 2026-04-24

"""

import sqlalchemy as sa
from alembic import op

revision = "j2k3l4m5n6o7"
down_revision = "i1j2k3l4m5n6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_logs", sa.Column("exc_text", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("app_logs", "exc_text")
