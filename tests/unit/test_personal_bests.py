from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from bot.database import Base, Game, Submission, get_personal_bests


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
        sess.merge(
            Game(
                id="wordle",
                name="Wordle",
                enabled=True,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        sess.flush()
        yield sess
        sess.rollback()


def _add_submission(
    session: Session,
    *,
    user_id: str,
    base_score: float,
    speed_bonus: int,
    rank: int,
    day: date,
    submitted_at: datetime,
    raw_data: dict | None = None,
) -> Submission:
    sub = Submission(
        user_id=user_id,
        username=user_id,
        game_id="wordle",
        date=day,
        base_score=base_score,
        speed_bonus=speed_bonus,
        total_score=base_score + speed_bonus,
        submission_rank=rank,
        raw_data=raw_data or {},
        submitted_at=submitted_at,
    )
    session.add(sub)
    session.flush()
    return sub


class TestGetPersonalBestsOrdering:
    def test_returns_higher_base_score_even_when_total_is_lower(self, session):
        _add_submission(
            session,
            user_id="u1",
            base_score=80.0,
            speed_bonus=15,
            rank=1,
            day=date(2026, 1, 1),
            submitted_at=datetime(2026, 1, 1, 12, 0, 0),
            raw_data={"variant": "A"},
        )
        _add_submission(
            session,
            user_id="u1",
            base_score=90.0,
            speed_bonus=0,
            rank=4,
            day=date(2026, 1, 2),
            submitted_at=datetime(2026, 1, 2, 12, 0, 0),
            raw_data={"variant": "B"},
        )

        bests = get_personal_bests(session, "u1", "wordle")

        assert bests is not None
        assert bests.best_score == 90.0
        assert bests.best_date == date(2026, 1, 2)
        assert bests.best_raw_data == {"variant": "B"}

    def test_tie_breaks_on_earliest_submitted_at(self, session):
        _add_submission(
            session,
            user_id="u2",
            base_score=85.0,
            speed_bonus=0,
            rank=4,
            day=date(2026, 2, 5),
            submitted_at=datetime(2026, 2, 5, 9, 0, 0),
            raw_data={"variant": "early"},
        )
        _add_submission(
            session,
            user_id="u2",
            base_score=85.0,
            speed_bonus=15,
            rank=1,
            day=date(2026, 2, 6),
            submitted_at=datetime(2026, 2, 6, 9, 0, 0),
            raw_data={"variant": "late"},
        )

        bests = get_personal_bests(session, "u2", "wordle")

        assert bests is not None
        assert bests.best_score == 85.0
        assert bests.best_raw_data == {"variant": "early"}

    def test_avg_score_uses_base_score(self, session):
        _add_submission(
            session,
            user_id="u3",
            base_score=60.0,
            speed_bonus=15,
            rank=1,
            day=date(2026, 3, 1),
            submitted_at=datetime(2026, 3, 1, 8, 0, 0),
        )
        _add_submission(
            session,
            user_id="u3",
            base_score=80.0,
            speed_bonus=0,
            rank=5,
            day=date(2026, 3, 2),
            submitted_at=datetime(2026, 3, 2, 8, 0, 0),
        )

        bests = get_personal_bests(session, "u3", "wordle")

        assert bests is not None
        assert bests.count == 2
        assert bests.avg_score == pytest.approx(70.0)

    def test_returns_none_when_no_submissions(self, session):
        assert get_personal_bests(session, "ghost", "wordle") is None
