from datetime import datetime

from bot.parsers.connections import ConnectionsParser

USER_ID = "123456789"
TIMESTAMP = datetime(2024, 1, 15, 12, 0, 0)

CONNECTIONS_PERFECT = "Connections\nPuzzle #100\n🟨🟨🟨🟨\n🟩🟩🟩🟩\n🟦🟦🟦🟦\n🟪🟪🟪🟪"
CONNECTIONS_TWO_MISSES = "Connections\nPuzzle #101\n🟨🟩🟦🟪\n🟩🟩🟩🟩\n🟨🟦🟨🟦\n🟦🟦🟦🟦\n🟨🟨🟨🟨\n🟪🟪🟪🟪"
CONNECTIONS_FAILED = "Connections\nPuzzle #102\n🟨🟩🟦🟪\n🟩🟨🟦🟪\n🟦🟨🟩🟪\n🟪🟨🟩🟦\n🟨🟨🟨🟩"


class TestConnectionsParserCanParse:
    parser = ConnectionsParser()

    def test_valid_message(self):
        assert self.parser.can_parse(CONNECTIONS_PERFECT)

    def test_rejects_unrelated(self):
        assert not self.parser.can_parse("unrelated message")

    def test_rejects_wordle(self):
        assert not self.parser.can_parse("Wordle 1,337 3/6")

    def test_rejects_partial_header(self):
        assert not self.parser.can_parse("Connections")


class TestConnectionsParserParse:
    parser = ConnectionsParser()

    def test_perfect_solve_zero_misses(self):
        # 0 misses → 100 pts
        result = self.parser.parse(CONNECTIONS_PERFECT, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 100.0
        assert result.raw_data["misses"] == 0
        assert result.raw_data["puzzle_number"] == 100
        assert result.raw_data["rows_played"] == 4

    def test_two_misses(self):
        # 2 non-pure rows → 100 - 2*20 = 60 pts
        result = self.parser.parse(CONNECTIONS_TWO_MISSES, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 60.0
        assert result.raw_data["misses"] == 2

    def test_failed_attempt_clamped_to_zero(self):
        # 5 non-pure rows → max(0, 100 - 100) = 0 pts
        result = self.parser.parse(CONNECTIONS_FAILED, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 0.0
        assert result.raw_data["misses"] == 5

    def test_game_id(self):
        result = self.parser.parse(CONNECTIONS_PERFECT, USER_ID, TIMESTAMP)
        assert result.game_id == "connections"

    def test_date_from_timestamp(self):
        result = self.parser.parse(CONNECTIONS_PERFECT, USER_ID, TIMESTAMP)
        assert result.date == TIMESTAMP.date()

    def test_returns_none_for_unrecognised(self):
        assert self.parser.parse("unrelated message", USER_ID, TIMESTAMP) is None

    def test_message_text_stored(self):
        result = self.parser.parse(CONNECTIONS_PERFECT, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.message_text == CONNECTIONS_PERFECT
