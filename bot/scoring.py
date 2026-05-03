from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.db.models import Game, Submission

# Multipliers only apply from Season 1 onwards; Beta submissions stay as-is.
_MULTIPLIER_EFFECTIVE_DATE = date(2026, 5, 1)


def calculate_speed_bonus(rank: int) -> int:
    return {1: 15, 2: 10, 3: 5}.get(rank, 0)


def assign_submission_rank(session: Session, game_id: str, submission_date: date) -> None:
    game = session.get(Game, game_id)
    multiplier = game.difficulty_multiplier if game and submission_date >= _MULTIPLIER_EFFECTIVE_DATE else 1.0

    submissions = session.scalars(
        select(Submission)
        .where(Submission.game_id == game_id, Submission.date == submission_date)
        .order_by(Submission.submitted_at)
    ).all()

    for rank, submission in enumerate(submissions, start=1):
        bonus = calculate_speed_bonus(rank) if submission.base_score > 0 else 0
        submission.submission_rank = rank
        submission.speed_bonus = bonus
        submission.total_score = round(submission.base_score * multiplier + bonus, 2)

    session.flush()
