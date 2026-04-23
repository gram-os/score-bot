from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from bot.achievements import check_and_award_achievements
from bot.database import Base, Game, Submission, User, UserStreak


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
        for game_id, name in [
            ("wordle", "Wordle"),
            ("glyph", "Glyph"),
            ("connections", "Connections"),
        ]:
            g = Game(
                id=game_id,
                name=name,
                enabled=True,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            sess.merge(g)
        user = User(
            user_id="u1",
            username="Tester",
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        sess.merge(user)
        sess.flush()
        yield sess
        sess.rollback()


def _make_submission(session, user_id="u1", game_id="wordle", d=date(2026, 1, 1), rank=2):
    sub = Submission(
        user_id=user_id,
        username="Tester",
        game_id=game_id,
        date=d,
        base_score=80.0,
        speed_bonus=0,
        total_score=80.0,
        submission_rank=rank,
        raw_data={},
        submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(sub)
    session.flush()
    return sub


def _make_streak(current=1, longest=1, freeze_count=0):
    return UserStreak(
        user_id="u1",
        game_id="wordle",
        current_streak=current,
        longest_streak=longest,
        last_submission_date=date(2026, 1, 1),
        freeze_count=freeze_count,
    )


class TestFirstSteps:
    def test_awarded_on_first_submission(self, session):
        sub = _make_submission(session, d=date(2026, 4, 1))
        streak = _make_streak()
        slugs = check_and_award_achievements(session, "u1", "wordle", date(2026, 4, 1), streak, sub, False, 3)
        assert "first_steps" in slugs

    def test_not_awarded_again(self, session):
        _make_submission(session, d=date(2026, 4, 2))
        sub = _make_submission(session, d=date(2026, 4, 3))
        streak = _make_streak()
        slugs = check_and_award_achievements(session, "u1", "wordle", date(2026, 4, 3), streak, sub, False, 3)
        assert "first_steps" not in slugs


class TestStreakAchievements:
    def test_on_fire_at_seven(self, session):
        sub = _make_submission(session, d=date(2026, 5, 1))
        streak = _make_streak(current=7, longest=7)
        slugs = check_and_award_achievements(session, "u1", "wordle", date(2026, 5, 1), streak, sub, False, 3)
        assert "on_fire" in slugs

    def test_on_fire_not_at_six(self, session):
        sub = _make_submission(session, d=date(2026, 5, 2))
        streak = _make_streak(current=6, longest=6)
        slugs = check_and_award_achievements(session, "u1", "wordle", date(2026, 5, 2), streak, sub, False, 3)
        assert "on_fire" not in slugs


class TestSpeedAchievements:
    def test_speed_demon_on_first_place(self, session):
        sub = _make_submission(session, d=date(2026, 6, 1), rank=1)
        streak = _make_streak()
        slugs = check_and_award_achievements(session, "u1", "wordle", date(2026, 6, 1), streak, sub, False, 3)
        assert "speed_demon" in slugs

    def test_speed_demon_not_on_second_place(self, session):
        sub = _make_submission(session, d=date(2026, 6, 2), rank=2)
        streak = _make_streak()
        slugs = check_and_award_achievements(session, "u1", "wordle", date(2026, 6, 2), streak, sub, False, 3)
        assert "speed_demon" not in slugs


class TestVarietyAchievements:
    def test_hat_trick_with_three_games(self, session):
        today = date(2026, 7, 1)
        _make_submission(session, game_id="wordle", d=today)
        _make_submission(session, game_id="glyph", d=today)
        sub = _make_submission(session, game_id="connections", d=today)
        streak = _make_streak()
        slugs = check_and_award_achievements(session, "u1", "connections", today, streak, sub, False, 3)
        assert "hat_trick" in slugs

    def test_completionist_when_all_games_played(self, session):
        today = date(2026, 7, 2)
        _make_submission(session, game_id="wordle", d=today)
        _make_submission(session, game_id="glyph", d=today)
        sub = _make_submission(session, game_id="connections", d=today)
        streak = _make_streak()
        slugs = check_and_award_achievements(session, "u1", "connections", today, streak, sub, False, 3)
        assert "completionist" in slugs

    def test_completionist_not_with_partial(self, session):
        today = date(2026, 7, 3)
        _make_submission(session, game_id="wordle", d=today)
        sub = _make_submission(session, game_id="glyph", d=today)
        streak = _make_streak()
        slugs = check_and_award_achievements(session, "u1", "glyph", today, streak, sub, False, 3)
        assert "completionist" not in slugs


class TestFreezeAchievement:
    def test_freeze_saver_when_freeze_used(self, session):
        sub = _make_submission(session, d=date(2026, 8, 1))
        streak = _make_streak(current=5)
        slugs = check_and_award_achievements(session, "u1", "wordle", date(2026, 8, 1), streak, sub, True, 3)
        assert "freeze_saver" in slugs

    def test_freeze_saver_not_without_freeze(self, session):
        sub = _make_submission(session, d=date(2026, 8, 2))
        streak = _make_streak(current=5)
        slugs = check_and_award_achievements(session, "u1", "wordle", date(2026, 8, 2), streak, sub, False, 3)
        assert "freeze_saver" not in slugs
