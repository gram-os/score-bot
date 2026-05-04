import logging
from datetime import datetime

import discord
from discord import app_commands
from sqlalchemy import select

from bot.db.config import SCORING_TZ
from bot.db.models import Game, Submission

log = logging.getLogger(__name__)


def format_submission_line(game_name: str, submission: Submission) -> str:
    total = int(submission.total_score)
    base = int(submission.base_score)
    bonus = int(submission.speed_bonus)
    return f"**{game_name}** {total} ({base} + {bonus})"


def get_today_submissions(session, user_id: str) -> list[tuple[str, Submission]]:
    today = datetime.now(SCORING_TZ).date()
    rows = session.execute(
        select(Submission, Game)
        .join(Game, Submission.game_id == Game.id)
        .where(Submission.user_id == user_id, Submission.date == today)
        .order_by(Game.name)
    ).all()
    return [(game.name, sub) for sub, game in rows]


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="submitted", description="See which games you've submitted today and your scores")
    async def submitted(interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        await interaction.response.defer(ephemeral=True)

        with Session() as session:
            entries = get_today_submissions(session, user_id)

        if not entries:
            await interaction.followup.send("You haven't submitted any games today.", ephemeral=True)
            return

        lines = [format_submission_line(name, sub) for name, sub in entries]
        embed = discord.Embed(
            title=f"Today's submissions — {interaction.user.display_name}",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        log.info("/submitted by %s (%d games)", interaction.user.display_name, len(entries))
        await interaction.followup.send(embed=embed, ephemeral=True)
