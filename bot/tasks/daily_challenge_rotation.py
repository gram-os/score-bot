import logging
from datetime import datetime

from bot.db import daily_challenge
from bot.db.config import SCORING_TZ

log = logging.getLogger(__name__)


def run_daily_rotation(Session) -> None:
    with Session() as session:
        if not daily_challenge.is_enabled(session):
            return
        if daily_challenge.get_mode(session) != "random":
            return
        today = datetime.now(SCORING_TZ).date()
        chosen = daily_challenge.roll_random_game(session, today)
        session.commit()
        log.info("Daily challenge auto-rotation: chose %s for %s", chosen, today)
