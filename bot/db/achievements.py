from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.db.models import UserAchievement


def get_user_achievements(session: Session, user_id: str) -> list[UserAchievement]:
    return list(
        session.scalars(
            select(UserAchievement).where(UserAchievement.user_id == user_id).order_by(UserAchievement.earned_at)
        ).all()
    )


def award_season_champion(session: Session, user_id: str, season_id: int) -> bool:
    """Award a season-scoped champion achievement. Returns True if newly awarded."""
    slug = f"season_champion_{season_id}"
    existing = session.scalar(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_slug == slug,
        )
    )
    if existing:
        return False
    session.add(
        UserAchievement(
            user_id=user_id,
            achievement_slug=slug,
            display_name="Season Champion",
            earned_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    session.flush()
    return True
