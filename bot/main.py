import datetime
import logging
import os
from datetime import timezone

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from bot.database import (
    Game,
    add_suggestion,
    create_daily_poll,
    find_similar_name,
    get_engine,
    get_latest_unnotified_poll,
    get_leaderboard,
    get_unpolled_suggestions,
    is_duplicate,
    mark_poll_notified,
    record_submission,
)
from bot.parsers.registry import ParserRegistry

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DISCORD_CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/data/scores.db")
ADMIN_DISCORD_IDS: list[int] = [
    int(uid.strip())
    for uid in os.environ.get("ADMIN_DISCORD_IDS", "").split(",")
    if uid.strip()
]
_POLL_HOUR = int(os.environ.get("POLL_HOUR", "9"))
_POLL_TIME = datetime.time(hour=_POLL_HOUR, tzinfo=datetime.timezone.utc)

GAME_CHOICES = [
    app_commands.Choice(name="All", value="all"),
    app_commands.Choice(name="Wordle", value="wordle"),
    app_commands.Choice(name="Glyph", value="glyph"),
    app_commands.Choice(name="Enclose Horse", value="enclose_horse"),
    app_commands.Choice(name="Mini Crossword", value="mini_crossword"),
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

        @self.tree.command(
            name="suggest", description="Suggest a game to be added to the bot"
        )
        @app_commands.describe(
            game_name="Name of the game you want to suggest",
            description="Why should we add this game? (optional)",
        )
        async def suggest(
            interaction: discord.Interaction,
            game_name: str,
            description: str = None,
        ) -> None:
            with self.Session() as session:
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

            await interaction.response.send_message(
                f"✅ **{game_name}** has been added to the suggestion list and will "
                "appear in tomorrow's poll!",
                ephemeral=True,
            )

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)
        await self.tree.sync()
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced slash commands to guild %s", guild.name)
        if not self.daily_suggestion_poll.is_running():
            self.daily_suggestion_poll.start()

    @tasks.loop(time=_POLL_TIME)
    async def daily_suggestion_poll(self) -> None:
        channel = self.get_channel(DISCORD_CHANNEL_ID)
        if channel is None:
            log.warning("Poll task: channel %s not found", DISCORD_CHANNEL_ID)
            return

        # --- Resolve previous poll ---
        with self.Session() as session:
            prev = get_latest_unnotified_poll(session)
            if prev:
                resolved = False
                try:
                    msg = await channel.fetch_message(int(prev.message_id))
                    if msg.poll and msg.poll.is_finalized:
                        await self._resolve_poll(channel, msg.poll, prev)
                        resolved = True
                except discord.NotFound:
                    log.warning(
                        "Poll message %s not found; skipping resolution",
                        prev.message_id,
                    )
                    resolved = True

                if resolved:
                    mark_poll_notified(session, prev.id)
                    session.commit()

        # --- Create new poll from unpolled suggestions ---
        with self.Session() as session:
            suggestions = get_unpolled_suggestions(session)
            if not suggestions:
                return

            is_yes_no = len(suggestions) == 1
            if is_yes_no:
                game = suggestions[0].game_name
                poll = discord.Poll(
                    question=f"Should we add {game} to the bot?",
                    duration=datetime.timedelta(hours=23),
                )
                poll.add_answer(text="Yes", emoji="✅")
                poll.add_answer(text="No", emoji="❌")
            else:
                poll = discord.Poll(
                    question="Which game should we add to the bot next?",
                    duration=datetime.timedelta(hours=23),
                )
                for s in suggestions:
                    poll.add_answer(text=s.game_name)

            msg = await channel.send(poll=poll)
            create_daily_poll(
                session,
                message_id=str(msg.id),
                is_yes_no=is_yes_no,
                suggestion_ids=[s.id for s in suggestions],
            )
            session.commit()
            log.info("Posted suggestion poll with %d option(s)", len(suggestions))

    async def _resolve_poll(
        self,
        channel: discord.TextChannel,
        poll: discord.Poll,
        poll_record,
    ) -> None:
        suggestions = poll_record.suggestions
        total_votes = sum(a.vote_count for a in poll.answers)

        if total_votes == 0:
            if poll_record.is_yes_no:
                s = suggestions[0]
                await channel.send(
                    f"🗳️ The vote for **{s.game_name}** ended with no participation. "
                    f"<@{s.user_id}>"
                )
            return

        if poll_record.is_yes_no:
            s = suggestions[0]
            yes = next((a for a in poll.answers if a.text == "Yes"), None)
            no = next((a for a in poll.answers if a.text == "No"), None)
            yes_votes = yes.vote_count if yes else 0
            no_votes = no.vote_count if no else 0

            if yes_votes > no_votes:
                await channel.send(
                    f"🎉 **{s.game_name}** passed the vote! "
                    f"<@{s.user_id}> your suggestion is on its way — admins have been notified."
                )
                await self._notify_admins(s.game_name)
            else:
                await channel.send(
                    f"❌ **{s.game_name}** didn't pass the vote this time. "
                    f"Better luck next time, <@{s.user_id}>!"
                )
        else:
            by_name = {s.game_name: s for s in suggestions}
            answers_sorted = sorted(
                poll.answers, key=lambda a: a.vote_count, reverse=True
            )
            winner_answer = answers_sorted[0]

            winner = by_name.get(winner_answer.text)
            await channel.send(
                f"🎉 **{winner_answer.text}** won the suggestion vote! "
                + (
                    f"<@{winner.user_id}> your suggestion is on its way — "
                    if winner
                    else ""
                )
                + "admins have been notified."
            )
            await self._notify_admins(winner_answer.text)

    async def _notify_admins(self, game_name: str) -> None:
        for admin_id in ADMIN_DISCORD_IDS:
            try:
                user = await self.fetch_user(admin_id)
                await user.send(
                    f"🎮 The community voted to add **{game_name}** to the bot! "
                    "Please look into implementing it."
                )
            except Exception:
                log.warning("Could not DM admin %s", admin_id)

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
                    await message.add_reaction("⚠️")
            break


def main() -> None:
    bot = ScoreBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
