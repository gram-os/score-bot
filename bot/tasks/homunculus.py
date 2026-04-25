import logging

import discord
from sqlalchemy.orm import sessionmaker

from bot.db.homunculus import add_homunculus_upgrade, homunculus_upgrade_exists

log = logging.getLogger(__name__)


async def check_homunculus_polls(
    client: discord.Client,
    channel_id: int,
    author_id: int,
    Session: sessionmaker,
) -> None:
    channel = client.get_channel(channel_id)
    if channel is None:
        log.warning("Homunculus: channel %s not found", channel_id)
        return

    try:
        messages = [msg async for msg in channel.history(limit=50)]
    except Exception:
        log.exception("Homunculus: failed to fetch channel history")
        return

    for message in messages:
        if message.author.id != author_id:
            continue
        if message.poll is None:
            continue
        if "homunculus" not in message.poll.question.text.lower():
            continue
        if not message.poll.is_finalized:
            continue

        message_id = str(message.id)
        with Session() as session:
            if homunculus_upgrade_exists(session, message_id):
                continue

            answers = sorted(message.poll.answers, key=lambda a: a.vote_count, reverse=True)
            if not answers:
                continue

            winner = answers[0]
            add_homunculus_upgrade(
                session,
                upgrade_text=winner.text or "Unknown",
                vote_count=winner.vote_count,
                poll_question=message.poll.question.text,
                message_id=message_id,
            )
            session.commit()
            log.info("Recorded homunculus upgrade: %s (message %s)", winner.text, message_id)

        try:
            await message.add_reaction("🧬")
            await message.add_reaction("✨")
        except Exception:
            log.warning("Homunculus: could not react to message %s", message_id)
