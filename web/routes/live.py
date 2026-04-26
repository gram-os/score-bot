from datetime import date as date_type

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from bot.database import Game, Submission
from web.deps import _db_session, require_admin, templates

router = APIRouter()


def _serialize_submission(s, game_name: str) -> dict:
    return {
        "id": s.id,
        "username": s.username,
        "game_id": s.game_id,
        "game_name": game_name,
        "base_score": int(s.base_score),
        "speed_bonus": s.speed_bonus,
        "total_score": int(s.total_score),
        "submission_rank": s.submission_rank,
        "submitted_at": s.submitted_at.strftime("%H:%M:%S") if s.submitted_at else "",
    }


def _fetch_today_submissions(db, today: date_type) -> tuple[list, int]:
    rows = db.execute(
        select(Submission)
        .join(Game, Submission.game_id == Game.id)
        .where(Submission.date == today)
        .order_by(Submission.submitted_at.desc())
        .add_columns(Game.name.label("game_name"))
    ).all()
    last_id = rows[0][0].id if rows else 0
    return [_serialize_submission(s, gn) for s, gn in rows], last_id


@router.get("/live")
async def live_view(
    request: Request,
    session: dict = Depends(require_admin),
):
    today = date_type.today()
    db = _db_session()
    try:
        submissions, last_sub_id = _fetch_today_submissions(db, today)
    finally:
        db.close()
    return templates.TemplateResponse(
        request,
        "live.html",
        {
            "active": "live",
            "submissions": submissions,
            "last_sub_id": last_sub_id,
            "today": today.isoformat(),
        },
    )


@router.get("/live/feed")
async def live_feed(
    after: int = 0,
    session: dict = Depends(require_admin),
):
    today = date_type.today()
    db = _db_session()
    try:
        rows = db.execute(
            select(Submission)
            .join(Game, Submission.game_id == Game.id)
            .where(Submission.date == today, Submission.id > after)
            .order_by(Submission.submitted_at.desc())
            .add_columns(Game.name.label("game_name"))
        ).all()
        submissions = [_serialize_submission(s, gn) for s, gn in rows]
    finally:
        db.close()
    return JSONResponse(submissions)


