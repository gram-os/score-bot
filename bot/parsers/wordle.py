import re
from datetime import datetime

from .base import GameParser, ParseResult

_PATTERN = re.compile(r"Wordle [\d,]+ ([X\d]+)/6(\*)?")

_SCORE_TABLE = {1: 100, 2: 90, 3: 75, 4: 60, 5: 40, 6: 20}


class WordleParser(GameParser):
    @property
    def game_id(self) -> str:
        return "wordle"

    @property
    def game_name(self) -> str:
        return "Wordle"

    @property
    def reaction(self) -> str:
        return "🟩"

    def can_parse(self, message: str) -> bool:
        return bool(_PATTERN.search(message))

    def parse(self, message: str, user_id: str, timestamp: datetime) -> ParseResult | None:
        m = _PATTERN.search(message)
        if not m:
            return None

        puzzle_number_match = re.search(r"Wordle ([\d,]+)", message)
        puzzle_number = int(puzzle_number_match.group(1).replace(",", ""))

        attempts_raw = m.group(1)
        hard_mode = m.group(2) == "*"

        if attempts_raw == "X":
            attempts = None
            base_score = 0.0
        else:
            attempts = int(attempts_raw)
            base_score = float(_SCORE_TABLE.get(attempts, 0))

        return ParseResult(
            game_id=self.game_id,
            user_id=user_id,
            date=timestamp.date(),
            base_score=base_score,
            raw_data={
                "puzzle_number": puzzle_number,
                "attempts": attempts,
                "max_attempts": 6,
                "hard_mode": hard_mode,
            },
        )
