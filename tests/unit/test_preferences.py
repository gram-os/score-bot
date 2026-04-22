import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from bot.database import Base, UserPreference, get_preference, set_preference


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as sess:
        yield sess
        sess.rollback()


class TestGetPreference:
    def test_returns_none_when_no_record(self, session):
        assert get_preference(session, "nonexistent_user") is None

    def test_returns_preference_after_set(self, session):
        set_preference(session, "user1", remind_streak_days=5)
        pref = get_preference(session, "user1")
        assert pref is not None
        assert pref.user_id == "user1"
        assert pref.remind_streak_days == 5


class TestSetPreference:
    def test_creates_new_preference(self, session):
        pref = set_preference(session, "user2", remind_streak_days=3)
        assert pref.user_id == "user2"
        assert pref.remind_streak_days == 3

    def test_updates_existing_preference(self, session):
        set_preference(session, "user3", remind_streak_days=3)
        updated = set_preference(session, "user3", remind_streak_days=7)
        assert updated.remind_streak_days == 7
        assert get_preference(session, "user3").remind_streak_days == 7

    def test_opt_out_sets_zero(self, session):
        set_preference(session, "user4", remind_streak_days=5)
        set_preference(session, "user4", remind_streak_days=0)
        assert get_preference(session, "user4").remind_streak_days == 0
