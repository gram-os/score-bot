import datetime
import logging

import discord
from sqlalchemy import func, select

from bot.database import (
    Submission,
    User,
    award_season_champion,
    get_season_ending_yesterday,
    get_weekly_digest,
    get_yesterday_digest,
)

log = logging.getLogger(__name__)


async def send_daily_digest(channel: discord.TextChannel | None, Session) -> None:
    if channel is None:
        log.warning("Digest: channel not found")
        return

    with Session() as session:
        digest_data = get_yesterday_digest(session)

    if not any(d.participant_count > 0 for d in digest_data):
        return

    yesterday = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).date()
    embed = discord.Embed(title=f"Daily Digest — {yesterday}", color=discord.Color.blurple())

    lines = []
    for d in digest_data:
        if d.participant_count == 0:
            lines.append(f"**{d.game_name}** — no activity")
        else:
            players = f"{d.participant_count} player{'s' if d.participant_count != 1 else ''}"
            streak_str = f" | 🔥 Top streak: {d.top_streak}" if d.top_streak >= 1 else ""
            lines.append(
                f"**{d.game_name}** — 🏆 {d.winner_username} ({d.winner_score:.0f} pts) | {players}{streak_str}"
            )
    embed.description = "\n".join(lines)
    await channel.send(embed=embed)
    log.info("Daily digest sent for %s", yesterday)


async def send_weekly_digest(client: discord.Client, channel: discord.TextChannel | None, Session) -> None:
    if channel is None:
        log.warning("Weekly digest: channel not found")
        return

    with Session() as session:
        data = get_weekly_digest(session)
        ended_season = get_season_ending_yesterday(session)
        season_champion_user_id: str | None = None
        season_end_embed: discord.Embed | None = None

        if ended_season:
            top_rows = session.execute(
                select(
                    Submission.user_id,
                    User.username,
                    func.sum(Submission.total_score).label("pts"),
                    func.count(Submission.id).label("cnt"),
                )
                .join(User, Submission.user_id == User.user_id)
                .where(
                    Submission.date >= ended_season.start_date,
                    Submission.date <= ended_season.end_date,
                )
                .group_by(Submission.user_id)
                .order_by(func.sum(Submission.total_score).desc())
                .limit(3)
            ).all()

            if top_rows:
                champion_row = top_rows[0]
                newly_awarded = award_season_champion(session, champion_row.user_id, ended_season.id)
                session.commit()
                if newly_awarded:
                    season_champion_user_id = champion_row.user_id
                    log.info(
                        "Season Champion awarded to %s for season %s",
                        champion_row.username,
                        ended_season.name,
                    )

                medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                standing_lines = [
                    f"{medals[i + 1]} **{row.username}** — {row.pts:.0f} pts ({row.cnt} submissions)"
                    for i, row in enumerate(top_rows)
                ]
                season_end_embed = discord.Embed(
                    title=f"🏁  {ended_season.name} has ended!",
                    color=discord.Color.gold(),
                )
                season_end_embed.add_field(
                    name="Final Standings",
                    value="\n".join(standing_lines),
                    inline=False,
                )
                season_end_embed.set_footer(text=f"{ended_season.start_date} – {ended_season.end_date}")

    if season_end_embed is not None:
        await channel.send(embed=season_end_embed)

    if season_champion_user_id:
        try:
            champ_user = await client.fetch_user(int(season_champion_user_id))
            await champ_user.send(
                f"👑 You finished **#1** in the **{ended_season.name}** season! "
                "Achievement unlocked: **Season Champion**."
            )
        except Exception:
            log.warning("Could not DM season champion %s", season_champion_user_id)

    if data.total_submissions == 0:
        return

    embed = discord.Embed(
        title=f"Weekly Recap — {data.week_start} to {data.week_end}",
        color=discord.Color.green(),
    )
    embed.add_field(
        name="Total Activity",
        value=f"{data.total_submissions} submissions · {data.unique_players} players",
        inline=False,
    )
    if data.top_scorer_username:
        embed.add_field(
            name="🏆 Top Scorer",
            value=f"**{data.top_scorer_username}** — {data.top_scorer_points:.0f} pts",
            inline=True,
        )
    if data.most_active_username:
        embed.add_field(
            name="📊 Most Active",
            value=f"**{data.most_active_username}** — {data.most_active_submissions} submissions",
            inline=True,
        )
    if data.best_single_username:
        embed.add_field(
            name="⚡ Best Single Score",
            value=(
                f"**{data.best_single_username}** — {data.best_single_score:.0f} pts"
                + (f" ({data.best_single_game})" if data.best_single_game else "")
            ),
            inline=True,
        )
    if data.top_streak_username and data.top_streak_days >= 1:
        embed.add_field(
            name="🔥 Longest Streak",
            value=f"**{data.top_streak_username}** — {data.top_streak_days} days",
            inline=True,
        )

    await channel.send(embed=embed)
    log.info("Weekly digest sent for week ending %s", data.week_end)
