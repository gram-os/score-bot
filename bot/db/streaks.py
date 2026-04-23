from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from bot.db.models import Game, Submission, User, UserStreak

MAX_FREEZES = 3


def _is_streak_active(row: UserStreak) -> bool:
    if row.last_submission_date is None:
        return False
    today = datetime.now(timezone.utc).date()
    return (today - row.last_submission_date).days <= 1


def get_streak(session: Session, user_id: str, game_id: str) -> int:
    row = session.scalar(
        select(UserStreak).where(
            UserStreak.user_id == user_id,
            UserStreak.game_id == game_id,
        )
    )
    if row is None:
        return 0
    return row.current_streak if _is_streak_active(row) else 0


def get_user_best_streaks(session: Session, user_id: str) -> tuple[int, int]:
    """Returns (best active streak, best ever streak) across all games."""
    rows = session.scalars(select(UserStreak).where(UserStreak.user_id == user_id)).all()
    best_current = max((r.current_streak for r in rows if _is_streak_active(r)), default=0)
    best_ever = max((r.longest_streak for r in rows), default=0)
    return best_current, best_ever


def get_user_streak(session: Session, user_id: str, game_id: str) -> "UserStreak | None":
    return session.scalar(
        select(UserStreak).where(
            UserStreak.user_id == user_id,
            UserStreak.game_id == game_id,
        )
    )


def get_all_streaks(session: Session, game_id: str) -> list[tuple[str, str, int]]:
    today = datetime.now(timezone.utc).date()
    rows = session.execute(
        select(
            UserStreak.user_id,
            User.username,
            UserStreak.current_streak,
            UserStreak.last_submission_date,
        )
        .join(User, UserStreak.user_id == User.user_id)
        .where(UserStreak.game_id == game_id)
    ).all()
    results = []
    for r in rows:
        days_since = (today - r.last_submission_date).days if r.last_submission_date else 999
        active = r.current_streak if days_since <= 1 else 0
        results.append((r.user_id, r.username, active))
    results.sort(key=lambda x: x[2], reverse=True)
    return results


def update_streak_on_submission(
    session: Session, user_id: str, game_id: str, submission_date: date
) -> tuple[UserStreak, bool]:
    """Update stored streak state for a new submission. Returns (streak, freeze_used)."""
    streak = session.scalar(
        select(UserStreak).where(
            UserStreak.user_id == user_id,
            UserStreak.game_id == game_id,
        )
    )

    if streak is None:
        streak = UserStreak(
            user_id=user_id,
            game_id=game_id,
            current_streak=1,
            longest_streak=1,
            last_submission_date=submission_date,
            freeze_count=0,
        )
        session.add(streak)
        session.flush()
        return streak, False

    if streak.last_submission_date is None:
        streak.current_streak = 1
        streak.longest_streak = max(streak.longest_streak, 1)
        streak.last_submission_date = submission_date
        session.flush()
        return streak, False

    days_gap = (submission_date - streak.last_submission_date).days
    freeze_used = False

    if days_gap <= 0:
        return streak, False
    elif days_gap == 1:
        streak.current_streak += 1
        if streak.current_streak % 7 == 0 and streak.freeze_count < MAX_FREEZES:
            streak.freeze_count += 1
    elif days_gap == 2:
        if streak.freeze_count > 0:
            streak.freeze_count -= 1
            streak.current_streak += 1
            freeze_used = True
        else:
            streak.current_streak = 1
    else:
        streak.current_streak = 1

    streak.longest_streak = max(streak.longest_streak, streak.current_streak)
    streak.last_submission_date = submission_date
    session.flush()
    return streak, freeze_used


@dataclass
class GameDigestData:
    game_id: str
    game_name: str
    winner_username: str | None
    winner_score: float
    participant_count: int
    top_streak: int


