import logging

import discord
from discord import app_commands

from bot.achievements import ACHIEVEMENTS
from bot.database import get_user_achievements, log_usage_event

log = logging.getLogger(__name__)


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="achievements", description="View all achievements and what they require")
    @app_commands.describe(user="Player to view (defaults to you)")
    async def achievements_command(
        interaction: discord.Interaction,
        user: discord.Member = None,
    ) -> None:
        target = user or interaction.user
        target_id = str(target.id)

        with Session() as session:
            user_achievements = get_user_achievements(session, target_id)
            log_usage_event(
                session,
                "command.achievements",
                str(interaction.user.id),
                interaction.user.display_name,
                {"target": target.display_name},
            )
            session.commit()

        earned_slugs = {ua.achievement_slug for ua in user_achievements}
        total = len(ACHIEVEMENTS)
        earned_count = len(earned_slugs & ACHIEVEMENTS.keys())

        lines = []
        for ach in ACHIEVEMENTS.values():
            prefix = "✅" if ach.slug in earned_slugs else "🔒"
            lines.append(f"{prefix} {ach.icon} **{ach.name}** — {ach.description}")

        embed = discord.Embed(
            title=f"🏆 {target.display_name}'s Achievements ({earned_count} / {total})",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )

        log.info("/achievements for %s by %s", target.display_name, interaction.user.display_name)
        await interaction.response.send_message(embed=embed)
