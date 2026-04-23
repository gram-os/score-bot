from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from bot.database import Base, Game, UserStreak, update_streak_on_submission


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
        game = Game(
            id="wordle",
            name="Wordle",
            enabled=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        sess.merge(game)
        sess.flush()
        yield sess
        sess.rollback()


D0 = date(2026, 1, 1)
D1 = date(2026, 1, 2)
D2 = date(2026, 1, 3)
D3 = date(2026, 1, 4)
D4 = date(2026, 1, 5)
D5 = date(2026, 1, 6)
D6 = date(2026, 1, 7)
D7 = date(2026, 1, 8)
D9 = date(2026, 1, 10)
D14 = date(2026, 1, 15)


def _streak(session, days: list[date]) -> tuple[UserStreak, bool]:
    streak, freeze_used = None, False
    for d in days:
        streak, freeze_used = update_streak_on_submission(session, "u1", "wordle", d)
    return streak, freeze_used


class TestConsecutiveStreak:
    def test_first_submission_starts_at_one(self, session):
        streak, _ = update_streak_on_submission(session, "u1", "wordle", D0)
        assert streak.current_streak == 1
        assert streak.longest_streak == 1

    def test_consecutive_day_increments(self, session):
        _streak(session, [D0, D1])
        streak, _ = update_streak_on_submission(session, "u1", "wordle", D2)
        assert streak.current_streak == 3

    def test_same_day_does_not_increment(self, session):
        _streak(session, [D0, D1])
        streak, _ = update_streak_on_submission(session, "u1", "wordle", D1)
        assert streak.current_streak == 2

    def test_longest_streak_tracks_maximum(self, session):
        _streak(session, [D0, D1, D2, D3])
        streak, _ = update_streak_on_submission(session, "u1", "wordle", D4)
        assert streak.longest_streak >= 5


class TestFreezeEarning:
    def test_freeze_awarded_at_day_seven(self, session):
        days = [D0, D1, D2, D3, D4, D5, D6]
        streak, _ = _streak(session, days)
        assert streak.current_streak == 7
        assert streak.freeze_count == 1

    def test_freeze_caps_at_three(self, session):
        # Build a 21-day streak (3 freeze milestones)
        days = [date(2026, 2, d) for d in range(1, 22)]
        streak, _ = _streak(session, days)
        assert streak.freeze_count == 3

    def test_freeze_does_not_exceed_cap_on_day_28(self, session):
        days = [date(2026, 3, d) for d in range(1, 29)]
        streak, _ = _streak(session, days)
        assert streak.freeze_count == 3


class TestFreezeUsage:
    def test_one_day_gap_uses_freeze(self, session):
        _streak(session, [D0, D1, D2, D3, D4, D5, D6])
        # D7 skipped — submit on D9 (2-day gap from D7's expected submission at D7)
        # Actually: last_submission is D6, submitting D8 = 2-day gap
        d8 = date(2026, 1, 9)
        streak, freeze_used = update_streak_on_submission(session, "u1", "wordle", d8)
        assert freeze_used is True
        assert streak.freeze_count == 0
        assert streak.current_streak == 8

    def test_one_day_gap_without_freeze_resets(self, session):
        _streak(session, [D0, D1])
        # 2-day gap, no freeze
        streak, freeze_used = update_streak_on_submission(session, "u1", "wordle", D4)
        assert freeze_used is False
        assert streak.current_streak == 1

    def test_two_day_gap_breaks_streak_even_with_freeze(self, session):
        _streak(session, [D0, D1, D2, D3, D4, D5, D6])
        # D6 → D9: 3-day gap, should break regardless of freeze
        streak, freeze_used = update_streak_on_submission(session, "u1", "wordle", D9)
        assert freeze_used is False
        assert streak.current_streak == 1


class TestLongestStreak:
    def test_longest_persists_after_reset(self, session):
        _streak(session, [D0, D1, D2, D3, D4])
        streak, _ = update_streak_on_submission(session, "u1", "wordle", D9)
        assert streak.longest_streak == 5
        assert streak.current_streak == 1
