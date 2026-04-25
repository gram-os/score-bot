from datetime import datetime


from bot.parsers.betweenle import BetweenleParser

USER_ID = "123456789"
TIMESTAMP = datetime(2024, 1, 15, 12, 0, 0)

SAMPLE_3_OF_5 = "Betweenle 1136 - 3/5:\n\n🏆🏆🏆\n\n⬇️⬇️⬆️⬆️⬇️ - ⬇️⬇️⬆️ - ⬆️🟩⬜ - ⬜⬜ - ⬜"
SAMPLE_1_OF_5 = "Betweenle 1136 - 1/5:\n\n🏆\n\n⬆️⬇️⬆️⬇️⬆️ - ⬇️⬇️⬆️ - ⬆️⬆️⬇️ - ⬇️⬇️ - 🟩"
SAMPLE_4_OF_5 = "Betweenle 1064 - 4/5:\n\n🏆🏆🏆🏆\n\n⬆️⬆️⬇️⬆️⬆️ - ⬆️🟩⬜ - ⬜⬜⬜ - ⬜⬜ - ⬜"
SAMPLE_2_OF_5 = "Betweenle 1064 - 2/5:\n\n🏆🏆\n\n⬆️⬆️⬆️⬆️⬆️ - ⬆️⬆️⬆️ - ⬇️⬇️⬇️ - 🟩⬜ - ⬜"
SAMPLE_5_OF_5 = "Betweenle 1064 - 5/5:\n\n🏆🏆🏆🏆🏆\n\n🟩⬜⬜⬜⬜ - ⬜⬜⬜ - ⬜⬜⬜ - ⬜⬜ - ⬜"
SAMPLE_FAIL = "Betweenle 1136 - 0/5:\n\n\n\n⬇️⬆️⬇️⬆️⬆️ - ⬇️⬇️⬇️ - ⬇️⬇️⬇️ - ⬇️⬇️ - ⬇️"


class TestBetweenleParserCanParse:
    parser = BetweenleParser()

    def test_three_of_five(self):
        assert self.parser.can_parse(SAMPLE_3_OF_5)

    def test_one_of_five(self):
        assert self.parser.can_parse(SAMPLE_1_OF_5)

    def test_four_of_five(self):
        assert self.parser.can_parse(SAMPLE_4_OF_5)

    def test_fail_result(self):
        assert self.parser.can_parse(SAMPLE_FAIL)

    def test_rejects_wordle(self):
        assert not self.parser.can_parse("Wordle 1338 3/6\n🟨⬜⬜⬜🟩")

    def test_rejects_plain_text(self):
        assert not self.parser.can_parse("hello world")


class TestBetweenleParserParse:
    parser = BetweenleParser()

    def test_five_of_five_scores_100(self):
        # 1 guess (🟩 only in group 1) → max score
        result = self.parser.parse(SAMPLE_5_OF_5, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 100.0
        assert result.raw_data["total_guesses"] == 1

    def test_four_of_five_score(self):
        # 7 guesses → ceil((14-7)/13 * 100) = 54
        result = self.parser.parse(SAMPLE_4_OF_5, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 54.0
        assert result.raw_data["total_guesses"] == 7

    def test_three_of_five_score(self):
        # 10 guesses → ceil((14-10)/13 * 100) = 31
        result = self.parser.parse(SAMPLE_3_OF_5, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 31.0
        assert result.raw_data["total_guesses"] == 10

    def test_two_of_five_score(self):
        # 12 guesses → ceil((14-12)/13 * 100) = 16
        result = self.parser.parse(SAMPLE_2_OF_5, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 16.0
        assert result.raw_data["total_guesses"] == 12

    def test_one_of_five_hits_floor(self):
        # 14 guesses → raw score 0.0, clamped to floor 5.0
        result = self.parser.parse(SAMPLE_1_OF_5, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 5.0
        assert result.raw_data["total_guesses"] == 14

    def test_failed_result_scores_zero(self):
        result = self.parser.parse(SAMPLE_FAIL, USER_ID, TIMESTAMP)
        assert result is not None
        assert result.base_score == 0.0
        assert result.raw_data["attempts"] is None
        assert result.raw_data["total_guesses"] is None

    def test_attempts_in_raw_data(self):
        result = self.parser.parse(SAMPLE_3_OF_5, USER_ID, TIMESTAMP)
        assert result.raw_data["attempts"] == 3

    def test_puzzle_number_in_raw_data(self):
        result = self.parser.parse(SAMPLE_3_OF_5, USER_ID, TIMESTAMP)
        assert result.raw_data["puzzle_number"] == 1136

    def test_max_guesses_in_raw_data(self):
        result = self.parser.parse(SAMPLE_3_OF_5, USER_ID, TIMESTAMP)
        assert result.raw_data["max_guesses"] == 14

    def test_game_id(self):
        result = self.parser.parse(SAMPLE_3_OF_5, USER_ID, TIMESTAMP)
        assert result.game_id == "betweenle"

    def test_date_from_timestamp(self):
        result = self.parser.parse(SAMPLE_3_OF_5, USER_ID, TIMESTAMP)
        assert result.date == TIMESTAMP.date()

    def test_user_id_preserved(self):
        result = self.parser.parse(SAMPLE_3_OF_5, USER_ID, TIMESTAMP)
        assert result.user_id == USER_ID

    def test_returns_none_for_non_matching(self):
        assert self.parser.parse("not a betweenle result", USER_ID, TIMESTAMP) is None
