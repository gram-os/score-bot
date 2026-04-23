import datetime
import logging

import discord

from bot.database import (
    create_daily_poll,
    get_latest_unnotified_poll,
    get_unpolled_suggestions,
    mark_poll_notified,
)

log = logging.getLogger(__name__)


async def run_poll_cycle(
    client: discord.Client,
    channel: discord.TextChannel | None,
    Session,
    admin_ids: list[int],
) -> None:
    if channel is None:
        log.warning("Poll task: channel not found")
        return

    await _resolve_pending_poll(client, channel, Session, admin_ids)
    await _post_new_poll(channel, Session)


async def _resolve_pending_poll(
    client: discord.Client,
    channel: discord.TextChannel,
    Session,
    admin_ids: list[int],
) -> None:
    with Session() as session:
        prev = get_latest_unnotified_poll(session)
        if not prev:
            return

        resolved = False
        try:
            msg = await channel.fetch_message(int(prev.message_id))
            if msg.poll and msg.poll.is_finalized:
                await _resolve_poll(client, channel, msg.poll, prev, admin_ids)
                resolved = True
        except discord.NotFound:
            log.warning("Poll message %s not found; skipping resolution", prev.message_id)
            resolved = True

        if resolved:
            mark_poll_notified(session, prev.id)
            session.commit()


async def _post_new_poll(channel: discord.TextChannel, Session) -> None:
    with Session() as session:
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
    client: discord.Client,
    channel: discord.TextChannel,
    poll: discord.Poll,
    poll_record,
    admin_ids: list[int],
) -> None:
    suggestions = poll_record.suggestions
    total_votes = sum(a.vote_count for a in poll.answers)

    if total_votes == 0:
        if poll_record.is_yes_no:
            s = suggestions[0]
            await channel.send(f"🗳️ The vote for **{s.game_name}** ended with no participation. <@{s.user_id}>")
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
            await _notify_admins(client, s.game_name, admin_ids)
        else:
            await channel.send(
                f"❌ **{s.game_name}** didn't pass the vote this time. Better luck next time, <@{s.user_id}>!"
            )
    else:
        by_name = {s.game_name: s for s in suggestions}
        answers_sorted = sorted(poll.answers, key=lambda a: a.vote_count, reverse=True)
        winner_answer = answers_sorted[0]
        winner = by_name.get(winner_answer.text)

        await channel.send(
            f"🎉 **{winner_answer.text}** won the suggestion vote! "
            + (f"<@{winner.user_id}> your suggestion is on its way — " if winner else "")
            + "admins have been notified."
        )
        await _notify_admins(client, winner_answer.text, admin_ids)


async def _notify_admins(client: discord.Client, game_name: str, admin_ids: list[int]) -> None:
    for admin_id in admin_ids:
        try:
            user = await client.fetch_user(admin_id)
            await user.send(
                f"🎮 The community voted to add **{game_name}** to the bot! Please look into implementing it."
            )
        except Exception:
            log.warning("Could not DM admin %s", admin_id)
