from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.db.models import MonthlyRankSnapshot


@dataclass
class RankHistoryPoint:
    year: int
    month: int
    rank: int
    total_users: int


def get_rank_history(session: Session, user_id: str) -> list[RankHistoryPoint]:
    rows = session.execute(
        select(
            MonthlyRankSnapshot.year,
            MonthlyRankSnapshot.month,
            MonthlyRankSnapshot.rank,
            MonthlyRankSnapshot.player_count,
        )
        .where(MonthlyRankSnapshot.user_id == user_id)
        .order_by(MonthlyRankSnapshot.year.asc(), MonthlyRankSnapshot.month.asc())
    ).all()
    return [
        RankHistoryPoint(year=row.year, month=row.month, rank=row.rank, total_users=row.player_count) for row in rows
    ]
