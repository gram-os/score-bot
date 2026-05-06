from fastapi import APIRouter, Depends, Request

from bot.db.analytics import get_game_dropoff_rates, get_user_health_breakdown, get_weekly_active_users
from web.deps import _db_session, require_admin, templates

router = APIRouter()


@router.get("/retention")
async def retention_dashboard(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        weekly = get_weekly_active_users(db, weeks=8)
        health = get_user_health_breakdown(db)
        dropoff = get_game_dropoff_rates(db)
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "retention.html",
        {
            "active": "retention",
            "weekly": weekly,
            "health": health,
            "dropoff": dropoff,
        },
    )
