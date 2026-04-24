import discord
from discord import app_commands

from bot.database import get_head_to_head, log_usage_event
from bot.helpers import game_autocomplete_choices, resolve_game_label


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="vs", description="Head-to-head comparison against another player")
    @app_commands.describe(
        opponent="The player to compare against",
        game="Which game to compare (default: all games)",
    )
    async def vs(
        interaction: discord.Interaction,
        opponent: discord.Member,
        game: str = None,
    ) -> None:
        caller_id = str(interaction.user.id)
        opponent_id = str(opponent.id)

        if caller_id == opponent_id:
            await interaction.response.send_message("You can't challenge yourself!", ephemeral=True)
            return

        game_label = resolve_game_label(registry, game)

        with Session() as session:
            result = get_head_to_head(session, caller_id, opponent_id, game)
            log_usage_event(
                session,
                "command.vs",
                caller_id,
                interaction.user.display_name,
                {"opponent": opponent.display_name, "game": game or "all"},
            )
            session.commit()

        if result is None:
            await interaction.response.send_message(
                f"No overlapping submissions found between you and "
                f"**{opponent.display_name}**"
                + (f" in **{game_label}**" if game else "")
                + ". Play some games together first!",
            )
            return

        overlapping = result.overlapping_days
        caller_win_rate = result.caller_wins / overlapping * 100 if overlapping else 0
        opponent_win_rate = result.opponent_wins / overlapping * 100 if overlapping else 0

        embed = discord.Embed(
            title=f"Head-to-Head — {game_label}",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Player",
            value=f"{result.caller_username}\n{result.opponent_username}",
            inline=True,
        )
        embed.add_field(
            name="Total Score",
            value=(f"{result.caller_total_score:.0f}\n{result.opponent_total_score:.0f}"),
            inline=True,
        )
        embed.add_field(
            name="Win Rate",
            value=(
                f"{caller_win_rate:.0f}% ({result.caller_wins}W/"
                f"{result.opponent_wins}L/{result.ties}T)\n"
                f"{opponent_win_rate:.0f}% ({result.opponent_wins}W/"
                f"{result.caller_wins}L/{result.ties}T)"
            ),
            inline=True,
        )
        embed.set_footer(text=f"Based on {overlapping} overlapping day(s)")

        await interaction.response.send_message(embed=embed)

    @vs.autocomplete("game")
    async def vs_game_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return game_autocomplete_choices(registry, current)
