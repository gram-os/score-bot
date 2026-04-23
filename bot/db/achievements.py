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


def award_season_champion(session: Session, user_id: str) -> bool:
    """Award season_champion achievement. Returns True if newly awarded."""
    existing = session.scalar(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_slug == "season_champion",
        )
    )
    if existing:
        return False
    session.add(
        UserAchievement(
            user_id=user_id,
            achievement_slug="season_champion",
            earned_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    session.flush()
    return True
