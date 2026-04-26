from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from bot.database import (
    get_game_difficulty_comparison,
    get_kpi_today,
    get_speed_bonus_leaders,
)
from web.deps import _db_session, require_admin, templates

router = APIRouter()


@router.get("/stats")
async def stats_dashboard(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        kpi = get_kpi_today(db)
        speed_leaders = get_speed_bonus_leaders(db, limit=5)
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "active": "stats",
            "kpi": kpi,
            "speed_leaders": speed_leaders,
        },
    )


@router.get("/stats/difficulty")
async def stats_difficulty(session: dict = Depends(require_admin)):
    db = _db_session()
    try:
        rows = get_game_difficulty_comparison(db)
    finally:
        db.close()

    return JSONResponse(
        [
            {
                "game": row.game_name,
                "avg_base_score": row.avg_base_score,
                "submission_count": row.submission_count,
            }
            for row in rows
        ]
    )
