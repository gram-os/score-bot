import math
import re
from datetime import datetime

from .base import GameParser, ParseResult

_PATTERN = re.compile(r"Betweenle (\d+) - (\d+)/5:?")

_MAX_GUESSES = 14
_WIN_SCORE_FLOOR = 5.0


def _count_guesses(message: str) -> int:
    return message.count("⬆️") + message.count("⬇️") + message.count("🟩")


def _score_from_guesses(total_guesses: int) -> float:
    raw = math.ceil((_MAX_GUESSES - total_guesses) / (_MAX_GUESSES - 1) * 100.0)
    return float(max(_WIN_SCORE_FLOOR, raw))


class BetweenleParser(GameParser):
    @property
    def game_id(self) -> str:
        return "betweenle"

    @property
    def game_name(self) -> str:
        return "Betweenle"

    @property
    def reaction(self) -> str:
        return "🔀"

    def can_parse(self, message: str) -> bool:
        return bool(_PATTERN.search(message))

    def parse(self, message: str, user_id: str, timestamp: datetime) -> ParseResult | None:
        m = _PATTERN.search(message)
        if not m:
            return None

        puzzle_number = int(m.group(1))
        attempts = int(m.group(2))

        if attempts == 0:
            return ParseResult(
                game_id=self.game_id,
                user_id=user_id,
                date=timestamp.date(),
                base_score=0.0,
                raw_data={
                    "puzzle_number": puzzle_number,
                    "attempts": None,
                    "total_guesses": None,
                    "max_guesses": _MAX_GUESSES,
                },
            )

        total_guesses = _count_guesses(message)
        base_score = _score_from_guesses(total_guesses)

        return ParseResult(
            game_id=self.game_id,
            user_id=user_id,
            date=timestamp.date(),
            base_score=base_score,
            raw_data={
                "puzzle_number": puzzle_number,
                "attempts": attempts,
                "total_guesses": total_guesses,
                "max_guesses": _MAX_GUESSES,
            },
        )
