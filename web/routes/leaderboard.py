from fastapi import APIRouter, Depends, Request

from bot.database import get_leaderboard
from web.deps import _db_session, fetch_all_games, require_admin, templates

router = APIRouter()


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
