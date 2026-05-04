from datetime import datetime

from bot.parsers.mini_crossword import MiniCrosswordParser

USER_ID = "123456789"
TIMESTAMP = datetime(2024, 1, 15, 12, 0, 0)


class TestMiniCrosswordParserCanParse:
    parser = MiniCrosswordParser()

    def test_valid_message(self):
        assert self.parser.can_parse("I solved the Mini in 1:23!")

    def test_valid_without_exclamation(self):
        assert self.parser.can_parse("I solved the Mini in 0:30")

    def test_rejects_wordle(self):
        assert not self.parser.can_parse("Wordle 1,337 3/6")

    def test_rejects_unrelated(self):
        assert not self.parser.can_parse("I solved the crossword")


class TestMiniCrosswordParserParse:
    parser = MiniCrosswordParser()

    def test_fast_time(self):
        # 0:30 → total_seconds=30 → base_score=70
        result = self.parser.parse("I solved the Mini in 0:30!", USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 70.0
        assert result.raw_data["minutes"] == 0
        assert result.raw_data["seconds"] == 30
        assert result.raw_data["total_seconds"] == 30

    def test_slow_time_clamped_to_zero(self):
        # 1:45 → total_seconds=105 → max(0, 100-105)=0
        result = self.parser.parse("I solved the Mini in 1:45!", USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 0.0
        assert result.raw_data["total_seconds"] == 105

    def test_exactly_100_seconds(self):
        # 1:40 → total_seconds=100 → base_score=0
        result = self.parser.parse("I solved the Mini in 1:40!", USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 0.0

    def test_game_id(self):
        result = self.parser.parse("I solved the Mini in 1:00!", USER_ID, TIMESTAMP)
        assert result.game_id == "mini_crossword"

    def test_date_from_timestamp(self):
        result = self.parser.parse("I solved the Mini in 1:00!", USER_ID, TIMESTAMP)
        assert result.date == TIMESTAMP.date()

    def test_returns_none_for_unrecognised(self):
        assert self.parser.parse("unrelated message", USER_ID, TIMESTAMP) is None

    def test_returns_none_for_seconds_at_60(self):
        assert self.parser.parse("I solved the Mini in 1:60!", USER_ID, TIMESTAMP) is None

    def test_returns_none_for_negative_minutes(self):
        assert self.parser.parse("I solved the Mini in -1:30!", USER_ID, TIMESTAMP) is None
