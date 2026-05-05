import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from bot.db import daily_challenge
from bot.db.config import SCORING_TZ
from web.deps import _db_session, fetch_all_games, require_admin, templates

log = logging.getLogger(__name__)
router = APIRouter()

_DAILY_CHALLENGE_PATH = "/daily-challenge"


def _today_et() -> "datetime.date":
    return datetime.now(SCORING_TZ).date()


def _render(request: Request, db, flash: str | None = None):
    today = _today_et()
    games = fetch_all_games(db)
    enabled_games = [g for g in games if g.enabled]
    today_game_id = daily_challenge.get_today_game_id(db, today)
    today_game_name = next((g.name for g in games if g.id == today_game_id), None)
    return templates.TemplateResponse(
        request,
        "daily_challenge.html",
        {
            "active": "daily_challenge",
            "flash": flash,
            "enabled": daily_challenge.is_enabled(db),
            "mode": daily_challenge.get_mode(db),
            "multiplier": daily_challenge.get_multiplier(db),
            "today": today,
            "today_game_id": today_game_id,
            "today_game_name": today_game_name,
            "enabled_games": enabled_games,
        },
    )


@router.get(_DAILY_CHALLENGE_PATH)
async def daily_challenge_view(request: Request, session: dict = Depends(require_admin)):
    db = _db_session()
    try:
        flash = request.session.pop("flash", None)
        return _render(request, db, flash)
    finally:
        db.close()


@router.post(_DAILY_CHALLENGE_PATH + "/toggle")
async def daily_challenge_toggle(
    request: Request,
    enabled: str = Form(""),
    admin_session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        new_enabled = enabled.lower() == "true"
        daily_challenge.set_enabled(db, new_enabled)
        db.commit()
    finally:
        db.close()
    log.info("Admin %s set daily_challenge.enabled=%s", admin_session["email"], new_enabled)
    request.session["flash"] = f"Daily challenge {'enabled' if new_enabled else 'disabled'}."
    return RedirectResponse(url="/admin" + _DAILY_CHALLENGE_PATH, status_code=303)


@router.post(_DAILY_CHALLENGE_PATH + "/mode")
async def daily_challenge_set_mode(
    request: Request,
    mode: str = Form(...),
    admin_session: dict = Depends(require_admin),
):
    if mode not in ("manual", "random"):
        request.session["flash"] = f"Invalid mode: {mode}"
        return RedirectResponse(url="/admin" + _DAILY_CHALLENGE_PATH, status_code=303)
    db = _db_session()
    try:
        daily_challenge.set_mode(db, mode)
        db.commit()
    finally:
        db.close()
    log.info("Admin %s set daily_challenge.mode=%s", admin_session["email"], mode)
    request.session["flash"] = f"Mode set to {mode}."
    return RedirectResponse(url="/admin" + _DAILY_CHALLENGE_PATH, status_code=303)


@router.post(_DAILY_CHALLENGE_PATH + "/multiplier")
async def daily_challenge_set_multiplier(
    request: Request,
    multiplier: float = Form(...),
    admin_session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        try:
            daily_challenge.set_multiplier(db, multiplier)
            db.commit()
            request.session["flash"] = f"Multiplier set to {multiplier}."
        except ValueError as e:
            db.rollback()
            request.session["flash"] = f"Invalid multiplier: {e}"
    finally:
        db.close()
    log.info("Admin %s set daily_challenge.multiplier=%s", admin_session["email"], multiplier)
    return RedirectResponse(url="/admin" + _DAILY_CHALLENGE_PATH, status_code=303)


@router.post(_DAILY_CHALLENGE_PATH + "/manual-pick")
async def daily_challenge_manual_pick(
    request: Request,
    game_id: str = Form(...),
    admin_session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        if daily_challenge.get_mode(db) != "manual":
            request.session["flash"] = "Manual pick is only available in manual mode."
            return RedirectResponse(url="/admin" + _DAILY_CHALLENGE_PATH, status_code=303)
        daily_challenge.set_today_game_id(db, game_id, _today_et())
        db.commit()
    finally:
        db.close()
    log.info("Admin %s manually picked daily challenge: %s", admin_session["email"], game_id)
    request.session["flash"] = f"Today's challenge set to {game_id}."
    return RedirectResponse(url="/admin" + _DAILY_CHALLENGE_PATH, status_code=303)


@router.post(_DAILY_CHALLENGE_PATH + "/reroll")
async def daily_challenge_reroll(
    request: Request,
    admin_session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        chosen = daily_challenge.roll_random_game(db, _today_et())
        db.commit()
    finally:
        db.close()
    log.info("Admin %s re-rolled daily challenge: %s", admin_session["email"], chosen)
    request.session["flash"] = f"Random pick: {chosen or 'none (no enabled games)'}."
    return RedirectResponse(url="/admin" + _DAILY_CHALLENGE_PATH, status_code=303)
