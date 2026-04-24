import logging
import os
from urllib.parse import urlencode

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.database import Game, get_engine

log = logging.getLogger(__name__)

templates = Jinja2Templates(directory="web/templates")
PAGE_SIZE = 50


class NotAuthenticated(Exception):
    pass


def _admin_ids() -> set[str]:
    raw = os.environ.get("ADMIN_DISCORD_IDS", "")
    return {uid.strip() for uid in raw.split(",") if uid.strip()}


def _db_session() -> Session:
    engine = get_engine()
    return Session(engine)


async def require_admin(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id or user_id not in _admin_ids():
        raise NotAuthenticated()
    return {"user_id": user_id, "username": request.session.get("username", "")}


def fetch_all_games(db: Session) -> list[Game]:
    return db.execute(select(Game).order_by(Game.name)).scalars().all()


def build_page_url(base_path: str, page: int, **filters: str) -> str:
    params: dict[str, str | int] = {"page": page}
    params.update({k: v for k, v in filters.items() if v})
    return f"{base_path}?{urlencode(params)}"
