from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.db.models import Feedback


def add_feedback(
    session: Session,
    user_id: str,
    username: str,
    category: str,
    content: str,
) -> Feedback:
    entry = Feedback(
        user_id=user_id,
        username=username,
        category=category,
        content=content,
        submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(entry)
    session.flush()
    return entry


def get_all_feedback(session: Session) -> list[Feedback]:
    return list(session.execute(select(Feedback).order_by(Feedback.submitted_at.desc())).scalars())
