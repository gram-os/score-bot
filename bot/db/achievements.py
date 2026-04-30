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


def award_season_champion(session: Session, user_id: str, season_id: int, season_name: str) -> bool:
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
            display_name=f"Season Champion · {season_name}",
            earned_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    session.flush()
    return True


def get_season_champion_user_ids(session: Session) -> set[str]:
    """Return user_ids of all past season champions."""
    rows = session.scalars(
        select(UserAchievement.user_id).where(UserAchievement.achievement_slug.like("season_champion_%"))
    ).all()
    return set(rows)
