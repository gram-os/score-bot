import discord
from discord import app_commands

from bot.database import get_personal_bests, get_streak, log_usage_event
from bot.helpers import game_autocomplete_choices, resolve_game_label


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="best", description="Show personal bests for a game")
    @app_commands.describe(
        game="Which game to look up",
        user="Player to look up (defaults to you)",
    )
    async def best(
        interaction: discord.Interaction,
        game: str,
        user: discord.Member = None,
    ) -> None:
        target = user or interaction.user
        target_id = str(target.id)
        game_name = resolve_game_label(registry, game)

        with Session() as session:
            bests = get_personal_bests(session, target_id, game)
            streak = get_streak(session, target_id, game) if bests else 0
            log_usage_event(
                session,
                "command.best",
                str(interaction.user.id),
                interaction.user.display_name,
                {"game": game, "target": target.display_name},
            )
            session.commit()

        if bests is None:
            await interaction.response.send_message(
                f"**{target.display_name}** hasn't submitted any **{game_name}** scores yet!"
            )
            return

        puzzle_num = bests.best_raw_data.get("puzzle_number")
        best_detail = f"{bests.best_score:.0f} pts"
        if puzzle_num is not None:
            best_detail += f" (puzzle #{puzzle_num}, {bests.best_date})"
        else:
            best_detail += f" ({bests.best_date})"

        embed = discord.Embed(
            title=f"{game_name} — {target.display_name}'s Bests",
            color=discord.Color.green(),
        )
        embed.add_field(name="Best Score", value=best_detail, inline=False)
        embed.add_field(name="Average Score", value=f"{bests.avg_score:.1f} pts", inline=True)
        embed.add_field(name="Total Submissions", value=str(bests.count), inline=True)
        if streak >= 1:
            embed.add_field(name="Current Streak", value=f"🔥 {streak} days", inline=True)

        await interaction.response.send_message(embed=embed)

    @best.autocomplete("game")
    async def best_game_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return game_autocomplete_choices(registry, current)
