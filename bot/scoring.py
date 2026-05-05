from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.db import daily_challenge
from bot.db.models import Game, Submission

# Multipliers only apply from Season 1 onwards; Beta submissions stay as-is.
_MULTIPLIER_EFFECTIVE_DATE = date(2026, 5, 1)


def calculate_speed_bonus(rank: int) -> int:
    return {1: 15, 2: 10, 3: 5}.get(rank, 0)


def _daily_challenge_bonus_multiplier(session: Session, game_id: str, submission_date: date) -> float:
    if not daily_challenge.is_enabled(session):
        return 1.0
    today_game_id = daily_challenge.get_today_game_id(session, submission_date)
    if today_game_id != game_id:
        return 1.0
    return daily_challenge.get_multiplier(session)


def assign_submission_rank(session: Session, game_id: str, submission_date: date) -> None:
    game = session.get(Game, game_id)
    multiplier = game.difficulty_multiplier if game and submission_date >= _MULTIPLIER_EFFECTIVE_DATE else 1.0
    challenge_bonus_multiplier = _daily_challenge_bonus_multiplier(session, game_id, submission_date)

    submissions = session.scalars(
        select(Submission)
        .where(Submission.game_id == game_id, Submission.date == submission_date)
        .order_by(Submission.submitted_at)
    ).all()

    next_rank = 1
    for submission in submissions:
        if submission.base_score > 0:
            rank = next_rank
            next_rank += 1
            base_bonus = calculate_speed_bonus(rank)
            bonus = round(base_bonus * challenge_bonus_multiplier)
        else:
            rank = 0
            bonus = 0
        submission.submission_rank = rank
        submission.speed_bonus = bonus
        submission.total_score = round(submission.base_score * multiplier + bonus, 2)

    session.flush()
