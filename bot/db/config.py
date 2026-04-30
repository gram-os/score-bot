from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from bot.db.models import AdminConfig


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


def get_scoring_tz(session: Session) -> ZoneInfo:
    tz_name = get_config(session, "scoring_timezone", "") or get_config(
        session, "display_timezone", "America/New_York"
    )
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        return ZoneInfo("America/New_York")
