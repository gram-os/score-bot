import logging
from datetime import datetime, timezone

import discord
from discord import app_commands

from bot.config import PERIOD_CHOICES, PERIOD_LABELS
from bot.database import Game, get_all_streaks, get_current_season, get_leaderboard, log_usage_event
from bot.helpers import game_autocomplete_choices, resolve_game_label

log = logging.getLogger(__name__)


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="leaderboard", description="Show the leaderboard")
    @app_commands.describe(
        game="Which game to show (default: all)",
        period="Time period (default: all time, or all periods when a game is selected)",
    )
    @app_commands.choices(period=PERIOD_CHOICES)
    async def leaderboard(
        interaction: discord.Interaction,
        game: str = None,
        period: app_commands.Choice[str] = None,
    ) -> None:
        game_id = game if game else "all"
        game_label = resolve_game_label(registry, game_id)
        show_all_periods = game_id != "all" and period is None
        period_value = period.value if period else "alltime"

        with Session() as session:
            if show_all_periods:
                embed = await _build_per_game_embed(session, game_id, game_label)
            else:
                embed = await _build_single_period_embed(session, registry, game_id, game_label, period_value)
            log_usage_event(
                session,
                "command.leaderboard",
                str(interaction.user.id),
                interaction.user.display_name,
                {"game": game_id, "period": period_value if not show_all_periods else "all"},
            )
            session.commit()

        log.info(
            "/leaderboard by %s (game=%s, period=%s)",
            interaction.user.display_name,
            game_id,
            period_value if not show_all_periods else "all",
        )
        await interaction.response.send_message(embed=embed)

    @leaderboard.autocomplete("game")
    async def leaderboard_game_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return game_autocomplete_choices(registry, current, include_all=True)


def _season_countdown(season) -> str | None:
    if season is None:
        return None
    today = datetime.now(timezone.utc).date()
    days_left = (season.end_date - today).days
    if days_left < 0 or days_left > 7:
        return None
    if days_left == 0:
        return f"⏳ Last day of {season.name}!"
    return f"⏳ {days_left} day{'s' if days_left != 1 else ''} remaining in {season.name}"


async def _build_per_game_embed(session, game_id: str, game_label: str) -> discord.Embed:
    embed = discord.Embed(title=f"Leaderboard — {game_label}", color=discord.Color.gold())
    streak_map = {uid: streak for uid, _, streak in get_all_streaks(session, game_id)}

    current_season = get_current_season(session)
    periods = [
        ("daily", "Today"),
        ("season", current_season.name if current_season else "Season"),
        ("alltime", "All Time"),
    ]

    for period_value, period_label in periods:
        rows = get_leaderboard(session, period=period_value, game_id=game_id)
        if not rows:
            embed.add_field(name=period_label, value="No submissions yet.", inline=False)
            continue
        lines = []
        for row in rows[:5]:
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(row.rank, f"`#{row.rank}`")
            streak = streak_map.get(row.user_id, 0)
            streak_str = f" 🔥{streak}" if streak >= 1 else ""
            lines.append(f"{medal} **{row.username}**{streak_str} — {row.total_score:.0f} pts")
        embed.add_field(name=period_label, value="\n".join(lines), inline=False)

    countdown = _season_countdown(current_season)
    if countdown:
        embed.set_footer(text=countdown)

    return embed


async def _build_single_period_embed(
    session, registry, game_id: str, game_label: str, period_value: str
) -> discord.Embed:
    rows = get_leaderboard(session, period=period_value, game_id=None if game_id == "all" else game_id)

    if game_id == "all":
        enabled_games = session.query(Game).filter(Game.enabled.is_(True)).all()
        streak_map: dict[str, int] = {}
        for g in enabled_games:
            for uid, _, streak in get_all_streaks(session, g.id):
                if streak > streak_map.get(uid, 0):
                    streak_map[uid] = streak
    else:
        streak_map = {uid: streak for uid, _, streak in get_all_streaks(session, game_id)}

    current_season = get_current_season(session)
    if period_value == "season":
        period_label = current_season.name if current_season else "Season"
    else:
        period_label = PERIOD_LABELS[period_value]

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

    if period_value == "season":
        countdown = _season_countdown(current_season)
        if countdown:
            embed.set_footer(text=countdown)

    return embed
