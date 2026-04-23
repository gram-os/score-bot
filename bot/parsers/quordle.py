import re
from datetime import datetime

from .base import GameParser, ParseResult

_HEADER_PATTERN = re.compile(r"Daily Quordle #(\d+)")

# Emoji digit → attempt count; 🟥 = failed word, counts as 9
_EMOJI_MAP = {
    "1️⃣": 1,
    "2️⃣": 2,
    "3️⃣": 3,
    "4️⃣": 4,
    "5️⃣": 5,
    "6️⃣": 6,
    "7️⃣": 7,
    "8️⃣": 8,
    "9️⃣": 9,
    "🟥": 9,
}
# Match any single emoji digit or failure square
_EMOJI_PATTERN = re.compile(r"(?:1️⃣|2️⃣|3️⃣|4️⃣|5️⃣|6️⃣|7️⃣|8️⃣|9️⃣|🟥)")


class QuordleParser(GameParser):
    @property
    def game_id(self) -> str:
        return "quordle"

    @property
    def game_name(self) -> str:
        return "Quordle"

    @property
    def reaction(self) -> str:
        return "4️⃣"

    def can_parse(self, message: str) -> bool:
        return bool(_HEADER_PATTERN.search(message))

    def parse(self, message: str, user_id: str, timestamp: datetime) -> ParseResult | None:
        header_match = _HEADER_PATTERN.search(message)
        if not header_match:
            return None

        puzzle_number = int(header_match.group(1))
        emojis = _EMOJI_PATTERN.findall(message)

        if len(emojis) != 4:
            return None

        attempts = [_EMOJI_MAP[e] for e in emojis]
        total_attempts = sum(attempts)
        failed = 9 in attempts

        # base_score = max(0, 100 - (total_attempts - 4) * 10)
        # best case: 4 attempts total (1 each) → 60 pts; worst: clamped to 0
        base_score = float(max(0, 100 - (total_attempts - 4) * 10))

        return ParseResult(
            game_id=self.game_id,
            user_id=user_id,
            date=timestamp.date(),
            base_score=base_score,
            raw_data={
                "puzzle_number": puzzle_number,
                "attempts": attempts,
                "total_attempts": total_attempts,
                "failed": failed,
            },
        )
