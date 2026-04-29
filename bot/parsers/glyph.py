import re
from datetime import date, datetime

from .base import GameParser, ParseResult

_PATTERN = re.compile(r"Glyph (\d{4}-\d{2}-\d{2}) \| ([X\d])/4")

_SCORE_TABLE = {1: 100, 2: 80, 3: 60, 4: 40}


class GlyphParser(GameParser):
    @property
    def game_id(self) -> str:
        return "glyph"

    @property
    def game_name(self) -> str:
        return "Glyph"

    @property
    def reaction(self) -> str:
        return "🔍"

    def can_parse(self, message: str) -> bool:
        return bool(_PATTERN.search(message))

    def parse(self, message: str, user_id: str, timestamp: datetime) -> ParseResult | None:
        m = _PATTERN.search(message)
        if not m:
            return None

        puzzle_date = date.fromisoformat(m.group(1))
        attempts_raw = m.group(2)

        if attempts_raw == "X":
            attempts = None
            base_score = 0.0
        else:
            attempts = int(attempts_raw)
            base_score = float(_SCORE_TABLE.get(attempts, 0))

        return ParseResult(
            game_id=self.game_id,
            user_id=user_id,
            date=puzzle_date,
            base_score=base_score,
            raw_data={
                "puzzle_date": m.group(1),
                "attempts": attempts,
                "max_attempts": 4,
            },
            message_text=message,
        )
