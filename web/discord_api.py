import urllib.parse
from datetime import date, datetime, timezone

import httpx

DISCORD_EPOCH_MS = 1420070400000


async def add_reaction(token: str, channel_id: int, message_id: str, emoji: str) -> None:
    encoded = urllib.parse.quote(emoji)
    headers = {"Authorization": f"Bot {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/reactions/{encoded}/@me",
            headers=headers,
        )
        resp.raise_for_status()


def date_to_snowflake(d: date, end_of_day: bool = False) -> int:
    if end_of_day:
        dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
    else:
        dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    ms = int(dt.timestamp() * 1000)
    return (ms - DISCORD_EPOCH_MS) << 22


def snowflake_to_datetime(snowflake: int) -> datetime:
    ms = (int(snowflake) >> 22) + DISCORD_EPOCH_MS
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


async def fetch_message_by_id(token: str, channel_id: int, message_id: str) -> dict:
    """Fetch a single Discord message by its ID."""
    headers = {"Authorization": f"Bot {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_channel_messages(
    token: str,
    channel_id: int,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Fetch all messages in channel between start_date and end_date inclusive, oldest first."""
    headers = {"Authorization": f"Bot {token}"}
    before_snowflake = date_to_snowflake(end_date, end_of_day=True)
    start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)

    messages: list[dict] = []
    async with httpx.AsyncClient() as client:
        while True:
            resp = await client.get(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers=headers,
                params={"limit": 100, "before": str(before_snowflake)},
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break

            for msg in batch:
                msg_dt = datetime.fromisoformat(msg["timestamp"])
                if msg_dt.tzinfo is None:
                    msg_dt = msg_dt.replace(tzinfo=timezone.utc)
                if msg_dt < start_dt:
                    return sorted(messages, key=lambda m: m["id"])
                messages.append(msg)

            before_snowflake = int(batch[-1]["id"])

    return sorted(messages, key=lambda m: m["id"])
