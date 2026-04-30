"""remove timezone config rows

Revision ID: v4w5x6y7z8a9
Revises: u3v4w5x6y7z8
Create Date: 2026-04-30

"""

import sqlalchemy as sa
from alembic import op

revision = "v4w5x6y7z8a9"
down_revision = "u3v4w5x6y7z8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM admin_config WHERE key IN ('display_timezone', 'scoring_timezone')"))


def downgrade() -> None:
    config_table = sa.table(
        "admin_config",
        sa.column("key", sa.String),
        sa.column("value", sa.String),
    )
    op.bulk_insert(config_table, [{"key": "display_timezone", "value": "America/New_York"}])
