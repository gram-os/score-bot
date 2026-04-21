import re
from datetime import datetime

from .base import GameParser, ParseResult

_HEADER = re.compile(r"^https://enclose\.horse/ Day (\d+)")
_RESULT_LINE = re.compile(r"(\d+(?:\.\d+)?)%\s*(🐴\S*)")

_HORSE = "🐴"


class EnclosHorseParser(GameParser):
    @property
    def game_id(self) -> str:
        return "enclose_horse"

    @property
    def game_name(self) -> str:
        return "Enclose.horse"

    @property
    def reaction(self) -> str:
        return "🐴"

    def can_parse(self, message: str) -> bool:
        return bool(_HEADER.match(message))

    def parse(self, message: str, user_id: str, timestamp: datetime) -> ParseResult | None:
        header_m = _HEADER.match(message)
        if not header_m:
            return None

        day = int(header_m.group(1))
        main_pct: float | None = None
        bonus_rounds: list[dict] = []

        for pct_str, horse_str in _RESULT_LINE.findall(message):
            pct = float(pct_str)
            variant = horse_str[len(_HORSE):]
            if not variant:
                main_pct = pct
            else:
                pts = round(pct / 100 * 15)
                bonus_rounds.append({"variant": variant, "pct": pct, "pts": pts})

        if main_pct is None:
            return None

        base_score = main_pct + sum(br["pts"] for br in bonus_rounds)

        return ParseResult(
            game_id=self.game_id,
            user_id=user_id,
            date=timestamp.date(),
            base_score=base_score,
            raw_data={
                "day": day,
                "main_pct": main_pct,
                "bonus_rounds": bonus_rounds,
            },
        )
