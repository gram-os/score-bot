import datetime
import logging

import discord
from sqlalchemy import select

from bot.database import Game, get_opted_in_preferences, get_streak, is_duplicate

log = logging.getLogger(__name__)


async def send_streak_reminders(client: discord.Client, Session, channel_id: int) -> None:
    today = datetime.datetime.now(datetime.timezone.utc).date()

    with Session() as session:
        prefs = get_opted_in_preferences(session)
        enabled_games = session.execute(select(Game).where(Game.enabled.is_(True))).scalars().all()

        reminders: dict[str, list[str]] = {}
        for pref in prefs:
            qualifying_games = []
            for game in enabled_games:
                streak = get_streak(session, pref.user_id, game.id)
                if streak >= pref.remind_streak_days and not is_duplicate(session, pref.user_id, game.id, today):
                    qualifying_games.append(game.name)
            if qualifying_games:
                reminders[pref.user_id] = qualifying_games

    sent = 0
    for user_id, game_names in reminders.items():
        try:
            user = await client.fetch_user(int(user_id))
            games_list = ", ".join(f"**{g}**" for g in game_names)
            await user.send(f"Don't break your streak! You haven't submitted today for: {games_list}")
            sent += 1
        except Exception:
            log.warning("Could not DM reminder to user %s", user_id)
    if sent:
        log.info("Sent streak reminders to %d user(s)", sent)
