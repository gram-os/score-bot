"""seed_pokedoku_game

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-04-22

"""

from typing import Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
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
            "id": "pokedoku",
            "name": "PokéDoku",
            "enabled": True,
            "created_at": now,
        },
    )


def downgrade() -> None:
    op.execute("DELETE FROM games WHERE id = 'pokedoku'")
