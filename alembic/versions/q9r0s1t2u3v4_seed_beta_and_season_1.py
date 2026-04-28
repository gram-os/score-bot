"""Seed Beta season and Season 1

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
Create Date: 2026-04-28

"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision = "q9r0s1t2u3v4"
down_revision: Union[str, None] = "p8q9r0s1t2u3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing = conn.execute(sa.text("SELECT COUNT(*) FROM seasons")).scalar()
    if existing == 0:
        conn.execute(
            sa.text(
                "INSERT INTO seasons (name, start_date, end_date) VALUES "
                "('Beta', '2024-01-01', '2026-04-30'), "
                "('Season 1', '2026-05-01', '2026-05-31')"
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM seasons WHERE name IN ('Beta', 'Season 1')"))
