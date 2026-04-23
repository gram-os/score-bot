import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from bot.database import Game, Submission, recalculate_game_ranks
from web.deps import _db_session, fetch_all_games, require_admin, templates

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/games")
async def games_list(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        games = fetch_all_games(db)
        counts = {
            row.game_id: row.count
            for row in db.execute(
                select(Submission.game_id, func.count(Submission.id).label("count")).group_by(Submission.game_id)
            ).all()
        }
    finally:
        db.close()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        request,
        "games.html",
        {
            "active": "games",
            "games": games,
            "counts": counts,
            "flash": flash,
        },
    )


@router.post("/games/{game_id}/recalculate")
async def game_recalculate(
    request: Request,
    game_id: str,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        affected = recalculate_game_ranks(db, game_id)
        db.commit()
    finally:
        db.close()
    log.info(
        "Admin %s recalculated ranks for %s (%d date(s))",
        session["username"],
        game_id,
        affected,
    )
    request.session["flash"] = f"Recalculated scores across {affected} date(s) for {game_id}."
    return RedirectResponse(url="/admin/games", status_code=303)


@router.post("/games/{game_id}/toggle")
async def game_toggle(
    request: Request,
    game_id: str,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        game = db.get(Game, game_id)
        if game:
            game.enabled = not game.enabled
            db.commit()
            state = "enabled" if game.enabled else "disabled"
            log.info("Admin %s %s game %s", session["username"], state, game_id)
            request.session["flash"] = f"{game.name} {state}."
    finally:
        db.close()
    return RedirectResponse(url="/admin/games", status_code=303)
