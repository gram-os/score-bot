from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot.db.models import UsageEvent


def log_usage_event(
    session: Session,
    event_type: str,
    user_id: str | None = None,
    username: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    session.add(
        UsageEvent(
            event_type=event_type,
            user_id=user_id,
            username=username,
            event_data=metadata,
            timestamp=datetime.utcnow(),
        )
    )


def get_usage_events(
    session: Session,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[UsageEvent], int]:
    stmt = select(UsageEvent).order_by(UsageEvent.timestamp.desc())
    count_stmt = select(func.count()).select_from(UsageEvent)

    if event_type:
        stmt = stmt.where(UsageEvent.event_type == event_type)
        count_stmt = count_stmt.where(UsageEvent.event_type == event_type)

    total = session.scalar(count_stmt) or 0
    rows = session.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return list(rows), total


def get_usage_summary(session: Session) -> list[tuple[str, int]]:
    rows = session.execute(
        select(UsageEvent.event_type, func.count(UsageEvent.id).label("cnt"))
        .group_by(UsageEvent.event_type)
        .order_by(func.count(UsageEvent.id).desc())
    ).all()
    return [(row.event_type, row.cnt) for row in rows]
