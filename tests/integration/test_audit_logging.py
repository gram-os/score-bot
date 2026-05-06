from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from bot.database import AuditLog, Base, Game, Submission, User
from bot.db import audit


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
                User(user_id="u1", username="Alice", updated_at=now),
            ]
        )
        sess.flush()
        sess.add(
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
            )
        )
        sess.commit()
    return route_engine


@pytest.fixture
def client(monkeypatch, seeded):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-audit-tests")
    monkeypatch.setenv("SESSION_HTTPS_ONLY", "false")
    from web import deps, main
    from web.routes import daily_challenge as dc_route
    from web.routes import games as games_route
    from web.routes import submissions as submissions_route

    monkeypatch.setattr(submissions_route, "_db_session", lambda: Session(seeded))
    monkeypatch.setattr(games_route, "_db_session", lambda: Session(seeded))
    monkeypatch.setattr(dc_route, "_db_session", lambda: Session(seeded))

    async def _fake_admin() -> dict:
        return {"email": "admin@example.com", "role": "admin"}

    main.app.dependency_overrides[deps.require_admin] = _fake_admin
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def _audit_rows(engine) -> list[AuditLog]:
    with Session(engine) as sess:
        return audit.list_recent(sess)


class TestAuditLogging:
    def test_submission_delete_records_audit(self, client: TestClient, seeded) -> None:
        with Session(seeded) as s:
            sub = s.query(Submission).first()
            sub_id = sub.id

        client.post(f"/admin/submissions/{sub_id}/delete", follow_redirects=False)

        rows = _audit_rows(seeded)
        assert any(r.action == "submission.deleted" and r.target_id == str(sub_id) for r in rows)
        deleted = next(r for r in rows if r.action == "submission.deleted")
        assert deleted.actor_email == "admin@example.com"
        assert "wordle" in deleted.details_json

    def test_game_toggle_records_audit(self, client: TestClient, seeded) -> None:
        client.post("/admin/games/wordle/toggle", follow_redirects=False)
        rows = _audit_rows(seeded)
        assert any(r.action == "game.toggled" and r.target_id == "wordle" for r in rows)

    def test_daily_challenge_toggle_records_audit(self, client: TestClient, seeded) -> None:
        client.post("/admin/daily-challenge/toggle", data={"enabled": "true"}, follow_redirects=False)
        rows = _audit_rows(seeded)
        toggled = [r for r in rows if r.action == "daily_challenge.toggled"]
        assert len(toggled) == 1
        assert toggled[0].actor_email == "admin@example.com"
