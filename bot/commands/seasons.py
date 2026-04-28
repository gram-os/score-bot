import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from sqlalchemy import func, select

from bot.database import Season, Submission, User, get_current_season

log = logging.getLogger(__name__)


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="seasons", description="View season history and champions")
    async def seasons(interaction: discord.Interaction) -> None:
        with Session() as session:
            all_seasons = session.scalars(select(Season).order_by(Season.start_date.desc())).all()

            if not all_seasons:
                await interaction.response.send_message("No seasons have been set up yet.", ephemeral=True)
                return

            today = datetime.now(timezone.utc).date()
            current_season = get_current_season(session)

            embed = discord.Embed(title="Season History", color=discord.Color.gold())

            for s in all_seasons:
                is_current = current_season is not None and s.id == current_season.id
                is_future = s.start_date > today

                if is_current:
                    days_left = (s.end_date - today).days
                    header = f"🟢 {s.name} (Current · {days_left}d remaining)"
                    detail = "Season in progress"
                elif is_future:
                    header = f"🔜 {s.name}"
                    detail = f"Starts {s.start_date}"
                else:
                    champion_row = session.execute(
                        select(User.username, func.sum(Submission.total_score).label("pts"))
                        .join(User, Submission.user_id == User.user_id)
                        .where(
                            Submission.date >= s.start_date,
                            Submission.date <= s.end_date,
                        )
                        .group_by(Submission.user_id)
                        .order_by(func.sum(Submission.total_score).desc())
                        .limit(1)
                    ).first()
                    detail = (
                        f"👑 {champion_row.username} — {champion_row.pts:.0f} pts" if champion_row else "No submissions"
                    )
                    header = s.name

                embed.add_field(
                    name=header,
                    value=f"{s.start_date} → {s.end_date}\n{detail}",
                    inline=False,
                )

        log.info("/seasons by %s", interaction.user.display_name)
        await interaction.response.send_message(embed=embed)
