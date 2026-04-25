import asyncio
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bot.tasks.polls import _FINALIZATION_GRACE, run_poll_cycle


def _make_poll_record(message_id: str, expires_at: datetime.datetime | None, is_yes_no: bool = True):
    suggestion = SimpleNamespace(game_name="TestGame", user_id="123")
    return SimpleNamespace(
        id=1,
        message_id=message_id,
        expires_at=expires_at,
        is_yes_no=is_yes_no,
        suggestions=[suggestion],
    )


def _make_discord_poll(is_finalized: bool, yes_votes: int = 0, no_votes: int = 0):
    yes = SimpleNamespace(text="Yes", vote_count=yes_votes)
    no = SimpleNamespace(text="No", vote_count=no_votes)
    return SimpleNamespace(is_finalized=is_finalized, answers=[yes, no])


def _make_session(inner_session=None):
    session_ctx = MagicMock()
    session_ctx.__enter__ = MagicMock(return_value=inner_session or MagicMock())
    session_ctx.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=session_ctx)


def test_resolve_skipped_within_grace_period():
    now = datetime.datetime.utcnow()
    record = _make_poll_record("999", expires_at=now + datetime.timedelta(minutes=2))
    channel = AsyncMock()

    with patch("bot.tasks.polls.get_latest_unnotified_poll", return_value=record):
        with patch("bot.tasks.polls.get_unpolled_suggestions", return_value=[]):
            asyncio.run(run_poll_cycle(MagicMock(), channel, _make_session(), []))

    channel.fetch_message.assert_not_called()


def test_resolve_skipped_within_grace_period_after_expiry():
    now = datetime.datetime.utcnow()
    # Expired 2 minutes ago — inside the 5-minute grace window
    record = _make_poll_record("999", expires_at=now - datetime.timedelta(minutes=2))
    channel = AsyncMock()

    with patch("bot.tasks.polls.get_latest_unnotified_poll", return_value=record):
        with patch("bot.tasks.polls.get_unpolled_suggestions", return_value=[]):
            asyncio.run(run_poll_cycle(MagicMock(), channel, _make_session(), []))

    channel.fetch_message.assert_not_called()


def test_resolve_proceeds_after_grace_period():
    now = datetime.datetime.utcnow()
    # Expired 10 minutes ago — well past the grace window
    record = _make_poll_record("999", expires_at=now - _FINALIZATION_GRACE - datetime.timedelta(minutes=5))

    discord_poll = _make_discord_poll(is_finalized=True, yes_votes=3, no_votes=1)
    channel = AsyncMock()
    channel.fetch_message = AsyncMock(return_value=SimpleNamespace(poll=discord_poll))

    inner_session = MagicMock()

    with patch("bot.tasks.polls.get_latest_unnotified_poll", return_value=record):
        with patch("bot.tasks.polls.get_unpolled_suggestions", return_value=[]):
            with patch("bot.tasks.polls.mark_poll_notified") as mock_notify:
                asyncio.run(run_poll_cycle(MagicMock(), channel, _make_session(inner_session), []))

    channel.fetch_message.assert_called_once_with(999)
    mock_notify.assert_called_once_with(inner_session, record.id)


def test_resolve_proceeds_with_no_expires_at():
    record = _make_poll_record("999", expires_at=None)

    discord_poll = _make_discord_poll(is_finalized=True, yes_votes=2, no_votes=0)
    channel = AsyncMock()
    channel.fetch_message = AsyncMock(return_value=SimpleNamespace(poll=discord_poll))

    inner_session = MagicMock()

    with patch("bot.tasks.polls.get_latest_unnotified_poll", return_value=record):
        with patch("bot.tasks.polls.get_unpolled_suggestions", return_value=[]):
            with patch("bot.tasks.polls.mark_poll_notified") as mock_notify:
                asyncio.run(run_poll_cycle(MagicMock(), channel, _make_session(inner_session), []))

    channel.fetch_message.assert_called_once_with(999)
    mock_notify.assert_called_once_with(inner_session, record.id)
