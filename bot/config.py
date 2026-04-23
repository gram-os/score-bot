import os

from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DISCORD_CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/data/scores.db")
ADMIN_DISCORD_IDS: list[int] = [
    int(uid.strip()) for uid in os.environ.get("ADMIN_DISCORD_IDS", "").split(",") if uid.strip()
]

_DIGEST_TIME = os.environ.get("DIGEST_TIME", "09:00")
_digest_hour, _digest_minute = (int(x) for x in _DIGEST_TIME.split(":"))
DIGEST_HOUR: int = _digest_hour
DIGEST_MINUTE: int = _digest_minute

_REMINDER_TIME = os.environ.get("REMINDER_TIME", "20:00")
_reminder_hour, _reminder_minute = (int(x) for x in _REMINDER_TIME.split(":"))
REMINDER_HOUR: int = _reminder_hour
REMINDER_MINUTE: int = _reminder_minute

PERIOD_CHOICES = [
    app_commands.Choice(name="All Time", value="alltime"),
    app_commands.Choice(name="Season", value="season"),
    app_commands.Choice(name="Daily", value="daily"),
    app_commands.Choice(name="Weekly", value="weekly"),
    app_commands.Choice(name="Monthly", value="monthly"),
]

PERIOD_LABELS = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "alltime": "All Time",
    "season": "Season",
}
