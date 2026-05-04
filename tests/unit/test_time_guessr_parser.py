from datetime import datetime

from bot.parsers.time_guessr import TimeGuessrParser

USER_ID = "123456789"
TIMESTAMP = datetime(2024, 1, 15, 12, 0, 0)

TIMEGUESSR_SAMPLE = (
    "TimeGuessr #1057 31,590/50,000\n"
    "🌎🟩🟩🟨 📅🟩🟨⬛\n"
    "🌎🟩🟩🟨 📅🟩⬛⬛\n"
    "🌎⬛️⬛️⬛️ 📅🟩🟨⬛\n"
    "🌎🟩🟩🟨 📅🟩⬛⬛\n"
    "🌎🟩🟩🟨 📅⬛️⬛️⬛️\n"
    "https://timeguessr.com/"
)
TIMEGUESSR_PERFECT = "TimeGuessr #999 50,000/50,000"
TIMEGUESSR_LOW = "TimeGuessr #42 5,000/50,000"
TIMEGUESSR_MOBILE = (
    "TimeGuessr #1061 — 33,133/50,000\n"
    "\n"
    "1️⃣ 🏆8891 - 📅5y - 🌍1554ft\n"
    "2️⃣ 🏆4873 - 📅29y - 🌍4.1mi\n"
    "3️⃣ 🏆8800 - 📅3y - 🌍186.4mi\n"
    "4️⃣ 🏆4208 - 📅8y - 🌍1476.9mi\n"
    "5️⃣ 🏆6361 - 📅9y - 🌍396.9mi\n"
    "\n"
    "https://timeguessr.com/"
)


class TestTimeGuessrParserCanParse:
    parser = TimeGuessrParser()

    def test_valid_full_message(self):
        assert self.parser.can_parse(TIMEGUESSR_SAMPLE)

    def test_valid_header_only(self):
        assert self.parser.can_parse("TimeGuessr #1057 31,590/50,000")

    def test_perfect_score(self):
        assert self.parser.can_parse(TIMEGUESSR_PERFECT)

    def test_valid_mobile_format(self):
        assert self.parser.can_parse(TIMEGUESSR_MOBILE)

    def test_rejects_wordle(self):
        assert not self.parser.can_parse("Wordle 1,337 3/6")

    def test_rejects_plain_text(self):
        assert not self.parser.can_parse("hello world")


class TestTimeGuessrParserParse:
    parser = TimeGuessrParser()

    def test_score_ceiled_integer(self):
        result = self.parser.parse(TIMEGUESSR_SAMPLE, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 64.0
        assert result.raw_data["raw_score"] == 31590
        assert result.raw_data["max_score"] == 50_000
        assert result.raw_data["puzzle_number"] == 1057

    def test_perfect_score_is_100(self):
        result = self.parser.parse(TIMEGUESSR_PERFECT, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 100.0

    def test_low_score(self):
        result = self.parser.parse(TIMEGUESSR_LOW, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 10.0

    def test_score_is_float(self):
        result = self.parser.parse(TIMEGUESSR_SAMPLE, USER_ID, TIMESTAMP)
        assert isinstance(result.base_score, float)

    def test_game_id(self):
        result = self.parser.parse(TIMEGUESSR_SAMPLE, USER_ID, TIMESTAMP)
        assert result.game_id == "time_guessr"

    def test_date_from_timestamp(self):
        result = self.parser.parse(TIMEGUESSR_SAMPLE, USER_ID, TIMESTAMP)
        assert result.date == TIMESTAMP.date()

    def test_user_id_preserved(self):
        result = self.parser.parse(TIMEGUESSR_SAMPLE, USER_ID, TIMESTAMP)
        assert result.user_id == USER_ID

    def test_mobile_format_score(self):
        result = self.parser.parse(TIMEGUESSR_MOBILE, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 67.0
        assert result.raw_data["raw_score"] == 33133
        assert result.raw_data["puzzle_number"] == 1061

    def test_returns_none_for_unrecognised(self):
        assert self.parser.parse("unrelated message", USER_ID, TIMESTAMP) is None

    def test_returns_none_for_score_above_max(self):
        assert self.parser.parse("TimeGuessr #1 60,000/50,000", USER_ID, TIMESTAMP) is None
