import logging
import os
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Request
from fastapi.templating import Jinja2Templates
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


class NotAuthenticated(Exception):
    pass


def _admin_ids() -> set[str]:
    raw = os.environ.get("ADMIN_DISCORD_IDS", "")
    return {uid.strip() for uid in raw.split(",") if uid.strip()}


def _homunculus_viewer_ids() -> set[str]:
    raw = os.environ.get("HOMUNCULUS_VIEWER_IDS", "")
    return {uid.strip() for uid in raw.split(",") if uid.strip()}


def _db_session() -> Session:
    engine = get_engine()
    return Session(engine)


async def require_admin(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id or user_id not in _admin_ids():
        raise NotAuthenticated()
    return {"user_id": user_id, "username": request.session.get("username", ""), "role": "admin"}


async def require_homunculus_access(request: Request) -> dict:
    user_id = request.session.get("user_id")
    role = request.session.get("role", "")
    if not user_id or role not in ("admin", "homunculus_viewer"):
        raise NotAuthenticated()
    return {"user_id": user_id, "username": request.session.get("username", ""), "role": role}


def fetch_all_games(db: Session) -> list[Game]:
    return db.execute(select(Game).order_by(Game.name)).scalars().all()


def build_page_url(base_path: str, page: int, **filters: str) -> str:
    params: dict[str, str | int] = {"page": page}
    params.update({k: v for k, v in filters.items() if v})
    return f"{base_path}?{urlencode(params)}"
