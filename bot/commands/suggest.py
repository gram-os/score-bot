import logging

import discord
from discord import app_commands
from sqlalchemy import select

from bot.database import Game, add_suggestion, find_similar_name, get_unpolled_suggestions

log = logging.getLogger(__name__)


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="suggest", description="Suggest a game to be added to the bot")
    @app_commands.describe(
        game_name="Name of the game you want to suggest",
        description="Why should we add this game? (optional)",
    )
    async def suggest(
        interaction: discord.Interaction,
        game_name: str,
        description: str = None,
    ) -> None:
        with Session() as session:
            game_names = [g.name for g in session.execute(select(Game)).scalars()]
            similar_game = find_similar_name(game_name, game_names)
            if similar_game:
                await interaction.response.send_message(
                    f"**{game_name}** looks similar to an already-tracked game "
                    f"(**{similar_game}**). Did you mean something different?",
                    ephemeral=True,
                )
                return

            pending = get_unpolled_suggestions(session)
            pending_names = [s.game_name for s in pending]
            similar_pending = find_similar_name(game_name, pending_names)
            if similar_pending:
                await interaction.response.send_message(
                    f"**{game_name}** looks similar to a pending suggestion "
                    f"(**{similar_pending}**) that's already in the queue.",
                    ephemeral=True,
                )
                return

            add_suggestion(
                session,
                user_id=str(interaction.user.id),
                username=interaction.user.display_name,
                game_name=game_name,
                description=description,
            )
            session.commit()
            log.info("/suggest by %s: %s", interaction.user.display_name, game_name)

        await interaction.response.send_message(
            f"✅ **{game_name}** has been added to the suggestion list and will appear in tomorrow's poll!",
            ephemeral=True,
        )
