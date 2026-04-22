import re
from datetime import datetime

from .base import GameParser, ParseResult

_HEADER_PATTERN = re.compile(r"Connections\s*\nPuzzle #(\d+)", re.IGNORECASE)

_COLOR_SQUARES = {"🟨", "🟩", "🟦", "🟪"}
_ROW_PATTERN = re.compile(r"[🟨🟩🟦🟪]{4}")


def _is_pure_row(row: str) -> bool:
    return len(set(row)) == 1


class ConnectionsParser(GameParser):
    @property
    def game_id(self) -> str:
        return "connections"

    @property
    def game_name(self) -> str:
        return "Connections"

    @property
    def reaction(self) -> str:
        return "🔗"

    def can_parse(self, message: str) -> bool:
        return bool(_HEADER_PATTERN.search(message))

    def parse(
        self, message: str, user_id: str, timestamp: datetime
    ) -> ParseResult | None:
        header_match = _HEADER_PATTERN.search(message)
        if not header_match:
            return None

        puzzle_number = int(header_match.group(1))
        rows = _ROW_PATTERN.findall(message)

        if not rows:
            return None

        # misses = rows where all 4 squares are not the same colour
        # base_score = max(0, 100 - misses * 20)
        misses = sum(1 for row in rows if not _is_pure_row(row))
        base_score = float(max(0, 100 - misses * 20))

        return ParseResult(
            game_id=self.game_id,
            user_id=user_id,
            date=timestamp.date(),
            base_score=base_score,
            raw_data={
                "puzzle_number": puzzle_number,
                "misses": misses,
                "rows_played": len(rows),
            },
        )
