from types import SimpleNamespace

from bot.commands.submitted import format_submission_line, get_today_submissions


def _make_submission(base_score, speed_bonus, total_score, game_id="wordle", sub_date=None):
    from datetime import date

    return SimpleNamespace(
        base_score=base_score,
        speed_bonus=speed_bonus,
        total_score=total_score,
        game_id=game_id,
        date=sub_date or date.today(),
    )


class TestFormatSubmissionLine:
    def test_with_speed_bonus(self):
        sub = _make_submission(base_score=100, speed_bonus=15, total_score=115)
        result = format_submission_line("Wordle", sub)
        assert result == "**Wordle** 115 (100 + 15)"

    def test_zero_speed_bonus(self):
        sub = _make_submission(base_score=70, speed_bonus=0, total_score=70)
        result = format_submission_line("Time Guessr", sub)
        assert result == "**Time Guessr** 70 (70 + 0)"

    def test_float_scores_rounded_to_int(self):
        sub = _make_submission(base_score=85.0, speed_bonus=10.0, total_score=95.0)
        result = format_submission_line("Connections", sub)
        assert result == "**Connections** 95 (85 + 10)"


class TestGetTodaySubmissions:
    def test_returns_empty_when_no_submissions(self, monkeypatch):
        from unittest.mock import MagicMock

        session = MagicMock()
        session.execute.return_value.all.return_value = []

        result = get_today_submissions(session, "user123")
        assert result == []

    def test_returns_name_and_submission_pairs(self, monkeypatch):
        from unittest.mock import MagicMock

        sub = _make_submission(base_score=100, speed_bonus=15, total_score=115)
        game = SimpleNamespace(name="Wordle", id="wordle")

        session = MagicMock()
        session.execute.return_value.all.return_value = [(sub, game)]

        result = get_today_submissions(session, "user123")
        assert len(result) == 1
        assert result[0][0] == "Wordle"
        assert result[0][1] is sub
