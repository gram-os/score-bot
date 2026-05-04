"""seed missing games

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-22

"""

from typing import Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

GAMES = [
    {"id": "connections", "name": "Connections"},
    {"id": "mini_crossword", "name": "Mini Crossword"},
    {"id": "quordle", "name": "Quordle"},
    {"id": "glyph", "name": "Glyph"},
    {"id": "enclose_horse", "name": "Enclose.horse"},
]


def upgrade() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conn = op.get_bind()
    for g in GAMES:
        conn.execute(
            sa.text(
                "INSERT OR IGNORE INTO games (id, name, enabled, created_at) VALUES (:id, :name, :enabled, :created_at)"
            ),
            {"id": g["id"], "name": g["name"], "enabled": True, "created_at": now},
        )


def downgrade() -> None:
    op.execute("DELETE FROM games WHERE id IN ('connections', 'mini_crossword', 'quordle', 'glyph', 'enclose_horse')")
