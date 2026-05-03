import logging
from datetime import date as date_type

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func, select

from bot.database import (
    Game,
    Submission,
    get_all_streaks,
    get_avg_score_over_time,
    get_game_difficulty_metrics,
    get_game_raw_data_breakdown,
    get_game_speed_bonus_stats,
    get_leaderboard,
    get_score_distribution,
    recalculate_game_ranks,
)
from web.deps import _db_session, fetch_all_games, require_admin, templates

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/games")
async def games_list(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        games = fetch_all_games(db)
        counts = {
            row.game_id: row.count
            for row in db.execute(
                select(Submission.game_id, func.count(Submission.id).label("count")).group_by(Submission.game_id)
            ).all()
        }
    finally:
        db.close()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        request,
        "games.html",
        {
            "active": "games",
            "games": games,
            "counts": counts,
            "flash": flash,
        },
    )


@router.get("/games/{game_id}")
async def game_detail(
    request: Request,
    game_id: str,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        game = db.get(Game, game_id)
        if not game:
            return RedirectResponse(url="/admin/games", status_code=302)
        metrics = get_game_difficulty_metrics(db, game_id)
        leaderboard = get_leaderboard(db, "alltime", game_id=game_id)
        streaks = [(uid, uname, streak) for uid, uname, streak in get_all_streaks(db, game_id) if streak > 0][:10]
    finally:
        db.close()

    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        request,
        "game_detail.html",
        {
            "active": "games",
            "game": game,
            "metrics": metrics,
            "leaderboard": leaderboard,
            "streaks": streaks,
            "flash": flash,
            "today": date_type.today().isoformat(),
        },
    )


@router.get("/games/{game_id}/stats")
async def game_detail_stats(
    game_id: str,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        distribution = get_score_distribution(db, game_id)
        score_over_time = get_avg_score_over_time(db, game_id, days=60)
        breakdown = get_game_raw_data_breakdown(db, game_id)
        speed_stats = get_game_speed_bonus_stats(db, game_id)
    finally:
        db.close()

    return JSONResponse(
        {
            "distribution": [{"label": b.label, "count": b.count} for b in distribution],
            "score_over_time": [
                {"date": p.date, "avg": p.avg_base_score, "count": p.submission_count} for p in score_over_time
            ],
            "breakdown": breakdown,
            "speed": {
                "total": speed_stats.total_submissions,
                "bonus_count": speed_stats.speed_bonus_count,
                "pct": speed_stats.speed_bonus_pct,
                "rank1": speed_stats.rank1_count,
                "rank2": speed_stats.rank2_count,
                "rank3": speed_stats.rank3_count,
            },
        }
    )


@router.post("/games/{game_id}/recalculate")
async def game_recalculate(
    request: Request,
    game_id: str,
    start_date: str = Form(...),
    end_date: str = Form(...),
    session: dict = Depends(require_admin),
):
    try:
        start = date_type.fromisoformat(start_date)
        end = date_type.fromisoformat(end_date)
    except ValueError:
        request.session["flash"] = "Invalid date range."
        return RedirectResponse(url=f"/admin/games/{game_id}", status_code=303)
    if end < start:
        request.session["flash"] = "End date must be on or after start date."
        return RedirectResponse(url=f"/admin/games/{game_id}", status_code=303)
    db = _db_session()
    try:
        affected = recalculate_game_ranks(db, game_id, start_date=start, end_date=end)
        db.commit()
    finally:
        db.close()
    log.info(
        "Admin %s recalculated ranks for %s (%d date(s), %s–%s)",
        session["email"],
        game_id,
        affected,
        start,
        end,
    )
    request.session["flash"] = f"Recalculated scores across {affected} date(s) ({start} → {end})."
    return RedirectResponse(url=f"/admin/games/{game_id}", status_code=303)


@router.post("/games/{game_id}/set-url")
async def game_set_url(
    request: Request,
    game_id: str,
    url: str = Form(default=""),
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        game = db.get(Game, game_id)
        if game:
            game.url = url.strip() or None
            db.commit()
            log.info("Admin %s set url for game %s to %s", session["email"], game_id, game.url)
            request.session["flash"] = f"URL updated for {game.name}."
    finally:
        db.close()
    return RedirectResponse(url=f"/admin/games/{game_id}", status_code=303)


@router.post("/games/{game_id}/set-multiplier")
async def game_set_multiplier(
    request: Request,
    game_id: str,
    multiplier: float = Form(...),
    session: dict = Depends(require_admin),
):
    if multiplier <= 0:
        request.session["flash"] = "Multiplier must be greater than 0."
        return RedirectResponse(url=f"/admin/games/{game_id}", status_code=303)
    db = _db_session()
    try:
        game = db.get(Game, game_id)
        if not game:
            return RedirectResponse(url="/admin/games", status_code=302)
        game.difficulty_multiplier = round(multiplier, 4)
        db.commit()
        log.info("Admin %s set multiplier for %s to %.4f", session["email"], game_id, multiplier)
        request.session["flash"] = f"Multiplier set to {multiplier:.4g}×. Use Recalculate to apply to existing scores."
    finally:
        db.close()
    return RedirectResponse(url=f"/admin/games/{game_id}", status_code=303)


@router.post("/games/{game_id}/toggle")
async def game_toggle(
    request: Request,
    game_id: str,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        game = db.get(Game, game_id)
        if game:
            game.enabled = not game.enabled
            db.commit()
            state = "enabled" if game.enabled else "disabled"
            log.info("Admin %s %s game %s", session["email"], state, game_id)
            request.session["flash"] = f"{game.name} {state}."
    finally:
        db.close()
    return RedirectResponse(url="/admin/games", status_code=303)
