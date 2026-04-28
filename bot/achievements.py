from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from bot.database import Submission, UserStreak


@dataclass(frozen=True)
class AchievementDef:
    slug: str
    name: str
    description: str
    icon: str


ACHIEVEMENTS: dict[str, AchievementDef] = {
    a.slug: a
    for a in [
        AchievementDef("first_steps", "First Steps", "Submit your first score", "🎯"),
        AchievementDef("on_fire", "On Fire", "Reach a 7-day streak on any game", "🔥"),
        AchievementDef("dedicated", "Dedicated", "Reach a 30-day streak on any game", "💪"),
        AchievementDef("unstoppable", "Unstoppable", "Reach a 100-day streak on any game", "⚡"),
        AchievementDef("century", "Century", "Submit 100 total scores", "💯"),
        AchievementDef("veteran", "Veteran", "Submit 500 total scores", "🏅"),
        AchievementDef(
            "speed_demon",
            "Speed Demon",
            "Earn the 1st-place speed bonus for the first time",
            "🚀",
        ),
        AchievementDef(
            "need_for_speed",
            "Need for Speed",
            "Earn the 1st-place speed bonus 25 times",
            "🏎️",
        ),
        AchievementDef("hat_trick", "Hat Trick", "Submit to 3 different games in one day", "🎩"),
        AchievementDef(
            "completionist",
            "Completionist",
            "Submit to every enabled game in one day",
            "🌟",
        ),
        AchievementDef(
            "freeze_saver",
            "Freeze Saver",
            "Save a streak by using a freeze",
            "🧊",
        ),
    ]
}

SEASON_CHAMPION_DEF = AchievementDef(
    "season_champion",
    "Season Champion",
    "Finish #1 overall in a season",
    "👑",
)


def resolve_achievement_def(slug: str) -> AchievementDef | None:
    if slug in ACHIEVEMENTS:
        return ACHIEVEMENTS[slug]
    if slug.startswith("season_champion_"):
        return SEASON_CHAMPION_DEF
    return None


def check_and_award_achievements(
    session: Session,
    user_id: str,
    game_id: str,
    submission_date,
    streak: "UserStreak",
    submission: "Submission",
    freeze_used: bool,
    enabled_game_count: int,
) -> list[str]:
    from bot.database import Submission as Sub
    from bot.database import UserAchievement

    earned = set(
        session.scalars(select(UserAchievement.achievement_slug).where(UserAchievement.user_id == user_id)).all()
    )

    newly_earned: list[str] = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    def award(slug: str) -> None:
        if slug not in earned and slug in ACHIEVEMENTS:
            session.add(
                UserAchievement(
                    user_id=user_id,
                    achievement_slug=slug,
                    display_name=ACHIEVEMENTS[slug].name,
                    earned_at=now,
                )
            )
            newly_earned.append(slug)
            earned.add(slug)

    total_count = session.scalar(select(func.count()).select_from(Sub).where(Sub.user_id == user_id)) or 0

    if total_count == 1:
        award("first_steps")
    if total_count >= 100:
        award("century")
    if total_count >= 500:
        award("veteran")

    if streak.current_streak >= 7:
        award("on_fire")
    if streak.current_streak >= 30:
        award("dedicated")
    if streak.current_streak >= 100:
        award("unstoppable")

    if submission.submission_rank == 1:
        award("speed_demon")
        first_count = (
            session.scalar(
                select(func.count()).select_from(Sub).where(Sub.user_id == user_id, Sub.submission_rank == 1)
            )
            or 0
        )
        if first_count >= 25:
            award("need_for_speed")

    today_game_count = (
        session.scalar(
            select(func.count(distinct(Sub.game_id))).where(
                Sub.user_id == user_id,
                Sub.date == submission_date,
            )
        )
        or 0
    )
    if today_game_count >= 3:
        award("hat_trick")
    if enabled_game_count > 0 and today_game_count >= enabled_game_count:
        award("completionist")

    if freeze_used:
        award("freeze_saver")

    if newly_earned:
        session.flush()

    return newly_earned
