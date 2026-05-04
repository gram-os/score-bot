import re
from datetime import datetime

from .base import GameParser, ParseResult

_PATTERN = re.compile(r"I solved the Mini in (\d+):(\d{2})!?")


class MiniCrosswordParser(GameParser):
    @property
    def game_id(self) -> str:
        return "mini_crossword"

    @property
    def game_name(self) -> str:
        return "Mini Crossword"

    @property
    def reaction(self) -> str:
        return "✏️"

    def can_parse(self, message: str) -> bool:
        return bool(_PATTERN.search(message))

    def parse(self, message: str, user_id: str, timestamp: datetime) -> ParseResult | None:
        m = _PATTERN.search(message)
        if not m:
            return None

        minutes = int(m.group(1))
        seconds = int(m.group(2))
        if minutes < 0 or not 0 <= seconds < 60:
            return None
        total_seconds = minutes * 60 + seconds
        if total_seconds < 0:
            return None

        base_score = float(max(0, 100 - total_seconds))

        return ParseResult(
            game_id=self.game_id,
            user_id=user_id,
            date=timestamp.date(),
            base_score=base_score,
            raw_data={
                "minutes": minutes,
                "seconds": seconds,
                "total_seconds": total_seconds,
            },
            message_text=message,
        )
