import math
import re
from datetime import datetime

from .base import GameParser, ParseResult

_PATTERN = re.compile(r"PokeDoku\b.*?Score:\s*(\d)/9", re.DOTALL)
_UNIQUENESS_PATTERN = re.compile(r"Uniqueness:\s*(\d+)/(\d+)")


class PokeDokuParser(GameParser):
    @property
    def game_id(self) -> str:
        return "pokedoku"

    @property
    def game_name(self) -> str:
        return "PokéDoku"

    @property
    def reaction(self) -> str:
        return "🔴"

    def can_parse(self, message: str) -> bool:
        return bool(_PATTERN.search(message))

    def parse(self, message: str, user_id: str, timestamp: datetime) -> ParseResult | None:
        m = _PATTERN.search(message)
        if not m:
            return None

        score = int(m.group(1))
        base_score = float(math.ceil(score * 100 / 9))

        raw_data: dict = {"score": score, "max_score": 9}

        um = _UNIQUENESS_PATTERN.search(message)
        if um:
            raw_data["uniqueness"] = int(um.group(1))
            raw_data["uniqueness_max"] = int(um.group(2))

        return ParseResult(
            game_id=self.game_id,
            user_id=user_id,
            date=timestamp.date(),
            base_score=base_score,
            raw_data=raw_data,
            message_text=message,
        )
