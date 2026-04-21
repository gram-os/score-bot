import logging
import os
from datetime import timezone

import discord
from discord import app_commands
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker

from bot.database import (
    Game,
    get_engine,
    get_leaderboard,
    is_duplicate,
    record_submission,
)
from bot.parsers.registry import ParserRegistry

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DISCORD_CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/data/scores.db")

GAME_CHOICES = [
    app_commands.Choice(name="All", value="all"),
    app_commands.Choice(name="Wordle", value="wordle"),
    app_commands.Choice(name="Glyph", value="glyph"),
    app_commands.Choice(name="Enclose Horse", value="enclose_horse"),
]

PERIOD_CHOICES = [
    app_commands.Choice(name="All Time", value="alltime"),
    app_commands.Choice(name="Daily", value="daily"),
    app_commands.Choice(name="Weekly", value="weekly"),
    app_commands.Choice(name="Monthly", value="monthly"),
]

PERIOD_LABELS = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "alltime": "All Time",
}


class ScoreBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.registry = ParserRegistry()

        engine = get_engine(DATABASE_PATH)
        self.Session = sessionmaker(bind=engine)

        self._register_commands()

    def _register_commands(self) -> None:
        @self.tree.command(name="leaderboard", description="Show the leaderboard")
        @app_commands.describe(
            game="Which game to show (default: all)",
            period="Time period (default: alltime)",
        )
        @app_commands.choices(game=GAME_CHOICES, period=PERIOD_CHOICES)
        async def leaderboard(
            interaction: discord.Interaction,
            game: app_commands.Choice[str] = None,
            period: app_commands.Choice[str] = None,
        ) -> None:
            game_id = game.value if game else "all"
            period_value = period.value if period else "alltime"

            with self.Session() as session:
                rows = get_leaderboard(
                    session,
                    period=period_value,
                    game_id=None if game_id == "all" else game_id,
                )

            game_label = game.name if game else "All Games"
            period_label = PERIOD_LABELS[period_value]
            title = f"Leaderboard — {game_label} ({period_label})"

            embed = discord.Embed(title=title, color=discord.Color.gold())

            if not rows:
                embed.description = "No submissions yet."
            else:
                lines = []
                for row in rows[:15]:
                    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(row.rank, f"`#{row.rank}`")
                    lines.append(
                        f"{medal} **{row.username}** — {row.total_score:.0f} pts"
                        f" ({row.submission_count} sub{'s' if row.submission_count != 1 else ''})"
                    )
                embed.description = "\n".join(lines)

            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="games", description="List enabled games")
        async def games(interaction: discord.Interaction) -> None:
            with self.Session() as session:
                enabled = session.query(Game).filter(Game.enabled.is_(True)).all()

            if not enabled:
                await interaction.response.send_message(
                    "No games are currently enabled."
                )
                return

            embed = discord.Embed(title="Enabled Games", color=discord.Color.blurple())
            lines = [f"**{g.name}** (`{g.id}`)" for g in enabled]
            embed.description = "\n".join(lines)
            await interaction.response.send_message(embed=embed)

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)
        await self.tree.sync()
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced slash commands to guild %s", guild.name)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.channel.id != DISCORD_CHANNEL_ID:
            return

        content = message.content
        timestamp = (
            message.created_at.replace(tzinfo=timezone.utc)
            if message.created_at.tzinfo is None
            else message.created_at
        )

        for parser in self.registry.all_parsers():
            if not parser.can_parse(content):
                continue

            result = parser.parse(content, str(message.author.id), timestamp)
            if result is None:
                break

            username = message.author.display_name

            with self.Session() as session:
                game = session.get(Game, result.game_id)
                if game is None or not game.enabled:
                    break

                duplicate = is_duplicate(
                    session, result.user_id, result.game_id, result.date
                )
                if not duplicate:
                    record_submission(session, result, username)
                    session.commit()
                    await message.add_reaction(parser.reaction)
                else:
                    await message.add_reaction("🎉")
            break


def main() -> None:
    bot = ScoreBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
