from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from bot.achievements import GAME_MVP_BADGES, check_and_award_achievements, resolve_achievement_def
from bot.database import Base, Game, Season, Submission, User, UserStreak
from bot.db.achievements import award_game_mvp, get_season_game_top_scorers


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


class TestGameMvpBadges:
    def test_resolve_all_game_mvp_slugs(self):
        for game_id, badge in GAME_MVP_BADGES.items():
            slug = f"game_mvp_{game_id}_season_1"
            resolved = resolve_achievement_def(slug)
            assert resolved is not None, f"Could not resolve slug for game_id={game_id}"
            assert resolved.name == badge.name

    def test_resolve_unknown_game_returns_none(self):
        assert resolve_achievement_def("game_mvp_unknown_game_season_1") is None

    def test_award_game_mvp_newly_awarded(self, session):
        awarded = award_game_mvp(session, "u1", "wordle", 1, "Season 1", "Five-Letter Freak")
        assert awarded is True

    def test_award_game_mvp_idempotent(self, session):
        award_game_mvp(session, "u1", "glyph", 1, "Season 1", "Hieroglyph Haver")
        awarded_again = award_game_mvp(session, "u1", "glyph", 1, "Season 1", "Hieroglyph Haver")
        assert awarded_again is False

    def test_get_season_game_top_scorers(self, session):
        season = Season(name="Season 1", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        session.add(season)
        session.flush()

        u2 = User(user_id="u2", username="Runner", updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        session.merge(u2)
        session.flush()

        session.add(
            Submission(
                user_id="u1",
                username="Tester",
                game_id="wordle",
                date=date(2026, 9, 1),
                base_score=100.0,
                speed_bonus=0,
                total_score=100.0,
                submission_rank=1,
                raw_data={},
                submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        session.add(
            Submission(
                user_id="u2",
                username="Runner",
                game_id="wordle",
                date=date(2026, 9, 2),
                base_score=60.0,
                speed_bonus=0,
                total_score=60.0,
                submission_rank=1,
                raw_data={},
                submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        session.flush()

        rows = get_season_game_top_scorers(session, season)
        wordle_mvp = next((r for r in rows if r.game_id == "wordle"), None)
        assert wordle_mvp is not None
        assert wordle_mvp.user_id == "u1"
        assert wordle_mvp.total_score == 100.0
