import datetime
import logging
import os
from datetime import timezone

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
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
    get_all_streaks,
    get_engine,
    get_head_to_head,
    get_latest_unnotified_poll,
    get_leaderboard,
    get_opted_in_preferences,
    get_personal_bests,
    get_preference,
    get_streak,
    get_unpolled_suggestions,
    get_yesterday_digest,
    is_duplicate,
    mark_poll_notified,
    record_submission,
    set_preference,
)
from bot.log_handler import setup_db_logging
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

_DIGEST_TIME = os.environ.get("DIGEST_TIME", "09:00")
_digest_hour, _digest_minute = (int(x) for x in _DIGEST_TIME.split(":"))

_REMINDER_TIME = os.environ.get("REMINDER_TIME", "20:00")
_reminder_hour, _reminder_minute = (int(x) for x in _REMINDER_TIME.split(":"))

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
        setup_db_logging(engine)

        self._scheduler = AsyncIOScheduler()
        self._register_commands()

    def _register_commands(self) -> None:
        @self.tree.command(name="leaderboard", description="Show the leaderboard")
        @app_commands.describe(
            game="Which game to show (default: all)",
            period="Time period (default: alltime)",
        )
        @app_commands.choices(period=PERIOD_CHOICES)
        async def leaderboard(
            interaction: discord.Interaction,
            game: str = None,
            period: app_commands.Choice[str] = None,
        ) -> None:
            game_id = game if game else "all"
            period_value = period.value if period else "alltime"

            with self.Session() as session:
                rows = get_leaderboard(
                    session,
                    period=period_value,
                    game_id=None if game_id == "all" else game_id,
                )
                if game_id == "all":
                    enabled_games = (
                        session.query(Game).filter(Game.enabled.is_(True)).all()
                    )
                    streak_map: dict[str, int] = {}
                    for g in enabled_games:
                        for uid, _, streak in get_all_streaks(session, g.id):
                            if streak > streak_map.get(uid, 0):
                                streak_map[uid] = streak
                else:
                    streak_map = {
                        uid: streak
                        for uid, _, streak in get_all_streaks(session, game_id)
                    }

            if game_id == "all":
                game_label = "All Games"
            else:
                parser = self.registry.get_parser(game_id)
                game_label = parser.game_name if parser else game_id
            period_label = PERIOD_LABELS[period_value]
            title = f"Leaderboard — {game_label} ({period_label})"

            embed = discord.Embed(title=title, color=discord.Color.gold())

            if not rows:
                embed.description = "No submissions yet."
            else:
                lines = []
                for row in rows[:15]:
                    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(row.rank, f"`#{row.rank}`")
                    streak = streak_map.get(row.user_id, 0)
                    streak_str = f" 🔥{streak}" if streak >= 1 else ""
                    lines.append(
                        f"{medal} **{row.username}**{streak_str} — {row.total_score:.0f} pts"
                        f" ({row.submission_count} sub{'s' if row.submission_count != 1 else ''})"
                    )
                embed.description = "\n".join(lines)

            log.info(
                "/leaderboard by %s (game=%s, period=%s)",
                interaction.user.display_name,
                game_id,
                period_value,
            )
            await interaction.response.send_message(embed=embed)

        @leaderboard.autocomplete("game")
        async def leaderboard_game_autocomplete(
            interaction: discord.Interaction,
            current: str,
        ) -> list[app_commands.Choice[str]]:
            choices = [app_commands.Choice(name="All Games", value="all")] + [
                app_commands.Choice(name=p.game_name, value=p.game_id)
                for p in self.registry.all_parsers()
            ]
            if current:
                choices = [
                    c
                    for c in choices
                    if current.lower() in c.name.lower()
                    or current.lower() in c.value.lower()
                ]
            return choices[:25]

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
                log.info("/suggest by %s: %s", interaction.user.display_name, game_name)

            await interaction.response.send_message(
                f"✅ **{game_name}** has been added to the suggestion list and will "
                "appear in tomorrow's poll!",
                ephemeral=True,
            )

        @self.tree.command(
            name="vs", description="Head-to-head comparison against another player"
        )
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
                await interaction.response.send_message(
                    "You can't challenge yourself!", ephemeral=True
                )
                return

            game_id = game if game else None
            if game_id:
                parser = self.registry.get_parser(game_id)
                game_label = parser.game_name if parser else game_id
            else:
                game_label = "All Games"

            with self.Session() as session:
                result = get_head_to_head(session, caller_id, opponent_id, game_id)

            if result is None:
                await interaction.response.send_message(
                    f"No overlapping submissions found between you and "
                    f"**{opponent.display_name}**"
                    + (f" in **{game_label}**" if game else "")
                    + ". Play some games together first!",
                )
                return

            overlapping = result.overlapping_days
            caller_win_rate = (
                result.caller_wins / overlapping * 100 if overlapping else 0
            )
            opponent_win_rate = (
                result.opponent_wins / overlapping * 100 if overlapping else 0
            )

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
                value=(
                    f"{result.caller_total_score:.0f}\n"
                    f"{result.opponent_total_score:.0f}"
                ),
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
            return [
                app_commands.Choice(name=p.game_name, value=p.game_id)
                for p in self.registry.all_parsers()
                if not current
                or current.lower() in p.game_name.lower()
                or current.lower() in p.game_id.lower()
            ][:25]

        @self.tree.command(name="best", description="Show personal bests for a game")
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

            parser = self.registry.get_parser(game)
            game_name = parser.game_name if parser else game

            with self.Session() as session:
                bests = get_personal_bests(session, target_id, game)
                streak = get_streak(session, target_id, game) if bests else 0

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
            embed.add_field(
                name="Average Score", value=f"{bests.avg_score:.1f} pts", inline=True
            )
            embed.add_field(
                name="Total Submissions", value=str(bests.count), inline=True
            )
            if streak >= 1:
                embed.add_field(
                    name="Current Streak", value=f"🔥 {streak} days", inline=True
                )

            await interaction.response.send_message(embed=embed)

        @best.autocomplete("game")
        async def best_game_autocomplete(
            interaction: discord.Interaction,
            current: str,
        ) -> list[app_commands.Choice[str]]:
            return [
                app_commands.Choice(name=p.game_name, value=p.game_id)
                for p in self.registry.all_parsers()
                if current.lower() in p.game_name.lower()
                or current.lower() in p.game_id.lower()
            ]

        @self.tree.command(
            name="remind",
            description="Toggle streak reminders for yourself",
        )
        @app_commands.describe(
            threshold="Minimum streak length to trigger a reminder (0 = opt out, default 3)"
        )
        async def remind(
            interaction: discord.Interaction,
            threshold: int = 3,
        ) -> None:
            user_id = str(interaction.user.id)
            with self.Session() as session:
                pref = get_preference(session, user_id)
                currently_opted_in = pref is not None and pref.remind_streak_days > 0

                if threshold == 0 or currently_opted_in:
                    set_preference(session, user_id, remind_streak_days=0)
                    session.commit()
                    log.info(
                        "/remind: %s opted out of streak reminders",
                        interaction.user.display_name,
                    )
                    await interaction.response.send_message(
                        "Streak reminders **disabled**. You won't receive reminder DMs.",
                        ephemeral=True,
                    )
                else:
                    set_preference(session, user_id, remind_streak_days=threshold)
                    session.commit()
                    log.info(
                        "/remind: %s opted in (threshold=%d)",
                        interaction.user.display_name,
                        threshold,
                    )
                    await interaction.response.send_message(
                        f"Streak reminders **enabled** — you'll be reminded when your streak reaches "
                        f"**{threshold}** days.",
                        ephemeral=True,
                    )

        @self.tree.command(name="help", description="How to use this bot")
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

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced slash commands to guild %s", guild.name)
        # Clear global commands after guild sync so duplicates stop appearing
        self.tree.clear_commands(guild=None)
        await self.tree.sync()
        if not self.daily_suggestion_poll.is_running():
            self.daily_suggestion_poll.start()
        if not self._scheduler.running:
            self._scheduler.add_job(
                self._send_daily_digest,
                CronTrigger(hour=_digest_hour, minute=_digest_minute),
                replace_existing=True,
            )
            self._scheduler.add_job(
                self._send_streak_reminders,
                CronTrigger(hour=_reminder_hour, minute=_reminder_minute),
                replace_existing=True,
            )
            self._scheduler.start()
            log.info(
                "Digest scheduler started (fires at %02d:%02d local)",
                _digest_hour,
                _digest_minute,
            )
            log.info(
                "Reminder scheduler started (fires at %02d:%02d local)",
                _reminder_hour,
                _reminder_minute,
            )

    async def close(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        await super().close()

    @tasks.loop(hours=4)
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
                    duration=datetime.timedelta(hours=4),
                )
                poll.add_answer(text="Yes", emoji="✅")
                poll.add_answer(text="No", emoji="❌")
            else:
                poll = discord.Poll(
                    question="Which game should we add to the bot next?",
                    duration=datetime.timedelta(hours=4),
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

    async def _send_daily_digest(self) -> None:
        channel = self.get_channel(DISCORD_CHANNEL_ID)
        if channel is None:
            log.warning("Digest: channel %s not found", DISCORD_CHANNEL_ID)
            return

        with self.Session() as session:
            digest_data = get_yesterday_digest(session)

        if not any(d.participant_count > 0 for d in digest_data):
            return

        yesterday = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        ).date()
        embed = discord.Embed(
            title=f"Daily Digest — {yesterday}",
            color=discord.Color.blurple(),
        )

        lines = []
        for d in digest_data:
            if d.participant_count == 0:
                lines.append(f"**{d.game_name}** — no activity")
            else:
                players = f"{d.participant_count} player{'s' if d.participant_count != 1 else ''}"
                streak_str = (
                    f" | 🔥 Top streak: {d.top_streak}" if d.top_streak >= 1 else ""
                )
                lines.append(
                    f"**{d.game_name}** — 🏆 {d.winner_username} ({d.winner_score:.0f} pts)"
                    f" | {players}{streak_str}"
                )
        embed.description = "\n".join(lines)
        await channel.send(embed=embed)
        log.info("Daily digest sent for %s", yesterday)

    async def _send_streak_reminders(self) -> None:
        today = datetime.datetime.now(datetime.timezone.utc).date()

        with self.Session() as session:
            prefs = get_opted_in_preferences(session)
            enabled_games = (
                session.execute(select(Game).where(Game.enabled.is_(True)))
                .scalars()
                .all()
            )

            reminders: dict[str, list[str]] = {}
            for pref in prefs:
                qualifying_games = []
                for game in enabled_games:
                    streak = get_streak(session, pref.user_id, game.id)
                    if streak >= pref.remind_streak_days and not is_duplicate(
                        session, pref.user_id, game.id, today
                    ):
                        qualifying_games.append(game.name)
                if qualifying_games:
                    reminders[pref.user_id] = qualifying_games

        sent = 0
        for user_id, game_names in reminders.items():
            try:
                user = await self.fetch_user(int(user_id))
                games_list = ", ".join(f"**{g}**" for g in game_names)
                await user.send(
                    f"Don't break your streak! You haven't submitted today for: {games_list}"
                )
                sent += 1
            except Exception:
                log.warning("Could not DM reminder to user %s", user_id)
        if sent:
            log.info("Sent streak reminders to %d user(s)", sent)

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
                log.warning(
                    "Parser %s matched but returned None for %s",
                    parser.game_id,
                    message.author.display_name,
                )
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
                    game_name = game.name
                    record_submission(session, result, username)
                    session.commit()
                    streak = get_streak(session, result.user_id, result.game_id)
                    log.info(
                        "Recorded %s for %s: base=%s total=%s",
                        result.game_id,
                        username,
                        result.base_score,
                        result.base_score,
                    )
                    await message.add_reaction(parser.reaction)
                    if streak >= 3:
                        await message.channel.send(
                            f"🔥 {username} is on a **{streak}-day streak** in {game_name}!",
                            reference=message,
                        )
                else:
                    log.warning(
                        "Duplicate %s submission from %s on %s",
                        result.game_id,
                        username,
                        result.date,
                    )
                    await message.add_reaction("⚠️")
            break


def main() -> None:
    bot = ScoreBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
