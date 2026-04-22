from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from bot.database import Game, Submission


def _add(session, user_id, username, game_id, days_ago):
    target_date = date.today() - timedelta(days=days_ago)
    sub = Submission(
        user_id=user_id,
        username=username,
        game_id=game_id,
        date=target_date,
        base_score=75.0,
        speed_bonus=0,
        total_score=75.0,
        submission_rank=1,
        raw_data={},
        submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(sub)
    session.flush()
    return sub


def _query_stats(session, days):
    from bot.database import Game, Submission

    cutoff = date.today() - timedelta(days=days)
    rows = session.execute(
        select(
            Submission.date,
            Submission.game_id,
            Game.name.label("game_name"),
            func.count(Submission.id).label("count"),
        )
        .join(Game, Submission.game_id == Game.id)
        .where(Submission.date >= cutoff)
        .group_by(Submission.game_id, Game.name, Submission.date)
        .order_by(Submission.date.asc(), Game.name.asc())
    ).all()
    return [
        {
            "date": str(r.date),
            "game_id": r.game_id,
            "game": r.game_name,
            "count": r.count,
        }
        for r in rows
    ]


@pytest.fixture
def two_games(session):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    g1 = Game(id="wordle", name="Wordle", enabled=True, created_at=now)
    g2 = Game(id="mini", name="Mini", enabled=True, created_at=now)
    session.add_all([g1, g2])
    session.flush()
    return g1, g2


class TestStatsSubmissionsQuery:
    def test_returns_entries_within_window(self, session, two_games):
        _add(session, "u1", "Alice", "wordle", days_ago=5)
        result = _query_stats(session, days=30)
        assert any(r["game_id"] == "wordle" and r["count"] == 1 for r in result)

    def test_excludes_entries_outside_window(self, session, two_games):
        _add(session, "u1", "Alice", "wordle", days_ago=31)
        result = _query_stats(session, days=30)
        assert result == []

    def test_groups_by_game_and_date(self, session, two_games):
        _add(session, "u1", "Alice", "wordle", days_ago=1)
        _add(session, "u2", "Bob", "wordle", days_ago=1)
        _add(session, "u3", "Carol", "mini", days_ago=1)
        result = _query_stats(session, days=7)
        by_game = {r["game_id"]: r["count"] for r in result}
        assert by_game["wordle"] == 2
        assert by_game["mini"] == 1

    def test_ordered_by_date_then_game(self, session, two_games):
        _add(session, "u1", "Alice", "wordle", days_ago=2)
        _add(session, "u2", "Bob", "mini", days_ago=1)
        result = _query_stats(session, days=7)
        dates = [r["date"] for r in result]
        assert dates == sorted(dates)

    def test_7_day_window(self, session, two_games):
        _add(session, "u1", "Alice", "wordle", days_ago=6)
        _add(session, "u2", "Bob", "wordle", days_ago=8)
        result = _query_stats(session, days=7)
        assert len(result) == 1
        assert result[0]["game_id"] == "wordle"

    def test_empty_db_returns_empty_list(self, session, two_games):
        assert _query_stats(session, days=30) == []
