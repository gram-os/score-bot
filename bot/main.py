import logging

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord import app_commands
from discord.ext import tasks
from sqlalchemy.orm import sessionmaker

from bot.commands import (
    achievements,
    best,
    feedback,
    games,
    halloffame,
    help,
    homunculus,
    leaderboard,
    mystats,
    profile,
    remind,
    seasons,
    suggest,
    submitted,
    vs,
)
from bot.config import (
    ADMIN_DISCORD_IDS,
    DATABASE_PATH,
    DIGEST_HOUR,
    DIGEST_MINUTE,
    DISCORD_CHANNEL_ID,
    DISCORD_TOKEN,
    HOMUNCULUS_AUTHOR_ID,
    HOMUNCULUS_CHANNEL_ID,
    REMINDER_HOUR,
    REMINDER_MINUTE,
)
from bot.database import get_engine
from bot.log_handler import setup_db_logging
from bot.parsers.registry import ParserRegistry
from bot.tasks import digests, message_handler, monthly_wrapped, polls, reminders, startup_backfill
from bot.tasks import homunculus as homunculus_task

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

_COMMAND_MODULES = [
    leaderboard,
    games,
    suggest,
    feedback,
    vs,
    best,
    mystats,
    profile,
    achievements,
    remind,
    help,
    homunculus,
    submitted,
    seasons,
    halloffame,
]


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
        for mod in _COMMAND_MODULES:
            mod.register(self.tree, self.registry, self.Session)

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced slash commands to guild %s", guild.name)
        self.tree.clear_commands(guild=None)
        await self.tree.sync()

        if not self.daily_suggestion_poll.is_running():
            self.daily_suggestion_poll.start()

        if HOMUNCULUS_CHANNEL_ID and not self.homunculus_poll_check.is_running():
            self.homunculus_poll_check.start()

        if not self._scheduler.running:
            self._scheduler.add_job(
                self._send_daily_digest,
                CronTrigger(hour=DIGEST_HOUR, minute=DIGEST_MINUTE, timezone="America/New_York"),
                replace_existing=True,
            )
            self._scheduler.add_job(
                self._send_weekly_digest,
                CronTrigger(
                    day_of_week="mon",
                    hour=DIGEST_HOUR,
                    minute=DIGEST_MINUTE,
                    timezone="America/New_York",
                ),
                replace_existing=True,
            )
            self._scheduler.add_job(
                self._send_streak_reminders,
                CronTrigger(hour=REMINDER_HOUR, minute=REMINDER_MINUTE, timezone="America/New_York"),
                replace_existing=True,
            )
            self._scheduler.add_job(
                self._send_cutoff_reminder,
                CronTrigger(hour=23, minute=0, timezone="America/New_York"),
                replace_existing=True,
            )
            self._scheduler.add_job(
                self._send_season_wrapped,
                CronTrigger(hour=DIGEST_HOUR, minute=DIGEST_MINUTE, timezone="America/New_York"),
                replace_existing=True,
            )
            self._scheduler.start()
            log.info("Digest scheduler started (fires at %02d:%02d local)", DIGEST_HOUR, DIGEST_MINUTE)
            log.info("Reminder scheduler started (fires at %02d:%02d local)", REMINDER_HOUR, REMINDER_MINUTE)

        await startup_backfill.run_startup_backfill(self, self.registry, self.Session, DISCORD_CHANNEL_ID)

    async def close(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        await super().close()

    @tasks.loop(hours=4)
    async def daily_suggestion_poll(self) -> None:
        channel = self.get_channel(DISCORD_CHANNEL_ID)
        await polls.run_poll_cycle(self, channel, self.Session, ADMIN_DISCORD_IDS)

    @tasks.loop(hours=1)
    async def homunculus_poll_check(self) -> None:
        if HOMUNCULUS_CHANNEL_ID and HOMUNCULUS_AUTHOR_ID:
            await homunculus_task.check_homunculus_polls(
                self, HOMUNCULUS_CHANNEL_ID, HOMUNCULUS_AUTHOR_ID, self.Session
            )

    async def _send_daily_digest(self) -> None:
        channel = self.get_channel(DISCORD_CHANNEL_ID)
        await digests.send_daily_digest(channel, self.Session)

    async def _send_weekly_digest(self) -> None:
        channel = self.get_channel(DISCORD_CHANNEL_ID)
        await digests.send_weekly_digest(self, channel, self.Session)

    async def _send_streak_reminders(self) -> None:
        await reminders.send_streak_reminders(self, self.Session, DISCORD_CHANNEL_ID)

    async def _send_cutoff_reminder(self) -> None:
        await reminders.send_cutoff_reminder(self, DISCORD_CHANNEL_ID)

    async def _send_season_wrapped(self) -> None:
        await monthly_wrapped.send_season_wrapped(self, self.Session)

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        command_name = interaction.command and interaction.command.name
        log.exception("Error in command '%s'", command_name, exc_info=error)
        await self._notify_admins_of_error(command_name, interaction.user, error)
        msg = "Something went wrong. Please try again."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    async def _notify_admins_of_error(
        self,
        command_name: str | None,
        triggering_user: discord.User | discord.Member,
        error: Exception,
    ) -> None:
        cause = error.__cause__ or error
        dm = (
            f"**Bot error** in `/{command_name or '?'}`\n"
            f"Triggered by: {triggering_user} (`{triggering_user.id}`)\n"
            f"```{type(cause).__name__}: {cause}```"
        )
        for admin_id in ADMIN_DISCORD_IDS:
            try:
                user = await self.fetch_user(admin_id)
                await user.send(dm)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                log.exception("Failed to DM admin %s", admin_id)

    async def on_message(self, message: discord.Message) -> None:
        await message_handler.handle_message(self, message, self.registry, self.Session, DISCORD_CHANNEL_ID)


def main() -> None:
    bot = ScoreBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
