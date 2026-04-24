import discord
from discord import app_commands

from bot.database import Game, log_usage_event


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="games", description="List enabled games")
    async def games(interaction: discord.Interaction) -> None:
        with Session() as session:
            enabled = session.query(Game).filter(Game.enabled.is_(True)).all()
            log_usage_event(session, "command.games", str(interaction.user.id), interaction.user.display_name)
            session.commit()

        if not enabled:
            await interaction.response.send_message("No games are currently enabled.")
            return

        embed = discord.Embed(title="Enabled Games", color=discord.Color.blurple())
        lines = [f"**{g.name}** (`{g.id}`)" for g in enabled]
        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)
