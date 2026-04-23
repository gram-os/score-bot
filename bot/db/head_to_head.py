from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from bot.db.models import Submission, User


@dataclass
class HeadToHeadResult:
    caller_username: str
    opponent_username: str
    caller_total_score: float
    opponent_total_score: float
    caller_wins: int
    opponent_wins: int
    ties: int
    overlapping_days: int


def get_head_to_head(
    session: Session,
    caller_id: str,
    opponent_id: str,
    game_id: str | None = None,
) -> HeadToHeadResult | None:
    caller_sub = aliased(Submission, name="caller_sub")
    opponent_sub = aliased(Submission, name="opponent_sub")

    stmt = (
        select(caller_sub, opponent_sub)
        .join(
            opponent_sub,
            (caller_sub.date == opponent_sub.date) & (caller_sub.game_id == opponent_sub.game_id),
        )
        .where(
            caller_sub.user_id == caller_id,
            opponent_sub.user_id == opponent_id,
        )
    )
    if game_id is not None:
        stmt = stmt.where(caller_sub.game_id == game_id)

    rows = session.execute(stmt).all()
    if not rows:
        return None

    caller_user = session.get(User, caller_id)
    opponent_user = session.get(User, opponent_id)
    caller_username = caller_user.username if caller_user else rows[0][0].username
    opponent_username = opponent_user.username if opponent_user else rows[0][1].username
    caller_wins = caller_losses = ties = 0
    caller_total = opponent_total = 0.0

    for c_sub, o_sub in rows:
        caller_total += c_sub.total_score
        opponent_total += o_sub.total_score
        if c_sub.total_score > o_sub.total_score:
            caller_wins += 1
        elif o_sub.total_score > c_sub.total_score:
            caller_losses += 1
        else:
            ties += 1

    return HeadToHeadResult(
        caller_username=caller_username,
        opponent_username=opponent_username,
        caller_total_score=caller_total,
        opponent_total_score=opponent_total,
        caller_wins=caller_wins,
        opponent_wins=caller_losses,
        ties=ties,
        overlapping_days=len(rows),
    )
