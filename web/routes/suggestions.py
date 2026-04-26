from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select

from bot.database import GameSuggestion
from web.deps import _db_session, require_admin, templates

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
        {"active": "suggestions", "suggestions": suggestions},
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
