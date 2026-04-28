from datetime import date, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as SASession

from bot.database import get_kpi_today, get_logs
from bot.db.models import Season, get_engine
from bot.db.season_stats import get_season_leaderboard
from web.deps import require_admin, templates

router = APIRouter()


def _db_session() -> SASession:
    return SASession(get_engine())


def _format_error_log(entry) -> dict:
    ts = entry.timestamp.replace(tzinfo=timezone.utc)
    return {
        "timestamp_str": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "logger": entry.logger,
        "message": entry.message,
    }


def _get_featured_season(db: SASession) -> Season | None:
    today = date.today()
    active = db.execute(
        select(Season).where(Season.start_date <= today, Season.end_date >= today).limit(1)
    ).scalar_one_or_none()
    if active:
        return active
    return db.execute(
        select(Season).where(Season.end_date < today).order_by(Season.end_date.desc()).limit(1)
    ).scalar_one_or_none()


@router.get("/dashboard")
async def dashboard_view(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        kpi = get_kpi_today(db)
        error_rows, error_total = get_logs(db, level="ERROR", limit=5)
        recent_errors = [_format_error_log(e) for e in error_rows]
        season = _get_featured_season(db)
        season_top3 = get_season_leaderboard(db, season)[:3] if season else []
    finally:
        db.close()

    today = date.today()
    season_is_active = bool(season and season.start_date <= today <= season.end_date)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "active": "dashboard",
            "kpi": kpi,
            "recent_errors": recent_errors,
            "error_total": error_total,
            "season": season,
            "season_is_active": season_is_active,
            "season_top3": season_top3,
        },
    )
