import logging

import discord
from discord import app_commands
from sqlalchemy.orm import sessionmaker

from bot.db.homunculus import get_homunculus_upgrades

log = logging.getLogger(__name__)


def register(tree: app_commands.CommandTree, registry, Session: sessionmaker) -> None:
    @tree.command(name="homunculus", description="Show the homunculus upgrade history")
    async def homunculus(interaction: discord.Interaction) -> None:
        with Session() as session:
            upgrades = get_homunculus_upgrades(session)

        if not upgrades:
            await interaction.response.send_message("The homunculus has no upgrades yet.", ephemeral=True)
            return

        embed = discord.Embed(title="The Homunculus", color=discord.Color.purple())
        lines = [f"**{i + 1}.** {u.upgrade_text}" for i, u in enumerate(upgrades)]
        embed.description = "\n".join(lines)
        embed.set_footer(text=f"{len(upgrades)} upgrade{'s' if len(upgrades) != 1 else ''} so far")
        await interaction.response.send_message(embed=embed)
