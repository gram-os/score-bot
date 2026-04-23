import logging

import discord
from discord import app_commands

from bot.config import PERIOD_CHOICES, PERIOD_LABELS
from bot.database import Game, get_all_streaks, get_current_season, get_leaderboard
from bot.helpers import game_autocomplete_choices, resolve_game_label

log = logging.getLogger(__name__)


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="leaderboard", description="Show the leaderboard")
    @app_commands.describe(
        game="Which game to show (default: all)",
        period="Time period (default: alltime)",
    )
    @app_commands.choices(period=PERIOD_CHOICES)
    async def leaderboard(
        interaction: discord.Interaction,
        game: str = None,
        period: app_commands.Choice[str] = None,
    ) -> None:
        game_id = game if game else "all"
        period_value = period.value if period else "alltime"

        with Session() as session:
            rows = get_leaderboard(
                session,
                period=period_value,
                game_id=None if game_id == "all" else game_id,
            )
            if game_id == "all":
                enabled_games = session.query(Game).filter(Game.enabled.is_(True)).all()
                streak_map: dict[str, int] = {}
                for g in enabled_games:
                    for uid, _, streak in get_all_streaks(session, g.id):
                        if streak > streak_map.get(uid, 0):
                            streak_map[uid] = streak
            else:
                streak_map = {uid: streak for uid, _, streak in get_all_streaks(session, game_id)}

            if period_value == "season":
                current_season = get_current_season(session)
                period_label = current_season.name if current_season else "Season"
            else:
                period_label = PERIOD_LABELS[period_value]

        game_label = resolve_game_label(registry, game_id)
        title = f"Leaderboard — {game_label} ({period_label})"
        embed = discord.Embed(title=title, color=discord.Color.gold())

        if not rows:
            embed.description = "No submissions yet."
        else:
            lines = []
            for row in rows[:15]:
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(row.rank, f"`#{row.rank}`")
                streak = streak_map.get(row.user_id, 0)
                streak_str = f" 🔥{streak}" if streak >= 1 else ""
                lines.append(
                    f"{medal} **{row.username}**{streak_str} — {row.total_score:.0f} pts"
                    f" ({row.submission_count} sub{'s' if row.submission_count != 1 else ''})"
                )
            embed.description = "\n".join(lines)

        log.info(
            "/leaderboard by %s (game=%s, period=%s)",
            interaction.user.display_name,
            game_id,
            period_value,
        )
        await interaction.response.send_message(embed=embed)

    @leaderboard.autocomplete("game")
    async def leaderboard_game_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return game_autocomplete_choices(registry, current, include_all=True)
