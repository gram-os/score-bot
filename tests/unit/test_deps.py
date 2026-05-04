import asyncio
from unittest.mock import MagicMock, patch

import jwt
import pytest

from web import deps
from web.deps import NotAuthenticated, require_admin, verify_cf_jwt


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_singleton():
    deps._jwks_client = None
    yield
    deps._jwks_client = None


@pytest.fixture
def cf_env(monkeypatch):
    monkeypatch.setenv("CF_AUD", "test-aud")
    monkeypatch.setenv("CF_TEAM_DOMAIN", "https://team.cloudflareaccess.com")


def _fake_signing_key() -> object:
    sk = MagicMock()
    sk.key = "fake-key-material"
    return sk


def test_verify_cf_jwt_retries_after_signature_error(cf_env):
    first_client = MagicMock()
    first_client.get_signing_key_from_jwt.return_value = _fake_signing_key()
    second_client = MagicMock()
    second_client.get_signing_key_from_jwt.return_value = _fake_signing_key()

    clients = iter([first_client, second_client])

    def fake_pyjwk_client(*args, **kwargs):
        return next(clients)

    expected_payload = {"email": "user@example.com"}
    decode_calls: list[int] = []

    def fake_decode(*args, **kwargs):
        decode_calls.append(1)
        if len(decode_calls) == 1:
            assert deps._jwks_client is first_client
            raise jwt.InvalidSignatureError("rotated")
        assert deps._jwks_client is second_client
        return expected_payload

    with (
        patch.object(deps, "PyJWKClient", side_effect=fake_pyjwk_client),
        patch.object(deps.jwt, "decode", side_effect=fake_decode),
    ):
        result = asyncio.run(verify_cf_jwt("fake-token"))

    assert result == expected_payload
    assert len(decode_calls) == 2
    assert deps._jwks_client is second_client
    assert first_client.get_signing_key_from_jwt.call_count == 1
    assert second_client.get_signing_key_from_jwt.call_count == 1


def test_verify_cf_jwt_does_not_retry_more_than_once(cf_env):
    client_a = MagicMock()
    client_a.get_signing_key_from_jwt.return_value = _fake_signing_key()
    client_b = MagicMock()
    client_b.get_signing_key_from_jwt.return_value = _fake_signing_key()

    clients = iter([client_a, client_b])

    def fake_pyjwk_client(*args, **kwargs):
        return next(clients)

    def always_fail(*args, **kwargs):
        raise jwt.InvalidSignatureError("still bad")

    with (
        patch.object(deps, "PyJWKClient", side_effect=fake_pyjwk_client),
        patch.object(deps.jwt, "decode", side_effect=always_fail),
    ):
        with pytest.raises(jwt.InvalidSignatureError):
            asyncio.run(verify_cf_jwt("fake-token"))


def test_require_admin_propagates_runtime_error_on_misconfig(monkeypatch):
    monkeypatch.delenv("CF_AUD", raising=False)
    monkeypatch.setenv("CF_TEAM_DOMAIN", "https://team.cloudflareaccess.com")

    request = MagicMock()
    request.headers.get.return_value = "some-token"
    request.session = {}

    with pytest.raises(RuntimeError, match="CF_AUD and CF_TEAM_DOMAIN must be set"):
        asyncio.run(require_admin(request))


def test_require_admin_returns_401_on_jwt_error(cf_env):
    fake_client = MagicMock()
    fake_client.get_signing_key_from_jwt.return_value = _fake_signing_key()

    request = MagicMock()
    request.headers.get.return_value = "bad-token"
    request.session = {}

    with (
        patch.object(deps, "PyJWKClient", return_value=fake_client),
        patch.object(deps.jwt, "decode", side_effect=jwt.InvalidTokenError("nope")),
    ):
        with pytest.raises(NotAuthenticated):
            asyncio.run(require_admin(request))
