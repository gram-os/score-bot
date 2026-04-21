from datetime import datetime, date

from bot.parsers.wordle import WordleParser
from bot.parsers.glyph import GlyphParser
from bot.parsers.enclose_horse import EnclosHorseParser

USER_ID = "123456789"
TIMESTAMP = datetime(2024, 1, 15, 12, 0, 0)


# ---------------------------------------------------------------------------
# WordleParser
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# GlyphParser
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# EnclosHorseParser
# ---------------------------------------------------------------------------

HORSE_DAY_42 = "https://enclose.horse/ Day 42\n75.5% 🐴"
HORSE_WITH_BONUS = "https://enclose.horse/ Day 42\n75.5% 🐴\n50.0% 🐴🐎"
HORSE_NO_MAIN = "https://enclose.horse/ Day 42\n50.0% 🐴🐎"


class TestEnclosHorseParserCanParse:
    parser = EnclosHorseParser()

    def test_valid_message(self):
        assert self.parser.can_parse(HORSE_DAY_42)

    def test_with_bonus_round(self):
        assert self.parser.can_parse(HORSE_WITH_BONUS)

    def test_rejects_wordle(self):
        assert not self.parser.can_parse("Wordle 1338 2/6")

    def test_rejects_url_not_at_start(self):
        assert not self.parser.can_parse("check this: https://enclose.horse/ Day 42")


class TestEnclosHorseParserParse:
    parser = EnclosHorseParser()

    def test_main_percentage_only(self):
        result = self.parser.parse(HORSE_DAY_42, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 75.5
        assert result.raw_data["main_pct"] == 75.5
        assert result.raw_data["bonus_rounds"] == []

    def test_day_number_captured(self):
        result = self.parser.parse(HORSE_DAY_42, USER_ID, TIMESTAMP)
        assert result.raw_data["day"] == 42

    def test_bonus_round_adds_to_score(self):
        result = self.parser.parse(HORSE_WITH_BONUS, USER_ID, TIMESTAMP)
        # 50% of 15 pts = 7.5 → rounds to 8
        assert result.raw_data["bonus_rounds"] == [
            {"variant": "🐎", "pct": 50.0, "pts": 8}
        ]
        assert result.base_score == 75.5 + 8

    def test_returns_none_when_no_main_percentage(self):
        assert self.parser.parse(HORSE_NO_MAIN, USER_ID, TIMESTAMP) is None

    def test_date_comes_from_timestamp(self):
        result = self.parser.parse(HORSE_DAY_42, USER_ID, TIMESTAMP)
        assert result.date == TIMESTAMP.date()

    def test_game_id(self):
        result = self.parser.parse(HORSE_DAY_42, USER_ID, TIMESTAMP)
        assert result.game_id == "enclose_horse"

    def test_returns_none_for_non_matching(self):
        assert self.parser.parse("unrelated message", USER_ID, TIMESTAMP) is None
