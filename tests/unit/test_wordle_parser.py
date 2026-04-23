from datetime import datetime

from bot.parsers.wordle import WordleParser

USER_ID = "123456789"
TIMESTAMP = datetime(2024, 1, 15, 12, 0, 0)


class TestWordleParserCanParse:
    parser = WordleParser()

    def test_standard_result(self):
        assert self.parser.can_parse("Wordle 1,337 3/6\n🟨⬜⬜⬜🟩")

    def test_no_comma_in_number(self):
        assert self.parser.can_parse("Wordle 1338 1/6\n🟩🟩🟩🟩🟩")

    def test_failed_result(self):
        assert self.parser.can_parse("Wordle 1339 X/6")

    def test_hard_mode(self):
        assert self.parser.can_parse("Wordle 1340 6/6*")

    def test_rejects_glyph_message(self):
        assert not self.parser.can_parse("Glyph 2024-01-15 | 1/4")

    def test_rejects_plain_text(self):
        assert not self.parser.can_parse("hello world")


class TestWordleParserParse:
    parser = WordleParser()

    def test_score_for_one_attempt(self):
        result = self.parser.parse("Wordle 1338 1/6", USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 100.0
        assert result.raw_data["attempts"] == 1
        assert result.raw_data["hard_mode"] is False

    def test_score_for_three_attempts(self):
        result = self.parser.parse("Wordle 1,337 3/6", USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 75.0
        assert result.raw_data["attempts"] == 3
        assert result.raw_data["puzzle_number"] == 1337

    def test_score_for_six_attempts(self):
        result = self.parser.parse("Wordle 1340 6/6", USER_ID, TIMESTAMP)
        assert result.base_score == 20.0
        assert result.raw_data["attempts"] == 6

    def test_failed_result_scores_zero(self):
        result = self.parser.parse("Wordle 1339 X/6", USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 0.0
        assert result.raw_data["attempts"] is None

    def test_hard_mode_flag(self):
        result = self.parser.parse("Wordle 1340 4/6*", USER_ID, TIMESTAMP)
        assert result.raw_data["hard_mode"] is True

    def test_non_hard_mode_flag(self):
        result = self.parser.parse("Wordle 1340 4/6", USER_ID, TIMESTAMP)
        assert result.raw_data["hard_mode"] is False

    def test_puzzle_number_strips_comma(self):
        result = self.parser.parse("Wordle 1,234 2/6", USER_ID, TIMESTAMP)
        assert result.raw_data["puzzle_number"] == 1234

    def test_date_comes_from_timestamp(self):
        result = self.parser.parse("Wordle 9999 2/6", USER_ID, TIMESTAMP)
        assert result.date == TIMESTAMP.date()

    def test_user_id_preserved(self):
        result = self.parser.parse("Wordle 1338 2/6", USER_ID, TIMESTAMP)
        assert result.user_id == USER_ID

    def test_game_id(self):
        result = self.parser.parse("Wordle 1338 2/6", USER_ID, TIMESTAMP)
        assert result.game_id == "wordle"

    def test_returns_none_for_non_matching(self):
        assert self.parser.parse("not a wordle result", USER_ID, TIMESTAMP) is None