def get_yesterday_digest(session: Session) -> list[GameDigestData]:
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    games = session.execute(select(Game).where(Game.enabled.is_(True))).scalars().all()

    results = []
    for game in games:
        subs = (
            session.execute(
                select(Submission)
                .where(Submission.game_id == game.id, Submission.date == yesterday)
                .order_by(Submission.total_score.desc())
            )
            .scalars()
            .all()
        )

        if not subs:
            results.append(
                GameDigestData(
                    game_id=game.id,
                    game_name=game.name,
                    winner_username=None,
                    winner_score=0.0,
                    participant_count=0,
                    top_streak=0,
                )
            )
            continue

        top_streak = max(get_streak(session, sub.user_id, game.id) for sub in subs)
        winner_user = session.get(User, subs[0].user_id)
        results.append(
            GameDigestData(
                game_id=game.id,
                game_name=game.name,
                winner_username=(winner_user.username if winner_user else subs[0].username),
                winner_score=subs[0].total_score,
                participant_count=len(subs),
                top_streak=top_streak,
            )
        )

    return results


@dataclass
class WeeklyDigestData:
    week_start: date
    week_end: date
    top_scorer_username: str | None
    top_scorer_points: float
    most_active_username: str | None
    most_active_submissions: int
    best_single_score: float
    best_single_username: str | None
    best_single_game: str | None
    top_streak_username: str | None
    top_streak_days: int
    total_submissions: int
    unique_players: int


def get_weekly_digest(session: Session) -> WeeklyDigestData:
    today = datetime.now(timezone.utc).date()
    week_end = today - timedelta(days=today.weekday() + 1)
    week_start = week_end - timedelta(days=6)

    scorer_row = session.execute(
        select(User.username, func.sum(Submission.total_score).label("pts"))
        .join(User, Submission.user_id == User.user_id)
        .where(Submission.date >= week_start, Submission.date <= week_end)
        .group_by(Submission.user_id)
        .order_by(func.sum(Submission.total_score).desc())
        .limit(1)
    ).first()

    active_row = session.execute(
        select(User.username, func.count(Submission.id).label("cnt"))
        .join(User, Submission.user_id == User.user_id)
        .where(Submission.date >= week_start, Submission.date <= week_end)
        .group_by(Submission.user_id)
        .order_by(func.count(Submission.id).desc())
        .limit(1)
    ).first()

    best_sub = session.execute(
        select(Submission, User.username, Game.name.label("game_name"))
        .join(User, Submission.user_id == User.user_id)
        .join(Game, Submission.game_id == Game.id)
        .where(Submission.date >= week_start, Submission.date <= week_end)
        .order_by(Submission.total_score.desc())
        .limit(1)
    ).first()

    streak_row = session.execute(
        select(User.username, UserStreak.current_streak)
        .join(User, UserStreak.user_id == User.user_id)
        .order_by(UserStreak.current_streak.desc())
        .limit(1)
    ).first()

    total_subs = (
        session.scalar(
            select(func.count())
            .select_from(Submission)
            .where(Submission.date >= week_start, Submission.date <= week_end)
        )
        or 0
    )

    unique_players = (
        session.scalar(
            select(func.count(distinct(Submission.user_id))).where(
                Submission.date >= week_start, Submission.date <= week_end
            )
        )
        or 0
    )

    return WeeklyDigestData(
        week_start=week_start,
        week_end=week_end,
        top_scorer_username=scorer_row.username if scorer_row else None,
        top_scorer_points=scorer_row.pts if scorer_row else 0.0,
        most_active_username=active_row.username if active_row else None,
        most_active_submissions=active_row.cnt if active_row else 0,
        best_single_score=best_sub[0].total_score if best_sub else 0.0,
        best_single_username=best_sub.username if best_sub else None,
        best_single_game=best_sub.game_name if best_sub else None,
        top_streak_username=streak_row.username if streak_row else None,
        top_streak_days=streak_row.current_streak if streak_row else 0,
        total_submissions=total_subs,
        unique_players=unique_players,
    )
