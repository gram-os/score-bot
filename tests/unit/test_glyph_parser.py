from datetime import datetime, date

from bot.parsers.glyph import GlyphParser

USER_ID = "123456789"
TIMESTAMP = datetime(2024, 1, 15, 12, 0, 0)


class TestGlyphParserCanParse:
    parser = GlyphParser()

    def test_valid_message(self):
        assert self.parser.can_parse("Glyph 2024-01-15 | 2/4")

    def test_failed_result(self):
        assert self.parser.can_parse("Glyph 2024-01-15 | X/4")

    def test_rejects_wordle(self):
        assert not self.parser.can_parse("Wordle 1338 2/6")

    def test_rejects_plain_text(self):
        assert not self.parser.can_parse("nothing to see here")


class TestGlyphParserParse:
    parser = GlyphParser()

    def test_score_for_one_attempt(self):
        result = self.parser.parse("Glyph 2024-01-15 | 1/4", USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 100.0
        assert result.raw_data["attempts"] == 1

    def test_score_for_two_attempts(self):
        result = self.parser.parse("Glyph 2024-01-15 | 2/4", USER_ID, TIMESTAMP)
        assert result.base_score == 80.0

    def test_score_for_four_attempts(self):
        result = self.parser.parse("Glyph 2024-01-15 | 4/4", USER_ID, TIMESTAMP)
        assert result.base_score == 40.0

    def test_failed_result_scores_zero(self):
        result = self.parser.parse("Glyph 2024-01-15 | X/4", USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 0.0
        assert result.raw_data["attempts"] is None

    def test_date_comes_from_puzzle_date_in_message(self):
        result = self.parser.parse("Glyph 2024-06-20 | 1/4", USER_ID, TIMESTAMP)
        assert result.date == date(2024, 6, 20)

    def test_game_id(self):
        result = self.parser.parse("Glyph 2024-01-15 | 1/4", USER_ID, TIMESTAMP)
        assert result.game_id == "glyph"

    def test_returns_none_for_non_matching(self):
        assert self.parser.parse("not glyph", USER_ID, TIMESTAMP) is None
