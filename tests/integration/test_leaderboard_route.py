from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from bot.database import Base, Game, Submission, User


pytestmark = pytest.mark.integration


@pytest.fixture
def route_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def seeded(route_engine):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = date.today()
    with Session(route_engine) as sess:
        sess.add_all(
            [
                Game(id="wordle", name="Wordle", enabled=True, created_at=now),
                Game(id="mini", name="Mini", enabled=True, created_at=now),
                User(user_id="u1", username="Alice", updated_at=now),
                User(user_id="u2", username="Bob", updated_at=now),
            ]
        )
        sess.flush()
        sess.add_all(
            [
                Submission(
                    user_id="u1",
                    username="Alice",
                    game_id="wordle",
                    date=today,
                    base_score=80.0,
                    speed_bonus=15,
                    total_score=95.0,
                    submission_rank=1,
                    raw_data={},
                    submitted_at=now,
                ),
                Submission(
                    user_id="u2",
                    username="Bob",
                    game_id="wordle",
                    date=today,
                    base_score=70.0,
                    speed_bonus=10,
                    total_score=80.0,
                    submission_rank=2,
                    raw_data={},
                    submitted_at=now,
                ),
                Submission(
                    user_id="u1",
                    username="Alice",
                    game_id="mini",
                    date=today - timedelta(days=2),
                    base_score=60.0,
                    speed_bonus=0,
                    total_score=60.0,
                    submission_rank=1,
                    raw_data={},
                    submitted_at=now,
                ),
            ]
        )
        sess.commit()
    return route_engine


@pytest.fixture
def client(monkeypatch, seeded):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-leaderboard-tests")
    monkeypatch.setenv("SESSION_HTTPS_ONLY", "false")
    from web import main
    from web.routes import leaderboard as leaderboard_route
    from web import deps

    monkeypatch.setattr(leaderboard_route, "_db_session", lambda: Session(seeded))

    async def _fake_admin() -> dict:
        return {"email": "admin@example.com", "role": "admin"}

    main.app.dependency_overrides[deps.require_admin] = _fake_admin
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


class TestLeaderboardRoute:
    def test_no_filters_renders_all_games(self, client: TestClient) -> None:
        response = client.get("/admin/leaderboard")
        assert response.status_code == 200
        body = response.text
        assert "Leaderboard" in body
        assert "Alice" in body
        assert "Bob" in body

    def test_filter_by_game(self, client: TestClient) -> None:
        response = client.get("/admin/leaderboard?game=wordle")
        assert response.status_code == 200
        body = response.text
        assert "Wordle" in body
        assert "Today&#39;s standings" in body or "Today's standings" in body
        assert "Alice" in body
        assert "Bob" in body

    def test_filter_by_period(self, client: TestClient) -> None:
        response = client.get("/admin/leaderboard?period=daily")
        assert response.status_code == 200
        body = response.text
        assert "Alice" in body
        assert "Bob" in body

    def test_filter_by_game_and_period(self, client: TestClient) -> None:
        response = client.get("/admin/leaderboard?game=wordle&period=season")
        assert response.status_code == 200
        body = response.text
        assert "Wordle" in body
        assert "Season" in body

    def test_invalid_period_falls_back_to_alltime(self, client: TestClient) -> None:
        response = client.get("/admin/leaderboard?period=bogus")
        assert response.status_code == 200
        body = response.text
        assert 'value="alltime" selected' in body or 'value="alltime"  selected' in body

    def test_filter_by_empty_game_combo(self, client: TestClient) -> None:
        response = client.get("/admin/leaderboard?game=mini&period=daily")
        assert response.status_code == 200
        body = response.text
        assert "No data for this period/game combination." in body
        assert "No submissions for Mini today." in body

    def test_unknown_game_renders_no_card(self, client: TestClient) -> None:
        response = client.get("/admin/leaderboard?game=does-not-exist")
        assert response.status_code == 200
        body = response.text
        assert "Today&#39;s standings" not in body
        assert "Today's standings" not in body
