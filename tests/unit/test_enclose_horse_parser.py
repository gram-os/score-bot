from datetime import datetime

from bot.parsers.enclose_horse import EncloseHorseParser

USER_ID = "123456789"
TIMESTAMP = datetime(2024, 1, 15, 12, 0, 0)

HORSE_DAY_42_NO_HORSE = "https://enclose.horse Day 114\n🥉 okay 🥉 37%"
HORSE_DAY_42 = "https://enclose.horse/ Day 42\n75.5% 🐴"
HORSE_WITH_BONUS = "https://enclose.horse/ Day 42\n75.5% 🐴\n50.0% 🐴🐎"
HORSE_NO_MAIN = "https://enclose.horse/ Day 42\n50.0% 🐴🐎"


class TestEncloseHorseParserCanParse:
    parser = EncloseHorseParser()

    def test_valid_message(self):
        assert self.parser.can_parse(HORSE_DAY_42)
        assert self.parser.can_parse(HORSE_DAY_42_NO_HORSE)

    def test_with_bonus_round(self):
        assert self.parser.can_parse(HORSE_WITH_BONUS)

    def test_rejects_wordle(self):
        assert not self.parser.can_parse("Wordle 1338 2/6")

    def test_rejects_url_not_at_start(self):
        assert not self.parser.can_parse("check this: https://enclose.horse/ Day 42")


class TestEncloseHorseParserParse:
    parser = EncloseHorseParser()

    def test_main_percentage_only(self):
        result = self.parser.parse(HORSE_DAY_42, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 75.5
        assert result.raw_data["main_pct"] == 75.5
        assert result.raw_data["bonus_rounds"] == []

        result = self.parser.parse(HORSE_DAY_42_NO_HORSE, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 37
        assert result.raw_data["main_pct"] == 37
        assert result.raw_data["bonus_rounds"] == []

    def test_day_number_captured(self):
        result = self.parser.parse(HORSE_DAY_42, USER_ID, TIMESTAMP)
        assert result.raw_data["day"] == 42

    def test_bonus_round_adds_to_score(self):
        result = self.parser.parse(HORSE_WITH_BONUS, USER_ID, TIMESTAMP)
        # 50% of 15 pts = 7.5 → rounds to 8
        assert result.raw_data["bonus_rounds"] == [{"variant": "🐎", "pct": 50.0, "pts": 8}]
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
