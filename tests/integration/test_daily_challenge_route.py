from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from bot.database import Base, Game
from bot.db import daily_challenge


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
    with Session(route_engine) as sess:
        sess.add_all(
            [
                Game(id="wordle", name="Wordle", enabled=True, created_at=now),
                Game(id="connections", name="Connections", enabled=True, created_at=now),
                Game(id="disabled_one", name="Disabled", enabled=False, created_at=now),
            ]
        )
        sess.commit()
    return route_engine


@pytest.fixture
def client(monkeypatch, seeded):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-daily-challenge-tests")
    monkeypatch.setenv("SESSION_HTTPS_ONLY", "false")
    from web import deps, main
    from web.routes import daily_challenge as dc_route

    monkeypatch.setattr(dc_route, "_db_session", lambda: Session(seeded))

    async def _fake_admin() -> dict:
        return {"email": "admin@example.com", "role": "admin"}

    main.app.dependency_overrides[deps.require_admin] = _fake_admin
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


class TestDailyChallengeRoute:
    def test_view_renders_default_disabled(self, client: TestClient) -> None:
        response = client.get("/admin/daily-challenge")
        assert response.status_code == 200
        assert "Daily Challenge" in response.text
        assert "no" in response.text.lower()  # default state shows "no"

    def test_toggle_enables_then_disables(self, client: TestClient, seeded) -> None:
        r1 = client.post("/admin/daily-challenge/toggle", data={"enabled": "true"}, follow_redirects=False)
        assert r1.status_code == 303
        with Session(seeded) as s:
            assert daily_challenge.is_enabled(s) is True

        r2 = client.post("/admin/daily-challenge/toggle", data={"enabled": "false"}, follow_redirects=False)
        assert r2.status_code == 303
        with Session(seeded) as s:
            assert daily_challenge.is_enabled(s) is False

    def test_set_mode_persists(self, client: TestClient, seeded) -> None:
        r = client.post("/admin/daily-challenge/mode", data={"mode": "manual"}, follow_redirects=False)
        assert r.status_code == 303
        with Session(seeded) as s:
            assert daily_challenge.get_mode(s) == "manual"

    def test_set_mode_rejects_invalid(self, client: TestClient, seeded) -> None:
        r = client.post("/admin/daily-challenge/mode", data={"mode": "garbage"}, follow_redirects=False)
        assert r.status_code == 303
        with Session(seeded) as s:
            assert daily_challenge.get_mode(s) == "random"  # unchanged

    def test_set_multiplier_persists(self, client: TestClient, seeded) -> None:
        r = client.post("/admin/daily-challenge/multiplier", data={"multiplier": "3.5"}, follow_redirects=False)
        assert r.status_code == 303
        with Session(seeded) as s:
            assert daily_challenge.get_multiplier(s) == 3.5

    def test_set_multiplier_rejects_zero(self, client: TestClient, seeded) -> None:
        with Session(seeded) as s:
            daily_challenge.set_multiplier(s, 2.0)
            s.commit()
        r = client.post("/admin/daily-challenge/multiplier", data={"multiplier": "0"}, follow_redirects=False)
        assert r.status_code == 303
        with Session(seeded) as s:
            assert daily_challenge.get_multiplier(s) == 2.0  # unchanged

    def test_manual_pick_only_in_manual_mode(self, client: TestClient, seeded) -> None:
        # mode defaults to random — manual-pick should be rejected
        r = client.post("/admin/daily-challenge/manual-pick", data={"game_id": "wordle"}, follow_redirects=False)
        assert r.status_code == 303
        # switch to manual then pick
        client.post("/admin/daily-challenge/mode", data={"mode": "manual"})
        r2 = client.post("/admin/daily-challenge/manual-pick", data={"game_id": "wordle"}, follow_redirects=False)
        assert r2.status_code == 303
        with Session(seeded) as s:
            from datetime import datetime as _dt

            from bot.db.config import SCORING_TZ

            today = _dt.now(SCORING_TZ).date()
            assert daily_challenge.get_today_game_id(s, today) == "wordle"

    def test_reroll_picks_an_enabled_game(self, client: TestClient, seeded) -> None:
        r = client.post("/admin/daily-challenge/reroll", follow_redirects=False)
        assert r.status_code == 303
        with Session(seeded) as s:
            from datetime import datetime as _dt

            from bot.db.config import SCORING_TZ

            today = _dt.now(SCORING_TZ).date()
            chosen = daily_challenge.get_today_game_id(s, today)
            assert chosen in ("wordle", "connections")
