from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from bot.achievements import ACHIEVEMENTS, SEASON_CHAMPION_DEF
from bot.database import (
    Submission,
    get_head_to_head,
    get_user_achievements,
    get_user_best_streaks,
    get_user_per_game_stats,
    get_user_score_history,
    get_user_submission_dates,
    get_user_total_freezes,
    get_users_for_h2h,
    get_users_summary,
)
from web.deps import _db_session, require_admin, templates

router = APIRouter()


def _build_achievement_list(user_achievements: list) -> list[dict]:
    earned_slugs = {ua.achievement_slug for ua in user_achievements}
    earned_at_by_slug = {ua.achievement_slug: ua.earned_at for ua in user_achievements}

    result = [
        {
            "slug": slug,
            "name": defn.name,
            "description": defn.description,
            "icon": defn.icon,
            "earned": slug in earned_slugs,
            "earned_at": earned_at_by_slug.get(slug),
        }
        for slug, defn in ACHIEVEMENTS.items()
    ]

    for slug in sorted(earned_slugs):
        if slug.startswith("season_champion_"):
            result.append(
                {
                    "slug": slug,
                    "name": SEASON_CHAMPION_DEF.name,
                    "description": SEASON_CHAMPION_DEF.description,
                    "icon": SEASON_CHAMPION_DEF.icon,
                    "earned": True,
                    "earned_at": earned_at_by_slug.get(slug),
                }
            )

    return result


@router.get("/users")
async def users_list(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        users = get_users_summary(db)
    finally:
        db.close()
    return templates.TemplateResponse(
        request,
        "users.html",
        {"active": "users", "users": users},
    )


@router.get("/users/{user_id}")
async def user_detail(
    request: Request,
    user_id: str,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        submissions = (
            db.execute(
                select(Submission)
                .where(Submission.user_id == user_id)
                .order_by(Submission.date.desc(), Submission.game_id)
            )
            .scalars()
            .all()
        )
        username = submissions[0].username if submissions else user_id
        total_score = sum(s.total_score for s in submissions)
        games_played = sorted({s.game_id for s in submissions})
        user_achievements = get_user_achievements(db, user_id)
        best_current_streak, best_ever_streak = get_user_best_streaks(db, user_id)
        total_freezes = get_user_total_freezes(db, user_id)
        per_game_stats = get_user_per_game_stats(db, user_id)
        submission_dates = get_user_submission_dates(db, user_id)
        h2h_users = get_users_for_h2h(db, exclude_user_id=user_id)
    finally:
        db.close()

    achievements = _build_achievement_list(user_achievements)
    return templates.TemplateResponse(
        request,
        "user_detail.html",
        {
            "active": "users",
            "user_id": user_id,
            "username": username,
            "submissions": submissions,
            "total_score": total_score,
            "games_played": games_played,
            "achievements": achievements,
            "best_current_streak": best_current_streak,
            "best_ever_streak": best_ever_streak,
            "total_freezes": total_freezes,
            "per_game_stats": per_game_stats,
            "submission_dates": submission_dates,
            "h2h_users": h2h_users,
        },
    )


@router.get("/users/{user_id}/score-history")
async def user_score_history(
    user_id: str,
    game_id: str = Query(default=""),
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        points = get_user_score_history(db, user_id, game_id=game_id or None)
    finally:
        db.close()
    return JSONResponse([{"date": p.date, "game_id": p.game_id, "score": p.total_score} for p in points])


@router.get("/users/{user_id}/h2h")
async def user_h2h(
    user_id: str,
    opponent: str = Query(...),
    game_id: str = Query(default=""),
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        result = get_head_to_head(db, user_id, opponent, game_id=game_id or None)
    finally:
        db.close()
    if not result:
        return JSONResponse({"error": "No overlapping games found."}, status_code=404)
    return JSONResponse(
        {
            "caller": result.caller_username,
            "opponent": result.opponent_username,
            "caller_wins": result.caller_wins,
            "opponent_wins": result.opponent_wins,
            "ties": result.ties,
            "caller_total": result.caller_total_score,
            "opponent_total": result.opponent_total_score,
            "days": result.overlapping_days,
        }
    )
