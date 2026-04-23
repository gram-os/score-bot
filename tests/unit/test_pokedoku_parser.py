from datetime import datetime

from bot.parsers.pokedoku import PokeDokuParser

USER_ID = "123456789"
TIMESTAMP = datetime(2024, 1, 15, 12, 0, 0)

CHAMPION_MSG = (
    "🌟 PokeDoku Champion 🌟\n"
    "By: Enixxx\n\n"
    "Score: 9/9\n"
    "Uniqueness: 63/28\n\n"
    "✅ ✅ ✅ \n"
    "✅ ✅ ✅ \n"
    "✅ ✅ ✅ \n\n"
    "Play at: https://pokedoku.com/share/6bF1pIMNXI47"
)

PARTIAL_MSG = (
    "🔴 PokeDoku Summary ⚪️\n"
    "By: Enixxx\n\n"
    "Score: 7/9\n"
    "Uniqueness: 292/28\n\n"
    "✅ ✅ ✅ \n"
    "✅ ✅ ✅ \n"
    "✅ 🟥 🟥 \n\n"
    "Play at: https://pokedoku.com/share/htKrF4iSIAQ0"
)


class TestPokeDokuParserCanParse:
    parser = PokeDokuParser()

    def test_champion_message(self):
        assert self.parser.can_parse(CHAMPION_MSG)

    def test_partial_message(self):
        assert self.parser.can_parse(PARTIAL_MSG)

    def test_rejects_wordle(self):
        assert not self.parser.can_parse("Wordle 1,337 3/6\n🟨⬜⬜⬜🟩")

    def test_rejects_plain_text(self):
        assert not self.parser.can_parse("hello world")


class TestPokeDokuParserParse:
    parser = PokeDokuParser()

    def test_perfect_score(self):
        result = self.parser.parse(CHAMPION_MSG, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 100.0
        assert result.raw_data["score"] == 9
        assert result.raw_data["max_score"] == 9

    def test_partial_score(self):
        result = self.parser.parse(PARTIAL_MSG, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 78.0
        assert result.raw_data["score"] == 7

    def test_uniqueness_captured(self):
        result = self.parser.parse(CHAMPION_MSG, USER_ID, TIMESTAMP)
        assert result.raw_data["uniqueness"] == 63
        assert result.raw_data["uniqueness_max"] == 28

    def test_game_id(self):
        result = self.parser.parse(CHAMPION_MSG, USER_ID, TIMESTAMP)
        assert result.game_id == "pokedoku"

    def test_user_id_preserved(self):
        result = self.parser.parse(CHAMPION_MSG, USER_ID, TIMESTAMP)
        assert result.user_id == USER_ID

    def test_date_from_timestamp(self):
        result = self.parser.parse(CHAMPION_MSG, USER_ID, TIMESTAMP)
        assert result.date == TIMESTAMP.date()

    def test_returns_none_for_non_matching(self):
        assert self.parser.parse("not a pokedoku result", USER_ID, TIMESTAMP) is None
