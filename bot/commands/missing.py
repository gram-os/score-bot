import logging
from datetime import datetime

import discord
from discord import app_commands
from sqlalchemy import select

from bot.db.config import SCORING_TZ
from bot.db.models import Game, Submission

log = logging.getLogger(__name__)


def get_missing_games(session, user_id: str) -> list[str]:
    today = datetime.now(SCORING_TZ).date()

    enabled_games = session.execute(select(Game.id, Game.name).where(Game.enabled.is_(True)).order_by(Game.name)).all()

    submitted_ids = {
        row.game_id
        for row in session.execute(
            select(Submission.game_id).where(Submission.user_id == user_id, Submission.date == today)
        ).all()
    }

    return [name for gid, name in enabled_games if gid not in submitted_ids]


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="missing", description="See which games you haven't submitted today")
    async def missing(interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        await interaction.response.defer(ephemeral=True)

        with Session() as session:
            games = get_missing_games(session, user_id)

        if not games:
            embed = discord.Embed(
                title="All done!",
                description="You've submitted every enabled game today.",
                color=discord.Color.green(),
            )
            log.info("/missing by %s — all submitted", interaction.user.display_name)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        lines = [f"• {name}" for name in games]
        embed = discord.Embed(
            title=f"Missing today — {interaction.user.display_name}",
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        embed.set_footer(text=f"{len(games)} game{'s' if len(games) != 1 else ''} remaining")
        log.info("/missing by %s — %d games remaining", interaction.user.display_name, len(games))
        await interaction.followup.send(embed=embed, ephemeral=True)
