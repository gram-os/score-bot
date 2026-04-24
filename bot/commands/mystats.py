import logging

import discord
from discord import app_commands
from sqlalchemy import select

from bot.achievements import ACHIEVEMENTS
from bot.database import (
    Game,
    get_current_season,
    get_leaderboard,
    get_personal_bests,
    get_user_achievements,
    get_user_streak,
    log_usage_event,
)
from bot.helpers import UserOverview, format_badges, get_user_overview

log = logging.getLogger(__name__)


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="mystats", description="View your personal stats, streaks, and achievements")
    async def mystats(interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        await interaction.response.defer(ephemeral=True)

        with Session() as session:
            overview: UserOverview = get_user_overview(session, user_id)

            season = get_current_season(session)
            season_name = season.name if season else None
            season_row = None
            if season:
                season_rows = get_leaderboard(session, period="season")
                season_row = next((r for r in season_rows if r.user_id == user_id), None)

            enabled_games = session.execute(select(Game).where(Game.enabled.is_(True))).scalars().all()

            game_stats = []
            for g in enabled_games:
                bests = get_personal_bests(session, user_id, g.id)
                if not bests:
                    continue
                streak_row = get_user_streak(session, user_id, g.id)
                game_stats.append(
                    (
                        g.name,
                        bests,
                        streak_row.current_streak if streak_row else 0,
                        streak_row.longest_streak if streak_row else 0,
                        streak_row.freeze_count if streak_row else 0,
                    )
                )

            user_achievements = get_user_achievements(session, user_id)
            earned_ach_count = sum(1 for ua in user_achievements if ua.achievement_slug in ACHIEVEMENTS)
            badges = format_badges(user_achievements, separator=" · ")
            log_usage_event(session, "command.mystats", user_id, interaction.user.display_name)
            session.commit()

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Stats",
            color=discord.Color.gold(),
        )

        rank_str = f"#{overview.overall_rank}" if overview.overall_rank else "Unranked"
        embed.add_field(
            name="Overall",
            value=f"{rank_str} · {overview.total_pts:.0f} pts · {overview.total_subs} submissions",
            inline=False,
        )

        if season_name:
            s_rank = f"#{season_row.rank}" if season_row else "Unranked"
            s_pts = season_row.total_score if season_row else 0.0
            s_subs = season_row.submission_count if season_row else 0
            embed.add_field(
                name=f"Season ({season_name})",
                value=f"{s_rank} · {s_pts:.0f} pts · {s_subs} submissions",
                inline=False,
            )

        for game_name, bests, cur, best_streak, freezes in game_stats:
            if cur >= 1:
                streak_str = f"🔥 {cur} day streak"
                if best_streak > cur:
                    streak_str += f" (best: {best_streak})"
            else:
                streak_str = "No active streak"
            freeze_str = f" · 🧊 {freezes} freeze{'s' if freezes != 1 else ''}" if freezes > 0 else ""

            embed.add_field(
                name=game_name,
                value=(
                    f"{bests.count} subs · Best: {bests.best_score:.0f} · "
                    f"Avg: {bests.avg_score:.1f}\n"
                    f"{streak_str}{freeze_str}"
                ),
                inline=True,
            )

        if earned_ach_count:
            embed.add_field(
                name=f"Achievements ({earned_ach_count})",
                value=badges,
                inline=False,
            )
        else:
            embed.add_field(name="Achievements", value="None yet — keep playing!", inline=False)

        log.info("/mystats by %s", interaction.user.display_name)
        await interaction.followup.send(embed=embed, ephemeral=True)
