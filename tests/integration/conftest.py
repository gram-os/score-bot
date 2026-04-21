from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from bot.database import Base, Game


@pytest.fixture(scope="session")
def engine():
    # StaticPool keeps a single in-memory connection alive for the whole session
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as sess:
        yield sess
        sess.rollback()


@pytest.fixture
def wordle_game(session):
    game = Game(
        id="wordle",
        name="Wordle",
        enabled=True,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(game)
    session.flush()
    return game
