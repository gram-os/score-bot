import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from sqlalchemy import func, select

from bot.database import Season, Submission, User

log = logging.getLogger(__name__)


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="halloffame", description="View all past season champions")
    async def halloffame(interaction: discord.Interaction) -> None:
        with Session() as session:
            embed = _build_halloffame_embed(session)
        log.info("/halloffame by %s", interaction.user.display_name)
        await interaction.response.send_message(embed=embed)


def _get_season_champion(session, season: Season):
    return session.execute(
        select(
            User.username,
            Submission.user_id,
            func.sum(Submission.total_score).label("pts"),
            func.count(Submission.id).label("cnt"),
        )
        .join(User, Submission.user_id == User.user_id)
        .where(Submission.date >= season.start_date, Submission.date <= season.end_date)
        .group_by(Submission.user_id)
        .order_by(func.sum(Submission.total_score).desc())
        .limit(1)
    ).first()


def _build_halloffame_embed(session) -> discord.Embed:
    today = datetime.now(timezone.utc).date()
    past_seasons = session.scalars(select(Season).where(Season.end_date < today).order_by(Season.end_date.desc())).all()

    embed = discord.Embed(title="🏆 Hall of Fame", color=discord.Color.gold())

    if not past_seasons:
        embed.description = "No seasons have ended yet."
        return embed

    champion_win_count: dict[str, int] = {}
    entries = []

    for season in past_seasons:
        champion = _get_season_champion(session, season)
        entries.append((season, champion))
        if champion:
            champion_win_count[champion.user_id] = champion_win_count.get(champion.user_id, 0) + 1

    for season, champion in entries:
        if champion:
            wins = champion_win_count[champion.user_id]
            multi = f" ({wins}× champ)" if wins > 1 else ""
            value = f"👑 **{champion.username}**{multi} — {champion.pts:.0f} pts · {champion.cnt} submissions"
        else:
            value = "No submissions"
        embed.add_field(
            name=f"{season.name}  ({season.start_date} → {season.end_date})",
            value=value,
            inline=False,
        )

    return embed
