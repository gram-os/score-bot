"""seed_betweenle_game

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2026-04-25

"""

from datetime import datetime, timezone
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "k3l4m5n6o7p8"
down_revision: Union[str, None] = "j2k3l4m5n6o7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT OR IGNORE INTO games (id, name, enabled, created_at) "
            "VALUES (:id, :name, :enabled, :created_at)"
        ),
        {
            "id": "betweenle",
            "name": "Betweenle",
            "enabled": True,
            "created_at": now,
        },
    )


def downgrade() -> None:
    op.execute("DELETE FROM games WHERE id = 'betweenle'")
