from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot.db.models import Submission, User
from bot.db.seasons import get_current_season


@dataclass
class LeaderboardRow:
    rank: int
    user_id: str
    username: str
    total_score: float
    submission_count: int


def _period_bounds(
    period: Literal["daily", "weekly", "monthly", "alltime"],
) -> tuple[date | None, date | None]:
    today = datetime.now(timezone.utc).date()
    if period == "daily":
        return today, today
    if period == "weekly":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if period == "monthly":
        start = today.replace(day=1)
        if today.month == 12:
            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return start, end
    return None, None


def get_leaderboard(
    session: Session,
    period: Literal["daily", "weekly", "monthly", "alltime", "season"],
    game_id: str | None = None,
) -> list[LeaderboardRow]:
    if period == "season":
        season = get_current_season(session)
        start = season.start_date if season else None
        end = season.end_date if season else None
    else:
        start, end = _period_bounds(period)

    stmt = (
        select(
            Submission.user_id,
            User.username,
            func.sum(Submission.total_score).label("total_score"),
            func.count(Submission.id).label("submission_count"),
        )
        .join(User, Submission.user_id == User.user_id)
        .group_by(Submission.user_id)
        .order_by(func.sum(Submission.total_score).desc())
    )

    if game_id is not None:
        stmt = stmt.where(Submission.game_id == game_id)
    if start is not None:
        stmt = stmt.where(Submission.date >= start)
    if end is not None:
        stmt = stmt.where(Submission.date <= end)

    rows = session.execute(stmt).all()
    return [
        LeaderboardRow(
            rank=i + 1,
            user_id=row.user_id,
            username=row.username,
            total_score=row.total_score,
            submission_count=row.submission_count,
        )
        for i, row in enumerate(rows)
    ]
