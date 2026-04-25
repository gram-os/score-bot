from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.db.models import HomunculusUpgrade


def add_homunculus_upgrade(
    session: Session,
    upgrade_text: str,
    vote_count: int,
    poll_question: str,
    message_id: str,
) -> HomunculusUpgrade:
    upgrade = HomunculusUpgrade(
        upgrade_text=upgrade_text,
        vote_count=vote_count,
        poll_question=poll_question,
        message_id=message_id,
        recorded_at=datetime.utcnow(),
    )
    session.add(upgrade)
    return upgrade


def get_homunculus_upgrades(session: Session) -> list[HomunculusUpgrade]:
    return session.execute(select(HomunculusUpgrade).order_by(HomunculusUpgrade.recorded_at)).scalars().all()


def homunculus_upgrade_exists(session: Session, message_id: str) -> bool:
    return (
        session.execute(
            select(HomunculusUpgrade).where(HomunculusUpgrade.message_id == message_id)
        ).scalar_one_or_none()
        is not None
    )
