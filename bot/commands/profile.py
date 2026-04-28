import logging

import discord
from discord import app_commands

from bot.achievements import ACHIEVEMENTS, resolve_achievement_def
from bot.database import (
    get_current_season,
    get_user_achievements,
    get_user_best_streaks,
    get_user_total_freezes,
    log_usage_event,
)
from bot.helpers import UserOverview, format_badges, get_user_overview

log = logging.getLogger(__name__)


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="profile", description="View a player's score card")
    @app_commands.describe(user="Player to view (defaults to you)")
    async def profile(
        interaction: discord.Interaction,
        user: discord.Member = None,
    ) -> None:
        target = user or interaction.user
        target_id = str(target.id)

        with Session() as session:
            overview: UserOverview = get_user_overview(session, target_id)
            season = get_current_season(session)
            season_label = season.name if season else None
            best_current, best_ever = get_user_best_streaks(session, target_id)
            total_freezes = get_user_total_freezes(session, target_id)
            user_achievements = get_user_achievements(session, target_id)
            earned_count = sum(1 for ua in user_achievements if resolve_achievement_def(ua.achievement_slug))
            achievement_badges = format_badges(user_achievements)
            log_usage_event(
                session,
                "command.profile",
                str(interaction.user.id),
                interaction.user.display_name,
                {"target": target.display_name},
            )
            session.commit()

        total_achievements = len(ACHIEVEMENTS)
        avg_score = overview.total_pts / overview.total_subs if overview.total_subs else 0.0

        rank_str = f"#{overview.overall_rank}" if overview.overall_rank else "Unranked"
        subtitle_parts = []
        if season_label:
            subtitle_parts.append(season_label)
        subtitle_parts.append(rank_str)

        embed = discord.Embed(
            title=f"🎮  {target.display_name}'s Score Card",
            description="  ·  ".join(subtitle_parts),
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(
            name="📊 Stats",
            value=f"{overview.total_pts:.0f} pts  ·  {overview.total_subs} submissions  ·  {avg_score:.1f} avg",
            inline=False,
        )

        streak_current = f"🔥 {best_current} days" if best_current else "—"
        freeze_str = f"  ·  🧊 {total_freezes} freeze{'s' if total_freezes != 1 else ''}" if total_freezes > 0 else ""
        embed.add_field(
            name="🔥 Streaks",
            value=f"Current: {streak_current}  ·  Best Ever: {best_ever} days{freeze_str}",
            inline=False,
        )

        embed.add_field(
            name=f"🏆 Achievements ({earned_count} / {total_achievements})",
            value=achievement_badges,
            inline=False,
        )

        log.info("/profile for %s by %s", target.display_name, interaction.user.display_name)
        await interaction.response.send_message(embed=embed)
