import logging

import discord
from discord import app_commands

from bot.database import get_preference, set_preference

log = logging.getLogger(__name__)


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="remind", description="Toggle streak reminders for yourself")
    @app_commands.describe(threshold="Minimum streak length to trigger a reminder (0 = opt out, default 3)")
    async def remind(interaction: discord.Interaction, threshold: int = 3) -> None:
        user_id = str(interaction.user.id)
        with Session() as session:
            pref = get_preference(session, user_id)
            currently_opted_in = pref is not None and pref.remind_streak_days > 0

            if threshold == 0 or currently_opted_in:
                set_preference(session, user_id, remind_streak_days=0)
                session.commit()
                log.info("/remind: %s opted out of streak reminders", interaction.user.display_name)
                await interaction.response.send_message(
                    "Streak reminders **disabled**. You won't receive reminder DMs.",
                    ephemeral=True,
                )
            else:
                set_preference(session, user_id, remind_streak_days=threshold)
                session.commit()
                log.info(
                    "/remind: %s opted in (threshold=%d)",
                    interaction.user.display_name,
                    threshold,
                )
                await interaction.response.send_message(
                    f"Streak reminders **enabled** — you'll be reminded when your streak reaches **{threshold}** days.",
                    ephemeral=True,
                )
