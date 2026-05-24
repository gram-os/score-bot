from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from bot.db.models import Game, Season, Submission, User, UserAchievement


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


def award_game_mvp(
    session: Session,
    user_id: str,
    game_id: str,
    season_id: int,
    season_name: str,
    badge_name: str,
) -> bool:
    """Award a per-game MVP achievement for a season. Returns True if newly awarded."""
    slug = f"game_mvp_{game_id}_season_{season_id}"
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
            display_name=f"{badge_name} · {season_name}",
            earned_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    session.flush()
    return True


@dataclass
class GameMvpRow:
    game_id: str
    game_name: str
    user_id: str
    username: str
    total_score: float


def get_season_game_top_scorers(session: Session, season: Season) -> list[GameMvpRow]:
    """Return the top scorer per enabled game for the given season."""
    games = session.scalars(select(Game).where(Game.enabled.is_(True))).all()
    results: list[GameMvpRow] = []
    for game in games:
        top = session.execute(
            select(
                Submission.user_id,
                User.username,
                func.sum(Submission.total_score).label("pts"),
            )
            .join(User, Submission.user_id == User.user_id)
            .where(
                Submission.game_id == game.id,
                Submission.date >= season.start_date,
                Submission.date <= season.end_date,
            )
            .group_by(Submission.user_id)
            .order_by(func.sum(Submission.total_score).desc())
            .limit(1)
        ).first()
        if top:
            results.append(
                GameMvpRow(
                    game_id=game.id,
                    game_name=game.name,
                    user_id=top.user_id,
                    username=top.username,
                    total_score=top.pts,
                )
            )
    return results


def get_season_champion_user_ids(session: Session) -> set[str]:
    """Return user_ids of all past season champions."""
    rows = session.scalars(
        select(UserAchievement.user_id).where(UserAchievement.achievement_slug.like("season_champion_%"))
    ).all()
    return set(rows)
