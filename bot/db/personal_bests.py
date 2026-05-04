from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from bot.db.models import Submission


@dataclass
class PersonalBests:
    best_score: float
    best_date: date
    best_raw_data: dict
    avg_score: float
    count: int


def _best_submission_query(user_id: str, game_id: str) -> Select[tuple[Submission]]:
    return (
        select(Submission)
        .where(Submission.user_id == user_id, Submission.game_id == game_id)
        .order_by(Submission.base_score.desc(), Submission.submitted_at.asc())
        .limit(1)
    )


def _aggregate_query(user_id: str, game_id: str) -> Select[tuple[int, float | None]]:
    return select(
        func.count(Submission.id),
        func.avg(Submission.base_score),
    ).where(Submission.user_id == user_id, Submission.game_id == game_id)


def get_personal_bests(session: Session, user_id: str, game_id: str) -> "PersonalBests | None":
    best = session.execute(_best_submission_query(user_id, game_id)).scalar_one_or_none()
    if best is None:
        return None

    count, avg = session.execute(_aggregate_query(user_id, game_id)).one()

    return PersonalBests(
        best_score=best.base_score,
        best_date=best.date,
        best_raw_data=best.raw_data,
        avg_score=float(avg) if avg is not None else 0.0,
        count=int(count),
    )


def get_best_base_score(session: Session, user_id: str, game_id: str) -> float | None:
    return session.scalar(
        select(func.max(Submission.base_score)).where(
            Submission.user_id == user_id,
            Submission.game_id == game_id,
        )
    )
