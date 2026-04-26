from datetime import date as date_type, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from bot.database import Game, Submission, get_leaderboard
from web.deps import _db_session, fetch_all_games, require_admin, templates

router = APIRouter()


@router.get("/stats/submissions")
async def stats_submissions(
    days: int = Query(default=30),
    session: dict = Depends(require_admin),
):
    if days not in (7, 30, 90):
        days = 30
    cutoff = date_type.today() - timedelta(days=days)

    db = _db_session()
    try:
        rows = db.execute(
            select(
                Submission.date,
                Submission.game_id,
                Game.name.label("game_name"),
                func.count(Submission.id).label("count"),
            )
            .join(Game, Submission.game_id == Game.id)
            .where(Submission.date >= cutoff)
            .group_by(Submission.game_id, Game.name, Submission.date)
            .order_by(Submission.date.asc(), Game.name.asc())
        ).all()
    finally:
        db.close()

    return JSONResponse(
        [
            {
                "date": str(row.date),
                "game_id": row.game_id,
                "game": row.game_name,
                "count": row.count,
            }
            for row in rows
        ]
    )


@router.get("/leaderboard")
async def leaderboard_view(
    request: Request,
    period: str = "weekly",
    game: str = "",
    session: dict = Depends(require_admin),
):
    if period not in ("daily", "weekly", "monthly", "alltime"):
        period = "weekly"

    db = _db_session()
    try:
        games = fetch_all_games(db)
        rows = get_leaderboard(db, period, game_id=game or None)
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "leaderboard.html",
        {
            "active": "leaderboard",
            "rows": rows,
            "games": games,
            "period": period,
            "game": game,
        },
    )
