from fastapi import APIRouter, Depends, Request

from bot.database import get_all_feedback
from web.deps import _db_session, require_admin, templates

router = APIRouter()


def _serialize(f) -> dict:
    return {
        "id": f.id,
        "username": f.username,
        "category": f.category,
        "content": f.content,
        "submitted_at": f.submitted_at.strftime("%Y-%m-%d %H:%M") if f.submitted_at else "",
    }


@router.get("/feedback")
async def feedback_view(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        rows = get_all_feedback(db)
        entries = [_serialize(f) for f in rows]
    finally:
        db.close()
    return templates.TemplateResponse(
        request,
        "feedback.html",
        {"active": "feedback", "entries": entries},
    )
