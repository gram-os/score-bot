"""add users table

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-04-22

"""

from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    # Backfill from submissions: most recent username per user_id
    op.get_bind().execute(sa.text("""
        INSERT INTO users (user_id, username, updated_at)
        SELECT user_id, username, MAX(submitted_at)
        FROM submissions
        GROUP BY user_id
    """))


def downgrade() -> None:
    op.drop_table("users")
