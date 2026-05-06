from dataclasses import dataclass
from datetime import datetime, timezone

from rapidfuzz import fuzz
from sqlalchemy import func, select, update
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
        update(GameSuggestion).where(GameSuggestion.id.in_(suggestion_ids)).values(poll_id=poll.id, status="polled")
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


# ---------------------------------------------------------------------------
# Suggestion analytics
# ---------------------------------------------------------------------------


@dataclass
class SuggestionStats:
    total: int
    by_status: dict[str, int]
    top_suggesters: list[dict]
    timeline: list[dict]


def get_suggestion_stats(session: Session) -> SuggestionStats:
    total = session.scalar(select(func.count(GameSuggestion.id))) or 0

    status_rows = session.execute(
        select(GameSuggestion.status, func.count(GameSuggestion.id).label("cnt")).group_by(GameSuggestion.status)
    ).all()
    by_status = {row.status or "pending": row.cnt for row in status_rows}

    suggester_rows = session.execute(
        select(GameSuggestion.username, func.count(GameSuggestion.id).label("cnt"))
        .where(GameSuggestion.username.isnot(None))
        .group_by(GameSuggestion.username)
        .order_by(func.count(GameSuggestion.id).desc())
        .limit(10)
    ).all()
    top_suggesters = [{"username": r.username, "count": r.cnt} for r in suggester_rows]

    # Monthly submission timeline
    timeline_rows = (
        session.execute(select(GameSuggestion.suggested_at).order_by(GameSuggestion.suggested_at.asc())).scalars().all()
    )
    monthly: dict[str, int] = {}
    for ts in timeline_rows:
        if ts:
            key = ts.strftime("%Y-%m")
            monthly[key] = monthly.get(key, 0) + 1
    timeline = [{"month": k, "count": v} for k, v in sorted(monthly.items())]

    return SuggestionStats(
        total=total,
        by_status=by_status,
        top_suggesters=top_suggesters,
        timeline=timeline,
    )
