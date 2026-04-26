from datetime import datetime, timezone

from rapidfuzz import fuzz
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from bot.db.models import DailyPoll, GameSuggestion

_FUZZY_THRESHOLD = 85


def find_similar_name(name: str, candidates: list[str]) -> str | None:
    name_lower = name.lower()
    for candidate in candidates:
        if fuzz.ratio(name_lower, candidate.lower()) >= _FUZZY_THRESHOLD:
            return candidate
    return None


def add_suggestion(
    session: Session,
    user_id: str,
    username: str,
    game_name: str,
    description: str | None = None,
) -> GameSuggestion:
    suggestion = GameSuggestion(
        user_id=user_id,
        username=username,
        game_name=game_name,
        description=description,
        suggested_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(suggestion)
    session.flush()
    return suggestion


def get_unpolled_suggestions(session: Session) -> list[GameSuggestion]:
    return list(session.execute(select(GameSuggestion).where(GameSuggestion.poll_id.is_(None))).scalars())


def create_daily_poll(
    session: Session,
    message_id: str,
    is_yes_no: bool,
    suggestion_ids: list[int],
    expires_at: datetime | None = None,
) -> DailyPoll:
    poll = DailyPoll(
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        expires_at=expires_at,
        message_id=message_id,
        is_yes_no=is_yes_no,
        notified=False,
    )
    session.add(poll)
    session.flush()
    session.execute(
        update(GameSuggestion)
        .where(GameSuggestion.id.in_(suggestion_ids))
        .values(poll_id=poll.id, status="polled")
    )
    return poll


def get_latest_unnotified_poll(session: Session) -> DailyPoll | None:
    return session.scalar(
        select(DailyPoll)
        .options(selectinload(DailyPoll.suggestions))
        .where(DailyPoll.notified.is_(False))
        .order_by(DailyPoll.created_at.desc())
        .limit(1)
    )


def mark_poll_notified(session: Session, poll_id: int) -> None:
    poll = session.get(DailyPoll, poll_id)
    if poll:
        poll.notified = True
