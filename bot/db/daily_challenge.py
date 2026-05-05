from __future__ import annotations

import random
from datetime import date
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.db.config import get_config, set_config
from bot.db.models import Game

Mode = Literal["manual", "random"]

KEY_ENABLED = "daily_challenge.enabled"
KEY_MODE = "daily_challenge.mode"
KEY_MULTIPLIER = "daily_challenge.multiplier"
KEY_TODAY_GAME_ID = "daily_challenge.today_game_id"
KEY_TODAY_DATE = "daily_challenge.today_date"

DEFAULT_MULTIPLIER = 2.0


def is_enabled(session: Session) -> bool:
    return get_config(session, KEY_ENABLED, "false").lower() == "true"


def set_enabled(session: Session, enabled: bool) -> None:
    set_config(session, KEY_ENABLED, "true" if enabled else "false")


def get_mode(session: Session) -> Mode:
    value = get_config(session, KEY_MODE, "random").lower()
    if value not in ("manual", "random"):
        return "random"
    return value  # type: ignore[return-value]


def set_mode(session: Session, mode: Mode) -> None:
    if mode not in ("manual", "random"):
        raise ValueError(f"invalid mode: {mode}")
    set_config(session, KEY_MODE, mode)


def get_multiplier(session: Session) -> float:
    raw = get_config(session, KEY_MULTIPLIER, str(DEFAULT_MULTIPLIER))
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_MULTIPLIER


def set_multiplier(session: Session, multiplier: float) -> None:
    if multiplier <= 0:
        raise ValueError("multiplier must be > 0")
    set_config(session, KEY_MULTIPLIER, str(float(multiplier)))


def get_today_game_id(session: Session, today: date) -> str | None:
    stored_date = get_config(session, KEY_TODAY_DATE, "")
    if stored_date != today.isoformat():
        return None
    game_id = get_config(session, KEY_TODAY_GAME_ID, "")
    return game_id or None


def set_today_game_id(session: Session, game_id: str | None, today: date) -> None:
    set_config(session, KEY_TODAY_GAME_ID, game_id or "")
    set_config(session, KEY_TODAY_DATE, today.isoformat())


def _enabled_game_ids(session: Session) -> list[str]:
    rows = session.scalars(select(Game.id).where(Game.enabled.is_(True))).all()
    return list(rows)


def roll_random_game(session: Session, today: date) -> str | None:
    candidates = _enabled_game_ids(session)
    if not candidates:
        set_today_game_id(session, None, today)
        return None
    chosen = random.choice(candidates)
    set_today_game_id(session, chosen, today)
    return chosen
