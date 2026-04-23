from datetime import datetime

from bot.parsers.quordle import QuordleParser

USER_ID = "123456789"
TIMESTAMP = datetime(2024, 1, 15, 12, 0, 0)

QUORDLE_LOW = "Daily Quordle #100\n2️⃣1️⃣\n1️⃣2️⃣"  # total=6 → score=80
QUORDLE_HIGH = "Daily Quordle #200\n8️⃣9️⃣\n9️⃣9️⃣"  # total=35 → clamped to 0
QUORDLE_FAIL = "Daily Quordle #300\n🟥2️⃣\n3️⃣4️⃣"  # 9+2+3+4=18 → score=0 (clamped); failed=True
QUORDLE_MID = "Daily Quordle #400\n4️⃣5️⃣\n6️⃣7️⃣"  # total=22 → max(0,100-180)=0


class TestQuordleParserCanParse:
    parser = QuordleParser()

    def test_detects_valid_header(self):
        assert self.parser.can_parse("Daily Quordle #123\n4️⃣5️⃣\n6️⃣7️⃣")

    def test_rejects_unrelated(self):
        assert not self.parser.can_parse("unrelated message")

    def test_rejects_wordle(self):
        assert not self.parser.can_parse("Wordle 1,337 3/6")


class TestQuordleParserParse:
    parser = QuordleParser()

    def test_low_attempts_high_score(self):
        # total=6 → max(0, 100 - (6-4)*10) = 80
        result = self.parser.parse(QUORDLE_LOW, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 80.0
        assert result.raw_data["attempts"] == [2, 1, 1, 2]
        assert result.raw_data["total_attempts"] == 6
        assert result.raw_data["failed"] is False

    def test_high_attempts_clamped_to_zero(self):
        # total=35 → clamped to 0
        result = self.parser.parse(QUORDLE_HIGH, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 0.0

    def test_failed_word_counts_as_nine(self):
        # 🟥 → 9; total=9+2+3+4=18 → max(0,100-140)=0; failed=True
        result = self.parser.parse(QUORDLE_FAIL, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.raw_data["attempts"][0] == 9
        assert result.raw_data["failed"] is True
        assert result.base_score == 0.0

    def test_puzzle_number_extracted(self):
        result = self.parser.parse(QUORDLE_MID, USER_ID, TIMESTAMP)
        assert result.raw_data["puzzle_number"] == 400

    def test_game_id(self):
        result = self.parser.parse(QUORDLE_LOW, USER_ID, TIMESTAMP)
        assert result.game_id == "quordle"

    def test_date_from_timestamp(self):
        result = self.parser.parse(QUORDLE_LOW, USER_ID, TIMESTAMP)
        assert result.date == TIMESTAMP.date()

    def test_returns_none_for_unrecognised(self):
        assert self.parser.parse("unrelated message", USER_ID, TIMESTAMP) is None

    def test_returns_none_for_wrong_emoji_count(self):
        assert self.parser.parse("Daily Quordle #1\n1️⃣2️⃣", USER_ID, TIMESTAMP) is None
