import logging
from datetime import date, datetime, timezone

import discord
from discord import app_commands

from bot.config import PERIOD_CHOICES, PERIOD_LABELS
from bot.database import (
    Game,
    get_all_streaks,
    get_current_season,
    get_leaderboard,
    get_season_champion_user_ids,
    log_usage_event,
)
from bot.helpers import game_autocomplete_choices, resolve_game_label

log = logging.getLogger(__name__)

_CUSTOM_RANGE_MAX_DAYS = 365


def _parse_custom_range(start: str | None, end: str | None) -> tuple[date, date] | str:
    if not start or not end:
        return "Custom period requires both `start` and `end` (YYYY-MM-DD)."
    try:
        start_d = datetime.strptime(start, "%Y-%m-%d").date()
        end_d = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        return "Could not parse dates. Use `YYYY-MM-DD` for both `start` and `end`."
    if end_d < start_d:
        return "`end` must be on or after `start`."
    if (end_d - start_d).days + 1 > _CUSTOM_RANGE_MAX_DAYS:
        return f"Custom range capped at {_CUSTOM_RANGE_MAX_DAYS} days."
    return start_d, end_d


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="leaderboard", description="Show the leaderboard")
    @app_commands.describe(
        game="Which game to show (default: all)",
        period="Time period (default: all time, or all periods when a game is selected)",
        start="Start date for custom range (YYYY-MM-DD)",
        end="End date for custom range (YYYY-MM-DD)",
    )
    @app_commands.choices(period=PERIOD_CHOICES)
    async def leaderboard(
        interaction: discord.Interaction,
        game: str | None = None,
        period: app_commands.Choice[str] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> None:
        game_id = game if game else "all"
        game_label = resolve_game_label(registry, game_id)
        show_all_periods = game_id != "all" and period is None
        period_value = period.value if period else "alltime"

        custom_range: tuple[date, date] | None = None
        if period_value == "custom":
            parsed = _parse_custom_range(start, end)
            if isinstance(parsed, str):
                await interaction.response.send_message(parsed, ephemeral=True)
                return
            custom_range = parsed

        await interaction.response.defer()

        with Session() as session:
            if show_all_periods:
                embed = await _build_per_game_embed(session, game_id, game_label)
            else:
                embed = await _build_single_period_embed(
                    session, registry, game_id, game_label, period_value, custom_range
                )
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
        await interaction.followup.send(embed=embed)

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
    champion_ids = get_season_champion_user_ids(session)

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
            crown = " 👑" if row.user_id in champion_ids else ""
            lines.append(f"{medal} **{row.username}**{streak_str}{crown} — {row.total_score:.0f} pts")
        embed.add_field(name=period_label, value="\n".join(lines), inline=False)

    countdown = _season_countdown(current_season)
    if countdown:
        embed.set_footer(text=countdown)

    return embed


async def _build_single_period_embed(
    session,
    registry,
    game_id: str,
    game_label: str,
    period_value: str,
    custom_range: tuple[date, date] | None = None,
) -> discord.Embed:
    lb_kwargs: dict = {"period": period_value, "game_id": None if game_id == "all" else game_id}
    if custom_range is not None:
        lb_kwargs["start_date"] = custom_range[0]
        lb_kwargs["end_date"] = custom_range[1]
    rows = get_leaderboard(session, **lb_kwargs)

    if game_id == "all":
        enabled_games = session.query(Game).filter(Game.enabled.is_(True)).all()
        streak_map: dict[str, int] = {}
        for g in enabled_games:
            for uid, _, streak in get_all_streaks(session, g.id):
                if streak > streak_map.get(uid, 0):
                    streak_map[uid] = streak
    else:
        streak_map = {uid: streak for uid, _, streak in get_all_streaks(session, game_id)}

    champion_ids = get_season_champion_user_ids(session)
    current_season = get_current_season(session)
    if period_value == "season":
        period_label = current_season.name if current_season else "Season"
    elif period_value == "custom" and custom_range is not None:
        period_label = f"Custom: {custom_range[0]} → {custom_range[1]}"
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
            crown = " 👑" if row.user_id in champion_ids else ""
            lines.append(
                f"{medal} **{row.username}**{streak_str}{crown} — {row.total_score:.0f} pts"
                f" ({row.submission_count} sub{'s' if row.submission_count != 1 else ''})"
            )
        embed.description = "\n".join(lines)

    if period_value == "season":
        countdown = _season_countdown(current_season)
        if countdown:
            embed.set_footer(text=countdown)

    return embed
