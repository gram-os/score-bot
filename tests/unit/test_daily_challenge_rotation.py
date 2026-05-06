from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from bot.db import daily_challenge
from bot.db.models import Base, Game
from bot.tasks import daily_challenge_rotation


pytestmark = pytest.mark.unit


@pytest.fixture
def Session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with factory() as s:
        s.add_all(
            [
                Game(id="wordle", name="Wordle", enabled=True, created_at=now),
                Game(id="connections", name="Connections", enabled=True, created_at=now),
                Game(id="disabled_one", name="Disabled", enabled=False, created_at=now),
            ]
        )
        s.commit()
    yield factory
    engine.dispose()


def _today(Session_factory) -> "datetime.date":
    from bot.db.config import SCORING_TZ

    return datetime.now(SCORING_TZ).date()


class TestDailyChallengeRotation:
    def test_no_op_when_disabled(self, Session_factory) -> None:
        daily_challenge_rotation.run_daily_rotation(Session_factory)

        with Session_factory() as s:
            chosen = daily_challenge.get_today_game_id(s, _today(Session_factory))
            assert chosen is None

    def test_no_op_when_manual_mode(self, Session_factory) -> None:
        with Session_factory() as s:
            daily_challenge.set_enabled(s, True)
            daily_challenge.set_mode(s, "manual")
            s.commit()

        daily_challenge_rotation.run_daily_rotation(Session_factory)

        with Session_factory() as s:
            chosen = daily_challenge.get_today_game_id(s, _today(Session_factory))
            assert chosen is None

    def test_rolls_when_enabled_and_random(self, Session_factory) -> None:
        with Session_factory() as s:
            daily_challenge.set_enabled(s, True)
            daily_challenge.set_mode(s, "random")
            s.commit()

        daily_challenge_rotation.run_daily_rotation(Session_factory)

        with Session_factory() as s:
            chosen = daily_challenge.get_today_game_id(s, _today(Session_factory))
            assert chosen in ("wordle", "connections")

    def test_skips_disabled_games(self, Session_factory) -> None:
        with Session_factory() as s:
            daily_challenge.set_enabled(s, True)
            daily_challenge.set_mode(s, "random")
            s.commit()

        for _ in range(20):
            daily_challenge_rotation.run_daily_rotation(Session_factory)

        with Session_factory() as s:
            chosen = daily_challenge.get_today_game_id(s, _today(Session_factory))
            assert chosen != "disabled_one"
