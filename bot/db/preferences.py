from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.db.models import UserPreference


def get_opted_in_preferences(session: Session) -> list[UserPreference]:
    return list(session.execute(select(UserPreference).where(UserPreference.remind_streak_days > 0)).scalars())


def get_preference(session: Session, user_id: str) -> "UserPreference | None":
    return session.get(UserPreference, user_id)


def set_preference(session: Session, user_id: str, remind_streak_days: int) -> UserPreference:
    pref = session.get(UserPreference, user_id)
    if pref is None:
        pref = UserPreference(user_id=user_id, remind_streak_days=remind_streak_days)
        session.add(pref)
    else:
        pref.remind_streak_days = remind_streak_days
    session.flush()
    return pref
