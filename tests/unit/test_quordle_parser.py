from datetime import datetime

from bot.parsers.quordle import QuordleParser

USER_ID = "123456789"
TIMESTAMP = datetime(2024, 1, 15, 12, 0, 0)

QUORDLE_LOW = "Daily Quordle #100\n2️⃣1️⃣\n1️⃣2️⃣"  # total=6, avg=1.5 → min(100, (9-1.5)/5*100)=100
QUORDLE_HIGH = "Daily Quordle #200\n8️⃣9️⃣\n9️⃣9️⃣"  # total=35, avg=8.75, no 🟥 → (9-8.75)/5*100=5.0
QUORDLE_FAIL = "Daily Quordle #300\n🟥2️⃣\n3️⃣4️⃣"  # failed → 0
QUORDLE_MID = "Daily Quordle #400\n4️⃣5️⃣\n6️⃣7️⃣"  # total=22, avg=5.5 → (9-5.5)/5*100=70


class TestQuordleParserCanParse:
    parser = QuordleParser()

    def test_detects_valid_header(self):
        assert self.parser.can_parse("Daily Quordle #123\n4️⃣5️⃣\n6️⃣7️⃣")

    def test_detects_header_without_hash(self):
        assert self.parser.can_parse("Daily Quordle 1553\n8️⃣5️⃣\n4️⃣7️⃣")

    def test_rejects_unrelated(self):
        assert not self.parser.can_parse("unrelated message")

    def test_rejects_wordle(self):
        assert not self.parser.can_parse("Wordle 1,337 3/6")


class TestQuordleParserParse:
    parser = QuordleParser()

    def test_low_attempts_high_score(self):
        # total=6, avg=1.5 → capped at 100
        result = self.parser.parse(QUORDLE_LOW, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 100.0
        assert result.raw_data["attempts"] == [2, 1, 1, 2]
        assert result.raw_data["total_attempts"] == 6
        assert result.raw_data["failed"] is False

    def test_nine_guesses_not_treated_as_failure(self):
        # 9️⃣ = solved on guess 9, not a failure — only 🟥 is a failure
        result = self.parser.parse(QUORDLE_HIGH, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.raw_data["failed"] is False
        assert result.base_score == 5.0

    def test_failed_word_scores_zero(self):
        # 🟥 is the only failure indicator; failed=True forces base_score=0
        result = self.parser.parse(QUORDLE_FAIL, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.raw_data["attempts"][0] == 9
        assert result.raw_data["failed"] is True
        assert result.base_score == 0.0

    def test_mid_attempts_score(self):
        # total=22, avg=5.5 → (9-5.5)/5*100 = 70
        result = self.parser.parse(QUORDLE_MID, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 70.0

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
