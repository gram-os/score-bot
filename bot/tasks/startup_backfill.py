import logging

import discord

from bot.db.config import get_config
from bot.tasks.message_handler import handle_message

log = logging.getLogger(__name__)


async def run_startup_backfill(client: discord.Client, registry, Session, channel_id: int) -> None:
    """Fetch and process any messages posted while the bot was offline."""
    with Session() as session:
        last_id_str = get_config(session, "last_seen_message_id", "")

    if not last_id_str:
        log.info("Startup backfill: no cursor stored, skipping (first run)")
        return

    channel = client.get_channel(channel_id)
    if channel is None:
        log.warning("Startup backfill: channel %s not available", channel_id)
        return

    messages: list[discord.Message] = []
    async for msg in channel.history(
        after=discord.Object(id=int(last_id_str)),
        oldest_first=True,
        limit=None,
    ):
        messages.append(msg)

    if not messages:
        log.info("Startup backfill: no missed messages since %s", last_id_str)
        return

    log.info("Startup backfill: replaying %d missed message(s)", len(messages))
    for msg in messages:
        await handle_message(client, msg, registry, Session, channel_id)

    log.info("Startup backfill: complete")
