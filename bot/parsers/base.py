from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class ParseResult:
    game_id: str
    user_id: str
    date: date
    base_score: float
    raw_data: dict = field(default_factory=dict)
    message_text: str | None = None


class GameParser(ABC):
    @property
    @abstractmethod
    def game_id(self) -> str: ...

    @property
    @abstractmethod
    def game_name(self) -> str: ...

    @property
    @abstractmethod
    def reaction(self) -> str: ...

    @abstractmethod
    def can_parse(self, message: str) -> bool: ...

    @abstractmethod
    def parse(self, message: str, user_id: str, timestamp: datetime) -> ParseResult | None: ...
