import asyncio
import logging
import os
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jwt
from fastapi import Request
from fastapi.templating import Jinja2Templates
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.database import Game, get_config, get_engine

DISPLAY_TIMEZONES = [
    ("UTC", "UTC"),
    ("America/New_York", "Eastern Time (ET)"),
    ("America/Chicago", "Central Time (CT)"),
    ("America/Denver", "Mountain Time (MT)"),
    ("America/Los_Angeles", "Pacific Time (PT)"),
    ("America/Anchorage", "Alaska Time (AKT)"),
    ("Pacific/Honolulu", "Hawaii Time (HT)"),
    ("America/Phoenix", "Arizona (MST, no DST)"),
    ("Europe/London", "London (GMT/BST)"),
    ("Europe/Paris", "Paris (CET/CEST)"),
    ("Europe/Berlin", "Berlin (CET/CEST)"),
    ("Asia/Tokyo", "Tokyo (JST)"),
    ("Asia/Singapore", "Singapore (SGT)"),
    ("Asia/Seoul", "Seoul (KST)"),
    ("Asia/Shanghai", "Shanghai (CST)"),
    ("Australia/Sydney", "Sydney (AEST/AEDT)"),
]


def get_display_tz(db: Session) -> ZoneInfo:
    tz_name = get_config(db, "display_timezone", "America/New_York")
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        return ZoneInfo("America/New_York")


log = logging.getLogger(__name__)

templates = Jinja2Templates(directory="web/templates")
PAGE_SIZE = 50

_jwks_client: PyJWKClient | None = None


class NotAuthenticated(Exception):
    pass


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        cf_team_domain = os.environ.get("CF_TEAM_DOMAIN", "")
        if not cf_team_domain:
            raise RuntimeError("CF_TEAM_DOMAIN must be set")
        _jwks_client = PyJWKClient(f"{cf_team_domain}/cdn-cgi/access/certs", cache_keys=True)
    return _jwks_client


def _admin_emails() -> set[str]:
    raw = os.environ.get("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _homunculus_viewer_emails() -> set[str]:
    raw = os.environ.get("HOMUNCULUS_VIEWER_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _db_session() -> Session:
    engine = get_engine()
    return Session(engine)


async def verify_cf_jwt(token: str) -> dict:
    cf_aud = os.environ.get("CF_AUD", "")
    cf_team_domain = os.environ.get("CF_TEAM_DOMAIN", "")
    if not cf_aud or not cf_team_domain:
        raise RuntimeError("CF_AUD and CF_TEAM_DOMAIN must be set")
    client = _get_jwks_client()
    loop = asyncio.get_event_loop()
    signing_key = await loop.run_in_executor(None, client.get_signing_key_from_jwt, token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=cf_aud,
        issuer=cf_team_domain,
    )


async def require_admin(request: Request) -> dict:
    token = request.headers.get("Cf-Access-Jwt-Assertion", "")
    if not token:
        raise NotAuthenticated()
    try:
        payload = await verify_cf_jwt(token)
    except Exception:
        log.warning("CF JWT verification failed for admin route")
        raise NotAuthenticated()
    email = payload.get("email", "").lower()
    if email not in _admin_emails():
        log.warning("Unauthorized access attempt by %s", email)
        raise NotAuthenticated()
    request.session["role"] = "admin"
    request.session["email"] = email
    return {"email": email, "role": "admin"}


async def require_homunculus_access(request: Request) -> dict:
    token = request.headers.get("Cf-Access-Jwt-Assertion", "")
    if not token:
        raise NotAuthenticated()
    try:
        payload = await verify_cf_jwt(token)
    except Exception:
        log.warning("CF JWT verification failed for homunculus route")
        raise NotAuthenticated()
    email = payload.get("email", "").lower()
    if email in _admin_emails():
        role = "admin"
    elif email in _homunculus_viewer_emails():
        role = "homunculus_viewer"
    else:
        log.warning("Unauthorized access attempt by %s", email)
        raise NotAuthenticated()
    request.session["role"] = role
    request.session["email"] = email
    return {"email": email, "role": role}


def fetch_all_games(db: Session) -> list[Game]:
    return db.execute(select(Game).order_by(Game.name)).scalars().all()


def build_page_url(base_path: str, page: int, **filters: str) -> str:
    params: dict[str, str | int] = {"page": page}
    params.update({k: v for k, v in filters.items() if v})
    return f"{base_path}?{urlencode(params)}"
