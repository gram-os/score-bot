"""add streaks, seasons, and achievements

Revision ID: g8h9i0j1k2l3
Revises: f7a8b9c0d1e2
Create Date: 2026-04-22

"""

from collections import defaultdict
from datetime import date, timedelta

import sqlalchemy as sa
from alembic import op

revision = "g8h9i0j1k2l3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_streaks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("game_id", sa.String(), nullable=False),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_submission_date", sa.Date(), nullable=True),
        sa.Column("freeze_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "game_id"),
    )

    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("achievement_slug", sa.String(), nullable=False),
        sa.Column("earned_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "achievement_slug"),
    )

    _seed_seasons()
    _backfill_streaks()


def _seed_seasons() -> None:
    seasons_table = sa.table(
        "seasons",
        sa.column("name", sa.String),
        sa.column("start_date", sa.Date),
        sa.column("end_date", sa.Date),
    )
    rows = []
    for year in (2024, 2025, 2026):
        rows += [
            {
                "name": f"Jan–Mar {year}",
                "start_date": date(year, 1, 1),
                "end_date": date(year, 3, 31),
            },
            {
                "name": f"Apr–Jun {year}",
                "start_date": date(year, 4, 1),
                "end_date": date(year, 6, 30),
            },
            {
                "name": f"Jul–Sep {year}",
                "start_date": date(year, 7, 1),
                "end_date": date(year, 9, 30),
            },
            {
                "name": f"Oct–Dec {year}",
                "start_date": date(year, 10, 1),
                "end_date": date(year, 12, 31),
            },
        ]
    op.bulk_insert(seasons_table, rows)


def _backfill_streaks() -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT user_id, game_id, date FROM submissions ORDER BY user_id, game_id, date"
        )
    )

    user_game_dates: dict[tuple[str, str], list[date]] = defaultdict(list)
    for row in result:
        raw = row[2]
        if isinstance(raw, str):
            d = date.fromisoformat(raw)
        else:
            d = raw
        user_game_dates[(row[0], row[1])].append(d)

    today = date.today()
    to_insert = []

    for (user_id, game_id), dates in user_game_dates.items():
        dates_set = set(dates)

        anchor = today if today in dates_set else today - timedelta(days=1)
        current_streak = 0
        if anchor in dates_set:
            d = anchor
            while d in dates_set:
                current_streak += 1
                d -= timedelta(days=1)

        sorted_dates = sorted(dates_set)
        longest = max_run = 1
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
                max_run += 1
                if max_run > longest:
                    longest = max_run
            else:
                max_run = 1

        to_insert.append(
            {
                "user_id": user_id,
                "game_id": game_id,
                "current_streak": current_streak,
                "longest_streak": longest,
                "last_submission_date": max(dates_set).isoformat(),
                "freeze_count": 0,
            }
        )

    if to_insert:
        bind.execute(
            sa.text(
                "INSERT INTO user_streaks "
                "(user_id, game_id, current_streak, longest_streak, last_submission_date, freeze_count) "
                "VALUES (:user_id, :game_id, :current_streak, :longest_streak, :last_submission_date, :freeze_count)"
            ),
            to_insert,
        )


def downgrade() -> None:
    op.drop_table("user_achievements")
    op.drop_table("seasons")
    op.drop_table("user_streaks")
