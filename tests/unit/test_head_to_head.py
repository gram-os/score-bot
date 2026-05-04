from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from bot.db.head_to_head import get_head_to_head
from bot.db.models import Base, Game, Submission, User


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
        for game_id, name in [("wordle", "Wordle"), ("connections", "Connections")]:
            sess.merge(Game(id=game_id, name=name, enabled=True, created_at=now))
        for uid, uname in [("alice", "Alice"), ("bob", "Bob")]:
            sess.merge(User(user_id=uid, username=uname, updated_at=now))
        sess.flush()
        yield sess
        sess.rollback()


def _add_submission(
    session: Session,
    *,
    user_id: str,
    game_id: str,
    total_score: float,
    day: date,
) -> Submission:
    sub = Submission(
        user_id=user_id,
        username=user_id,
        game_id=game_id,
        date=day,
        base_score=total_score,
        speed_bonus=0,
        total_score=total_score,
        submission_rank=1,
        raw_data={},
        submitted_at=datetime.combine(day, datetime.min.time()),
    )
    session.add(sub)
    session.flush()
    return sub


def _seed_overlapping_pair(session: Session) -> None:
    _add_submission(session, user_id="alice", game_id="wordle", total_score=90.0, day=date(2026, 1, 1))
    _add_submission(session, user_id="bob", game_id="wordle", total_score=80.0, day=date(2026, 1, 1))
    _add_submission(session, user_id="alice", game_id="wordle", total_score=70.0, day=date(2026, 1, 2))
    _add_submission(session, user_id="bob", game_id="wordle", total_score=85.0, day=date(2026, 1, 2))
    _add_submission(session, user_id="alice", game_id="connections", total_score=50.0, day=date(2026, 1, 3))
    _add_submission(session, user_id="bob", game_id="connections", total_score=50.0, day=date(2026, 1, 3))


class TestGetHeadToHeadGameFilter:
    def test_no_filter_counts_all_games(self, session):
        _seed_overlapping_pair(session)

        result = get_head_to_head(session, "alice", "bob")

        assert result is not None
        assert result.overlapping_days == 3
        assert result.caller_total_score == pytest.approx(210.0)
        assert result.opponent_total_score == pytest.approx(215.0)
        assert result.caller_wins == 1
        assert result.opponent_wins == 1
        assert result.ties == 1

    def test_game_filter_only_counts_that_game(self, session):
        _seed_overlapping_pair(session)

        result = get_head_to_head(session, "alice", "bob", game_id="wordle")

        assert result is not None
        assert result.overlapping_days == 2
        assert result.caller_total_score == pytest.approx(160.0)
        assert result.opponent_total_score == pytest.approx(165.0)
        assert result.caller_wins == 1
        assert result.opponent_wins == 1
        assert result.ties == 0

    def test_game_filter_with_no_overlap_returns_none(self, session):
        _add_submission(session, user_id="alice", game_id="wordle", total_score=90.0, day=date(2026, 2, 1))
        _add_submission(session, user_id="bob", game_id="connections", total_score=80.0, day=date(2026, 2, 1))

        result = get_head_to_head(session, "alice", "bob", game_id="wordle")

        assert result is None

    def test_returns_resolved_usernames_from_user_table(self, session):
        _seed_overlapping_pair(session)

        result = get_head_to_head(session, "alice", "bob", game_id="wordle")

        assert result is not None
        assert result.caller_username == "Alice"
        assert result.opponent_username == "Bob"
