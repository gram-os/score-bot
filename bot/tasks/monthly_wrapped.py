import asyncio
import calendar
import logging
from datetime import datetime, timezone

import discord

from bot.db.monthly_stats import (
    MonthlyGameStat,
    MonthlyWrapped,
    get_monthly_active_user_ids,
    get_monthly_wrapped,
    monthly_report_already_sent,
    prev_month,
    snapshot_month,
)
from bot.db.usage import log_usage_event

log = logging.getLogger(__name__)

_DM_DELAY_SECONDS = 0.5


def _score_delta_str(delta: float) -> str:
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.0f}"


def _game_stats_value(game_stats: list[MonthlyGameStat]) -> str:
    lines = []
    for g in game_stats:
        delta = (
            f" ({_score_delta_str(g.score_delta)} vs last mo.)"
            if g.score_delta is not None
            else ""
        )
        lines.append(f"**{g.game_name}**: {g.submissions}× · avg {g.avg_base_score:.0f}{delta}")
    return "\n".join(lines)


def _format_wrapped_embed(w: MonthlyWrapped) -> discord.Embed:
    month_name = calendar.month_name[w.month]
    embed = discord.Embed(
        title=f"📊 Your {month_name} {w.year} Wrapped",
        color=discord.Color.blurple(),
    )

    rank_str = f"#{w.rank} of {w.player_count}" if w.rank else "unranked"
    embed.description = (
        f"**{w.total_submissions}** submissions · **{w.total_points:.0f}** pts · "
        f"**{len(w.game_stats)}** game{'s' if len(w.game_stats) != 1 else ''}\n"
        f"Monthly rank: **{rank_str}**"
    )

    if w.favorite_game_name:
        embed.add_field(name="🎯 Ride-or-die", value=w.favorite_game_name, inline=True)

    if w.best_score is not None and w.best_score_game:
        date_str = (
            f" on {w.best_score_date.strftime('%b')} {w.best_score_date.day}"
            if w.best_score_date
            else ""
        )
        embed.add_field(
            name="⚡ Best moment",
            value=f"{w.best_score:.0f} pts in {w.best_score_game}{date_str}",
            inline=True,
        )

    if w.score_delta_pct is not None:
        embed.add_field(
            name="📈 vs last month",
            value=f"{_score_delta_str(w.score_delta_pct)}%",
            inline=True,
        )

    embed.add_field(
        name="🗓️ Consistency",
        value=f"{w.active_days}/{w.days_in_month} days",
        inline=True,
    )

    if w.speed_bonuses:
        embed.add_field(name="🚀 Speed bonuses", value=f"{w.speed_bonuses}× top 3", inline=True)

    if w.pbs_set:
        embed.add_field(
            name="🏅 New personal bests",
            value=f"{w.pbs_set} game{'s' if w.pbs_set != 1 else ''}",
            inline=True,
        )

    if w.achievements_earned:
        embed.add_field(
            name="🏆 Achievements",
            value=f"{w.achievements_earned} unlocked",
            inline=True,
        )

    if w.new_games:
        embed.add_field(name="✨ New this month", value=", ".join(w.new_games), inline=False)

    if w.peak_hour is not None:
        embed.add_field(name="🕐 Peak hour", value=f"{w.peak_hour:02d}:00 UTC", inline=True)

    if w.game_stats:
        embed.add_field(name="📋 By game", value=_game_stats_value(w.game_stats), inline=False)

    return embed


async def send_monthly_wrapped(client: discord.Client, Session) -> None:
    now = datetime.now(timezone.utc)
    year, month = prev_month(now.year, now.month)

    with Session() as session:
        snapshot_month(session, year, month)
        session.commit()
        user_ids = get_monthly_active_user_ids(session, year, month)

    log.info(
        "Monthly wrapped: %d eligible users for %d-%02d", len(user_ids), year, month
    )
    sent = 0

    for user_id in user_ids:
        with Session() as session:
            if monthly_report_already_sent(session, user_id, year, month):
                continue
            wrapped = get_monthly_wrapped(session, user_id, year, month)
            if not wrapped:
                continue

        embed = _format_wrapped_embed(wrapped)
        username = wrapped.username
        try:
            discord_user = await client.fetch_user(int(user_id))
            await discord_user.send(embed=embed)

            with Session() as session:
                log_usage_event(
                    session,
                    "monthly_report.sent",
                    user_id,
                    username,
                    {"year": year, "month": month},
                )
                session.commit()

            sent += 1
        except Exception:
            log.warning("Monthly wrapped: could not DM user %s", user_id)

        await asyncio.sleep(_DM_DELAY_SECONDS)

    log.info(
        "Monthly wrapped: sent %d/%d for %d-%02d", sent, len(user_ids), year, month
    )
