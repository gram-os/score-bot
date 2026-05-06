import logging
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from bot.db import audit
from bot.db.models import Season, get_engine
from bot.db.season_stats import (
    get_season_daily_activity,
    get_season_game_breakdown,
    get_season_leaderboard,
    get_season_stats,
    get_seasons_summary,
)
from sqlalchemy.orm import Session as SASession
from web.deps import require_admin, templates

log = logging.getLogger(__name__)
router = APIRouter()


def _db():
    session = SASession(get_engine())
    try:
        yield session
    finally:
        session.close()


def _db_session():
    return SASession(get_engine())


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _overlapping_season(db: SASession, start: date, end: date, exclude_id: int | None = None) -> Season | None:
    stmt = select(Season).where(Season.start_date <= end, Season.end_date >= start)
    if exclude_id is not None:
        stmt = stmt.where(Season.id != exclude_id)
    return db.execute(stmt).scalars().first()


@router.get("/seasons")
async def seasons_list(request: Request, session: dict = Depends(require_admin)):
    db = _db_session()
    try:
        summaries = get_seasons_summary(db)
    finally:
        db.close()
    return templates.TemplateResponse(
        request,
        "seasons.html",
        {
            "active": "seasons",
            "summaries": summaries,
            "today": date.today(),
            "flash": request.query_params.get("flash"),
            "error": request.query_params.get("error"),
        },
    )


@router.get("/seasons/{season_id}")
async def season_detail(request: Request, season_id: int, session: dict = Depends(require_admin)):
    db = _db_session()
    try:
        season = db.get(Season, season_id)
        if not season:
            return RedirectResponse("/admin/seasons?error=Season+not+found", status_code=302)
        stats = get_season_stats(db, season)
        leaderboard = get_season_leaderboard(db, season)
        game_breakdown = get_season_game_breakdown(db, season)
        daily_activity = get_season_daily_activity(db, season)
    finally:
        db.close()

    today = date.today()
    is_current = season.start_date <= today <= season.end_date
    is_future = season.start_date > today

    return templates.TemplateResponse(
        request,
        "season_detail.html",
        {
            "active": "seasons",
            "season": season,
            "stats": stats,
            "leaderboard": leaderboard,
            "game_breakdown": game_breakdown,
            "daily_activity": [{"date": p.date, "count": p.count} for p in daily_activity],
            "is_current": is_current,
            "is_future": is_future,
            "today": today,
            "flash": request.query_params.get("flash"),
        },
    )


@router.post("/seasons/create")
async def season_create(request: Request, session: dict = Depends(require_admin)):
    form = await request.form()
    name = (form.get("name") or "").strip()
    start = _parse_date(form.get("start_date", ""))
    end = _parse_date(form.get("end_date", ""))

    if not name or not start or not end:
        return RedirectResponse("/admin/seasons?error=All+fields+required", status_code=302)
    if end < start:
        return RedirectResponse("/admin/seasons?error=End+date+must+be+after+start+date", status_code=302)

    db = _db_session()
    try:
        conflict = _overlapping_season(db, start, end)
        if conflict:
            return RedirectResponse(
                f"/admin/seasons?error=Dates+overlap+with+existing+season+%22{conflict.name}%22",
                status_code=302,
            )
        new_season = Season(name=name, start_date=start, end_date=end)
        db.add(new_season)
        db.flush()
        audit.record(
            db,
            actor_email=session["email"],
            actor_role=session.get("role", "admin"),
            action="season.created",
            target_type="season",
            target_id=str(new_season.id),
            details={"name": name, "start": start.isoformat(), "end": end.isoformat()},
        )
        db.commit()
        log.info("Season created: %s (%s – %s) by %s", name, start, end, session.get("email"))
    finally:
        db.close()

    return RedirectResponse(f"/admin/seasons?flash=Season+%22{name}%22+created", status_code=302)


@router.post("/seasons/{season_id}/edit")
async def season_edit(request: Request, season_id: int, session: dict = Depends(require_admin)):
    form = await request.form()
    name = (form.get("name") or "").strip()
    start = _parse_date(form.get("start_date", ""))
    end = _parse_date(form.get("end_date", ""))

    if not name or not start or not end:
        return RedirectResponse(f"/admin/seasons/{season_id}?flash=All+fields+required", status_code=302)
    if end < start:
        return RedirectResponse(f"/admin/seasons/{season_id}?flash=End+date+must+be+after+start+date", status_code=302)

    db = _db_session()
    try:
        s = db.get(Season, season_id)
        if not s:
            return RedirectResponse("/admin/seasons?error=Season+not+found", status_code=302)
        conflict = _overlapping_season(db, start, end, exclude_id=season_id)
        if conflict:
            return RedirectResponse(
                f"/admin/seasons/{season_id}?flash=Dates+overlap+with+existing+season+%22{conflict.name}%22",
                status_code=302,
            )
        old = {"name": s.name, "start": s.start_date.isoformat(), "end": s.end_date.isoformat()}
        s.name = name
        s.start_date = start
        s.end_date = end
        audit.record(
            db,
            actor_email=session["email"],
            actor_role=session.get("role", "admin"),
            action="season.edited",
            target_type="season",
            target_id=str(season_id),
            details={"old": old, "new": {"name": name, "start": start.isoformat(), "end": end.isoformat()}},
        )
        db.commit()
        log.info("Season %s updated by %s", season_id, session.get("email"))
    finally:
        db.close()

    return RedirectResponse(f"/admin/seasons/{season_id}?flash=Season+updated", status_code=302)


@router.post("/seasons/{season_id}/delete")
async def season_delete(request: Request, season_id: int, session: dict = Depends(require_admin)):
    db = _db_session()
    try:
        s = db.get(Season, season_id)
        if s:
            name = s.name
            audit.record(
                db,
                actor_email=session["email"],
                actor_role=session.get("role", "admin"),
                action="season.deleted",
                target_type="season",
                target_id=str(season_id),
                details={"name": name, "start": s.start_date.isoformat(), "end": s.end_date.isoformat()},
            )
            db.delete(s)
            db.commit()
            log.info("Season %s (%s) deleted by %s", season_id, name, session.get("email"))
    finally:
        db.close()
    return RedirectResponse("/admin/seasons?flash=Season+deleted", status_code=302)
