from types import SimpleNamespace
from unittest.mock import MagicMock


from bot.helpers import format_badges, game_autocomplete_choices, resolve_game_label


def _make_parser(game_id: str, game_name: str):
    p = MagicMock()
    p.game_id = game_id
    p.game_name = game_name
    return p


def _make_registry(*parsers):
    r = MagicMock()
    r.all_parsers.return_value = list(parsers)
    r.get_parser.side_effect = lambda gid: next((p for p in parsers if p.game_id == gid), None)
    return r


def _make_achievement(slug: str, icon: str, name: str):
    return SimpleNamespace(slug=slug, icon=icon, name=name)


def _make_user_achievement(slug: str):
    return SimpleNamespace(achievement_slug=slug)


class TestFormatBadges:
    def test_no_achievements_returns_fallback(self, monkeypatch):
        monkeypatch.setattr("bot.achievements.ACHIEVEMENTS", {})
        result = format_badges([])
        assert result == "None yet — keep playing!"

    def test_earned_achievements_formatted(self, monkeypatch):
        monkeypatch.setattr(
            "bot.achievements.ACHIEVEMENTS",
            {"streak_3": _make_achievement("streak_3", "🔥", "On Fire")},
        )
        ua = _make_user_achievement("streak_3")
        result = format_badges([ua])
        assert result == "🔥 On Fire"

    def test_unknown_slug_skipped(self, monkeypatch):
        monkeypatch.setattr("bot.achievements.ACHIEVEMENTS", {})
        ua = _make_user_achievement("nonexistent")
        result = format_badges([ua])
        assert result == "None yet — keep playing!"

    def test_custom_separator(self, monkeypatch):
        monkeypatch.setattr(
            "bot.achievements.ACHIEVEMENTS",
            {
                "a": _make_achievement("a", "🎯", "A"),
                "b": _make_achievement("b", "🏆", "B"),
            },
        )
        result = format_badges([_make_user_achievement("a"), _make_user_achievement("b")], separator=" | ")
        assert result == "🎯 A | 🏆 B"


class TestResolveGameLabel:
    def test_none_returns_all_games(self):
        assert resolve_game_label(MagicMock(), None) == "All Games"

    def test_all_value_returns_all_games(self):
        assert resolve_game_label(MagicMock(), "all") == "All Games"

    def test_known_game_returns_parser_name(self):
        parser = _make_parser("wordle", "Wordle")
        registry = _make_registry(parser)
        assert resolve_game_label(registry, "wordle") == "Wordle"

    def test_unknown_game_returns_game_id(self):
        registry = _make_registry()
        assert resolve_game_label(registry, "unknown_game") == "unknown_game"


class TestGameAutocompleteChoices:
    def setup_method(self):
        self.registry = _make_registry(
            _make_parser("wordle", "Wordle"),
            _make_parser("connections", "Connections"),
        )

    def test_no_filter_returns_all_parsers(self):
        choices = game_autocomplete_choices(self.registry, "")
        names = [c.name for c in choices]
        assert "Wordle" in names
        assert "Connections" in names

    def test_include_all_prepends_all_games(self):
        choices = game_autocomplete_choices(self.registry, "", include_all=True)
        assert choices[0].name == "All Games"
        assert choices[0].value == "all"

    def test_filter_by_name(self):
        choices = game_autocomplete_choices(self.registry, "word")
        assert len(choices) == 1
        assert choices[0].name == "Wordle"

    def test_filter_case_insensitive(self):
        choices = game_autocomplete_choices(self.registry, "CONN")
        assert len(choices) == 1
        assert choices[0].name == "Connections"

    def test_empty_current_returns_all_without_filtering(self):
        choices = game_autocomplete_choices(self.registry, "")
        assert len(choices) == 2

    def test_no_match_returns_empty(self):
        choices = game_autocomplete_choices(self.registry, "zzz")
        assert choices == []

    def test_capped_at_25(self):
        parsers = [_make_parser(f"game_{i}", f"Game {i}") for i in range(30)]
        registry = _make_registry(*parsers)
        choices = game_autocomplete_choices(registry, "")
        assert len(choices) == 25
