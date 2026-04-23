"""add admin_config table

Revision ID: h0i1j2k3l4m5
Revises: g8h9i0j1k2l3
Create Date: 2026-04-23

"""

import sqlalchemy as sa
from alembic import op

revision = "h0i1j2k3l4m5"
down_revision = "g8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_config",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    config_table = sa.table(
        "admin_config",
        sa.column("key", sa.String),
        sa.column("value", sa.String),
    )
    op.bulk_insert(
        config_table, [{"key": "display_timezone", "value": "America/New_York"}]
    )


def downgrade() -> None:
    op.drop_table("admin_config")
