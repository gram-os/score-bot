import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select

from bot.database import Game, GameSuggestion
from web.deps import _db_session, require_admin, templates

log = logging.getLogger(__name__)

router = APIRouter()

_VALID_STATUSES = {"pending", "polled", "accepted", "rejected"}


def _serialize(s: GameSuggestion) -> dict:
    return {
        "id": s.id,
        "username": s.username,
        "game_name": s.game_name,
        "description": s.description or "",
        "status": s.status,
        "suggested_at": s.suggested_at.strftime("%Y-%m-%d %H:%M") if s.suggested_at else "",
    }


@router.get("/suggestions")
async def suggestions_view(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        rows = db.execute(select(GameSuggestion).order_by(GameSuggestion.suggested_at.desc())).scalars().all()
        suggestions = [_serialize(s) for s in rows]
    finally:
        db.close()
    return templates.TemplateResponse(
        request,
        "suggestions.html",
        {
            "active": "suggestions",
            "suggestions": suggestions,
            "flash": request.query_params.get("flash"),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/suggestions/{suggestion_id}/status")
async def update_suggestion_status(
    suggestion_id: int,
    status: str = Form(...),
    session: dict = Depends(require_admin),
):
    if status not in _VALID_STATUSES:
        return JSONResponse({"error": "invalid status"}, status_code=400)
    db = _db_session()
    try:
        suggestion = db.get(GameSuggestion, suggestion_id)
        if not suggestion:
            return JSONResponse({"error": "not found"}, status_code=404)
        suggestion.status = status
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/admin/suggestions", status_code=303)


@router.post("/suggestions/{suggestion_id}/promote")
async def promote_suggestion(
    request: Request,
    suggestion_id: int,
    game_id: str = Form(...),
    game_name: str = Form(...),
    session: dict = Depends(require_admin),
):
    game_id = game_id.strip().lower()
    game_name = game_name.strip()
    if not game_id or not game_name:
        return RedirectResponse("/admin/suggestions?error=Game+ID+and+name+are+required", status_code=303)

    db = _db_session()
    try:
        suggestion = db.get(GameSuggestion, suggestion_id)
        if not suggestion:
            return RedirectResponse("/admin/suggestions?error=Suggestion+not+found", status_code=303)
        if db.get(Game, game_id):
            return RedirectResponse(f"/admin/suggestions?error=Game+ID+%22{game_id}%22+already+exists", status_code=303)
        db.add(Game(id=game_id, name=game_name, enabled=True))
        suggestion.status = "accepted"
        db.commit()
        log.info(
            "Admin %s promoted suggestion %s to game %s (%s)",
            session.get("email"),
            suggestion_id,
            game_id,
            game_name,
        )
    finally:
        db.close()
    return RedirectResponse(f"/admin/games/{game_id}?flash=Game+created+from+suggestion", status_code=303)
