from datetime import datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from bot.db.config import SCORING_TZ
from bot.db.models import Season


def get_current_season(session: Session) -> "Season | None":
    today = datetime.now(SCORING_TZ).date()
    return session.scalar(select(Season).where(and_(Season.start_date <= today, Season.end_date >= today)))


def get_season_ending_yesterday(session: Session) -> "Season | None":
    yesterday = (datetime.now(SCORING_TZ) - timedelta(days=1)).date()
    return session.scalar(select(Season).where(Season.end_date == yesterday))
