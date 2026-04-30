"""add scoring_timezone config

Revision ID: u3v4w5x6y7z8
Revises: t2u3v4w5x6y7
Create Date: 2026-04-30

"""

import sqlalchemy as sa
from alembic import op

revision = "u3v4w5x6y7z8"
down_revision = "t2u3v4w5x6y7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    config_table = sa.table(
        "admin_config",
        sa.column("key", sa.String),
        sa.column("value", sa.String),
    )
    # Seed scoring_timezone to match the existing display_timezone value.
    # Uses a subselect so existing installs inherit their configured display timezone.
    conn = op.get_bind()
    row = conn.execute(sa.text("SELECT value FROM admin_config WHERE key = 'display_timezone'")).fetchone()
    default_tz = row[0] if row else "America/New_York"

    existing = conn.execute(sa.text("SELECT key FROM admin_config WHERE key = 'scoring_timezone'")).fetchone()
    if not existing:
        op.bulk_insert(config_table, [{"key": "scoring_timezone", "value": default_tz}])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM admin_config WHERE key = 'scoring_timezone'"))
