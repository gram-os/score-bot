import os
from datetime import date, datetime, timezone

os.environ.setdefault("DISCORD_TOKEN", "test")
os.environ.setdefault("DISCORD_CHANNEL_ID", "0")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from bot.db.leaderboard import get_leaderboard  # noqa: E402
from bot.db.models import Base, Game, Submission, User  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def session(engine):
    with Session(engine) as sess:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        sess.merge(Game(id="wordle", name="Wordle", enabled=True, created_at=now))
        for uid, uname in [("alice", "Alice"), ("bob", "Bob")]:
            sess.merge(User(user_id=uid, username=uname, updated_at=now))
        sess.flush()
        yield sess
        sess.rollback()


def _add(session: Session, user_id: str, day: date, total_score: float) -> None:
    session.add(
        Submission(
            user_id=user_id,
            username=user_id,
            game_id="wordle",
            date=day,
            base_score=total_score,
            speed_bonus=0,
            total_score=total_score,
            submission_rank=1,
            raw_data={},
            submitted_at=datetime(day.year, day.month, day.day, 12, 0, 0),
        )
    )
    session.flush()


class TestCustomRange:
    def test_custom_range_filters_to_inclusive_window(self, session: Session) -> None:
        _add(session, "alice", date(2026, 1, 1), 100)
        _add(session, "alice", date(2026, 1, 5), 50)
        _add(session, "alice", date(2026, 1, 10), 25)

        rows = get_leaderboard(
            session,
            period="custom",
            start_date=date(2026, 1, 2),
            end_date=date(2026, 1, 9),
        )

        assert len(rows) == 1
        assert rows[0].user_id == "alice"
        assert rows[0].total_score == 50

    def test_custom_range_inclusive_endpoints(self, session: Session) -> None:
        _add(session, "alice", date(2026, 2, 1), 10)
        _add(session, "alice", date(2026, 2, 7), 20)

        rows = get_leaderboard(
            session,
            period="custom",
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 7),
        )

        assert rows[0].total_score == 30

    def test_custom_range_requires_both_dates(self, session: Session) -> None:
        with pytest.raises(ValueError):
            get_leaderboard(session, period="custom", start_date=date(2026, 1, 1))
        with pytest.raises(ValueError):
            get_leaderboard(session, period="custom", end_date=date(2026, 1, 1))


class TestParseCustomRange:
    def test_rejects_missing(self) -> None:
        from bot.commands.leaderboard import _parse_custom_range

        assert isinstance(_parse_custom_range(None, "2026-01-01"), str)
        assert isinstance(_parse_custom_range("2026-01-01", None), str)

    def test_rejects_bad_format(self) -> None:
        from bot.commands.leaderboard import _parse_custom_range

        assert isinstance(_parse_custom_range("01/01/2026", "2026-01-02"), str)

    def test_rejects_inverted_range(self) -> None:
        from bot.commands.leaderboard import _parse_custom_range

        assert isinstance(_parse_custom_range("2026-02-01", "2026-01-01"), str)

    def test_rejects_oversized_range(self) -> None:
        from bot.commands.leaderboard import _parse_custom_range

        assert isinstance(_parse_custom_range("2025-01-01", "2026-12-31"), str)

    def test_accepts_valid(self) -> None:
        from bot.commands.leaderboard import _parse_custom_range

        result = _parse_custom_range("2026-01-01", "2026-01-31")
        assert result == (date(2026, 1, 1), date(2026, 1, 31))
