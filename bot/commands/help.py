import discord
from discord import app_commands


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="help", description="How to use this bot")
    async def help_command(interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Score Bot — How It Works",
            description=(
                "Just paste your daily puzzle results in this channel and the bot "
                "automatically tracks your score. No commands needed to submit!"
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Tracked Games",
            value=(
                "Wordle · Glyph · Enclose Horse · Mini Crossword · Quordle · Connections\n"
                "Use `/games` to see the current list."
            ),
            inline=False,
        )
        embed.add_field(
            name="Scoring",
            value=(
                "Each submission earns a base score plus a speed bonus: "
                "**+15** for 1st, **+10** for 2nd, **+5** for 3rd submission of the day per game."
            ),
            inline=False,
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/profile` — public score card with rank and achievements\n"
                "`/achievements` — full achievement list with descriptions\n"
                "`/mystats` — your personal stats, streaks, and achievements\n"
                "`/leaderboard` — rankings by game and time period\n"
                "`/best` — personal bests and stats for a game\n"
                "`/vs` — head-to-head comparison against another player\n"
                "`/suggest` — suggest a new game to add\n"
                "`/remind` — opt in to streak reminder DMs\n"
                "`/games` — list currently tracked games"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
