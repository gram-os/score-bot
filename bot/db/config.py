from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from bot.db.models import AdminConfig

SCORING_TZ = ZoneInfo("America/New_York")


def get_config(session: Session, key: str, default: str = "") -> str:
    row = session.get(AdminConfig, key)
    return row.value if row else default


def set_config(session: Session, key: str, value: str) -> None:
    row = session.get(AdminConfig, key)
    if row is None:
        session.add(AdminConfig(key=key, value=value))
    else:
        row.value = value
    session.commit()
