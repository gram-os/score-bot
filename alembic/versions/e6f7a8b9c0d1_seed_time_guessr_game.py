"""seed_time_guessr_game

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-04-22

"""

from typing import Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT OR IGNORE INTO games (id, name, enabled, created_at) VALUES (:id, :name, :enabled, :created_at)"
        ),
        {
            "id": "time_guessr",
            "name": "Time Guessr",
            "enabled": True,
            "created_at": now,
        },
    )


def downgrade() -> None:
    op.execute("DELETE FROM games WHERE id = 'time_guessr'")
