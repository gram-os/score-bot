"""Add difficulty_multiplier to games and seed Season 1 values

Revision ID: w5x6y7z8a9b0
Revises: v4w5x6y7z8a9
Create Date: 2026-04-30

"""

import sqlalchemy as sa
from alembic import op

revision = "w5x6y7z8a9b0"
down_revision = "v4w5x6y7z8a9"
branch_labels = None
depends_on = None

# Multipliers derived from difficulty analysis (reference avg = 50.0)
# Games not listed (mini_crossword) retain the default 1.0
SEASON_1_MULTIPLIERS = {
    "betweenle": 1.4,
    "quordle": 1.36,
    "connections": 0.86,
    "wordle": 0.84,
    "glyph": 0.74,
    "time_guessr": 0.7,
    "pokedoku": 0.52,
    "enclose_horse": 0.51,
}


def upgrade() -> None:
    with op.batch_alter_table("games") as batch_op:
        batch_op.add_column(
            sa.Column(
                "difficulty_multiplier",
                sa.Float(),
                nullable=False,
                server_default="1.0",
            )
        )

    conn = op.get_bind()
    for game_id, multiplier in SEASON_1_MULTIPLIERS.items():
        conn.execute(
            sa.text("UPDATE games SET difficulty_multiplier = :m WHERE id = :id"),
            {"m": multiplier, "id": game_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("games") as batch_op:
        batch_op.drop_column("difficulty_multiplier")
