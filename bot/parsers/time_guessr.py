import math
import re
from datetime import datetime

from .base import GameParser, ParseResult

_PATTERN = re.compile(r"TimeGuessr #(\d+)(?:\s+—)?\s+([\d,]+)/50,000")


class TimeGuessrParser(GameParser):
    @property
    def game_id(self) -> str:
        return "time_guessr"

    @property
    def game_name(self) -> str:
        return "Time Guessr"

    @property
    def reaction(self) -> str:
        return "⏰"

    def can_parse(self, message: str) -> bool:
        return bool(_PATTERN.search(message))

    def parse(self, message: str, user_id: str, timestamp: datetime) -> ParseResult | None:
        m = _PATTERN.search(message)
        if not m:
            return None

        puzzle_number = int(m.group(1))
        raw_score = int(m.group(2).replace(",", ""))
        base_score = float(math.ceil(raw_score * 100 / 50_000))

        return ParseResult(
            game_id=self.game_id,
            user_id=user_id,
            date=timestamp.date(),
            base_score=base_score,
            raw_data={
                "puzzle_number": puzzle_number,
                "raw_score": raw_score,
                "max_score": 50_000,
            },
            message_text=message,
        )
