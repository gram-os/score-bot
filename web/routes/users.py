from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from bot.achievements import ACHIEVEMENTS
from bot.database import Submission, get_user_achievements, get_users_summary
from web.deps import _db_session, require_admin, templates

router = APIRouter()


def _build_achievement_list(user_achievements: list) -> list[dict]:
    earned_slugs = {ua.achievement_slug for ua in user_achievements}
    earned_at_by_slug = {ua.achievement_slug: ua.earned_at for ua in user_achievements}
    return [
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
        },
    )
