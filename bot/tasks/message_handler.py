import logging
from datetime import timezone

import discord
from sqlalchemy import func, select

from bot.achievements import ACHIEVEMENTS, check_and_award_achievements
from bot.database import Game, is_duplicate, record_submission, update_streak_on_submission

log = logging.getLogger(__name__)


async def handle_message(
    client: discord.Client,
    message: discord.Message,
    registry,
    Session,
    channel_id: int,
) -> None:
    if message.author.bot:
        return
    if message.channel.id != channel_id:
        return

    content = message.content
    timestamp = (
        message.created_at.replace(tzinfo=timezone.utc) if message.created_at.tzinfo is None else message.created_at
    )

    for parser in registry.all_parsers():
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

        with Session() as session:
            game = session.get(Game, result.game_id)
            if game is None or not game.enabled:
                break

            duplicate = is_duplicate(session, result.user_id, result.game_id, result.date)
            if not duplicate:
                game_name = game.name
                submission = record_submission(session, result, username)
                if submission is None:
                    await message.add_reaction("⚠️")
                    break

                user_streak, freeze_used = update_streak_on_submission(
                    session, result.user_id, result.game_id, result.date
                )
                enabled_count = (
                    session.scalar(select(func.count()).select_from(Game).where(Game.enabled.is_(True))) or 0
                )
                new_achievements = check_and_award_achievements(
                    session,
                    result.user_id,
                    result.game_id,
                    result.date,
                    user_streak,
                    submission,
                    freeze_used,
                    enabled_count,
                )
                session.commit()

                streak = user_streak.current_streak
                log.info(
                    "Recorded %s for %s: base=%s streak=%s",
                    result.game_id,
                    username,
                    result.base_score,
                    streak,
                )
                await message.add_reaction(parser.reaction)

                if freeze_used:
                    await _dm_user(
                        client,
                        result.user_id,
                        f"🧊 A streak freeze was used to preserve your "
                        f"**{streak}-day streak** in **{game_name}**! "
                        f"You have {user_streak.freeze_count} freeze"
                        f"{'s' if user_streak.freeze_count != 1 else ''} remaining.",
                    )

                for slug in new_achievements:
                    ach = ACHIEVEMENTS.get(slug)
                    if ach:
                        await _dm_user(
                            client,
                            result.user_id,
                            f"🏆 Achievement unlocked: **{ach.icon} {ach.name}**\n_{ach.description}_",
                        )

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


async def _dm_user(client: discord.Client, user_id: str, message: str) -> None:
    try:
        user = await client.fetch_user(int(user_id))
        await user.send(message)
    except Exception:
        log.warning("Could not DM user %s", user_id)
