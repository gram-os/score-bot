import logging

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord import app_commands
from discord.ext import tasks
from sqlalchemy.orm import sessionmaker

from bot.commands import achievements, best, games, help, leaderboard, mystats, profile, remind, suggest, vs
from bot.config import (
    ADMIN_DISCORD_IDS,
    DATABASE_PATH,
    DIGEST_HOUR,
    DIGEST_MINUTE,
    DISCORD_CHANNEL_ID,
    DISCORD_TOKEN,
    REMINDER_HOUR,
    REMINDER_MINUTE,
)
from bot.database import get_engine
from bot.log_handler import setup_db_logging
from bot.parsers.registry import ParserRegistry
from bot.tasks import digests, message_handler, polls, reminders

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

_COMMAND_MODULES = [leaderboard, games, suggest, vs, best, mystats, profile, achievements, remind, help]


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

        if not self._scheduler.running:
            self._scheduler.add_job(
                self._send_daily_digest,
                CronTrigger(hour=DIGEST_HOUR, minute=DIGEST_MINUTE),
                replace_existing=True,
            )
            self._scheduler.add_job(
                self._send_weekly_digest,
                CronTrigger(day_of_week="mon", hour=DIGEST_HOUR, minute=DIGEST_MINUTE),
                replace_existing=True,
            )
            self._scheduler.add_job(
                self._send_streak_reminders,
                CronTrigger(hour=REMINDER_HOUR, minute=REMINDER_MINUTE),
                replace_existing=True,
            )
            self._scheduler.start()
            log.info("Digest scheduler started (fires at %02d:%02d local)", DIGEST_HOUR, DIGEST_MINUTE)
            log.info("Reminder scheduler started (fires at %02d:%02d local)", REMINDER_HOUR, REMINDER_MINUTE)

    async def close(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        await super().close()

    @tasks.loop(hours=4)
    async def daily_suggestion_poll(self) -> None:
        channel = self.get_channel(DISCORD_CHANNEL_ID)
        await polls.run_poll_cycle(self, channel, self.Session, ADMIN_DISCORD_IDS)

    async def _send_daily_digest(self) -> None:
        channel = self.get_channel(DISCORD_CHANNEL_ID)
        await digests.send_daily_digest(channel, self.Session)

    async def _send_weekly_digest(self) -> None:
        channel = self.get_channel(DISCORD_CHANNEL_ID)
        await digests.send_weekly_digest(self, channel, self.Session)

    async def _send_streak_reminders(self) -> None:
        await reminders.send_streak_reminders(self, self.Session, DISCORD_CHANNEL_ID)

    async def on_message(self, message: discord.Message) -> None:
        await message_handler.handle_message(self, message, self.registry, self.Session, DISCORD_CHANNEL_ID)


def main() -> None:
    bot = ScoreBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
