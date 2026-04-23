from datetime import datetime, timezone

import pytest

from bot.database import Game
from web.backfill import process_messages


def make_message(
    msg_id: str,
    user_id: str,
    username: str,
    content: str,
    timestamp: datetime,
) -> dict:
    return {
        "id": msg_id,
        "content": content,
        "author": {"id": user_id, "username": username, "global_name": username, "bot": False},
        "timestamp": timestamp.isoformat(),
    }


WORDLE_MSG = "Wordle 1,338 3/6\n🟨⬜⬜⬜🟩\n⬜🟨⬜⬜⬜\n🟩🟩🟩🟩🟩"
TS = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def wordle_game(session):
    game = Game(
        id="wordle",
        name="Wordle",
        enabled=True,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(game)
    session.flush()
    return game


class TestProcessMessages:
    def test_records_new_submission(self, session, wordle_game):
        messages = [make_message("1", "user1", "Alice", WORDLE_MSG, TS)]
        result = process_messages(session, messages)

        assert len(result.recorded) == 1
        assert result.recorded[0].username == "Alice"
        assert result.recorded[0].game_name == "Wordle"
        assert len(result.duplicates) == 0
        assert len(result.errors) == 0

    def test_skips_duplicate(self, session, wordle_game):
        messages = [make_message("1", "user1", "Alice", WORDLE_MSG, TS)]
        process_messages(session, messages)
        session.flush()

        result = process_messages(session, messages)
        assert len(result.recorded) == 0
        assert len(result.duplicates) == 1
        assert result.duplicates[0].status == "duplicate"

    def test_skips_bot_messages(self, session, wordle_game):
        msg = make_message("1", "bot1", "SomeBot", WORDLE_MSG, TS)
        msg["author"]["bot"] = True
        result = process_messages(session, [msg])
        assert result.messages_scanned == 1
        assert len(result.recorded) == 0

    def test_skips_unmatched_messages(self, session, wordle_game):
        msg = make_message("1", "user1", "Alice", "just chatting", TS)
        result = process_messages(session, [msg])
        assert len(result.recorded) == 0
        assert len(result.errors) == 0

    def test_multiple_users_same_game(self, session, wordle_game):
        messages = [
            make_message("1", "user1", "Alice", WORDLE_MSG, TS),
            make_message("2", "user2", "Bob", WORDLE_MSG, TS),
        ]
        result = process_messages(session, messages)
        assert len(result.recorded) == 2

    def test_messages_scanned_count(self, session, wordle_game):
        messages = [
            make_message("1", "user1", "Alice", WORDLE_MSG, TS),
            make_message("2", "user2", "Bob", "just chatting", TS),
        ]
        result = process_messages(session, messages)
        assert result.messages_scanned == 2

    def test_skips_disabled_game(self, session):
        game = Game(
            id="wordle",
            name="Wordle",
            enabled=False,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(game)
        session.flush()

        messages = [make_message("1", "user1", "Alice", WORDLE_MSG, TS)]
        result = process_messages(session, messages)
        assert len(result.recorded) == 0
