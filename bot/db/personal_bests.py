from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.db.models import Submission


@dataclass
class PersonalBests:
    best_score: float
    best_date: date
    best_raw_data: dict
    avg_score: float
    count: int


def get_personal_bests(session: Session, user_id: str, game_id: str) -> "PersonalBests | None":
    rows = (
        session.execute(
            select(Submission)
            .where(Submission.user_id == user_id, Submission.game_id == game_id)
            .order_by(Submission.total_score.desc())
        )
        .scalars()
        .all()
    )

    if not rows:
        return None

    best = rows[0]
    avg = sum(r.total_score for r in rows) / len(rows)
    return PersonalBests(
        best_score=best.total_score,
        best_date=best.date,
        best_raw_data=best.raw_data,
        avg_score=avg,
        count=len(rows),
    )
