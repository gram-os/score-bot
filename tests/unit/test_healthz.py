import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.unit


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-healthz-tests")
    monkeypatch.setenv("SESSION_HTTPS_ONLY", "false")
    from web import main

    return TestClient(main.app)


def test_healthz_returns_ok_when_db_reachable(client: TestClient, monkeypatch) -> None:
    from web import main

    monkeypatch.setattr(main, "_ping_database", lambda: None)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_returns_503_when_db_unreachable(client: TestClient, monkeypatch) -> None:
    from web import main

    def _raise() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "_ping_database", _raise)

    response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json() == {"status": "db-unreachable"}
