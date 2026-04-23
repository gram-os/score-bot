import importlib
import inspect
import pkgutil
from pathlib import Path

from bot.parsers.base import GameParser


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, GameParser] = {}
        self._discover()

    def _discover(self) -> None:
        parsers_dir = Path(__file__).parent
        package = "bot.parsers"

        for module_info in pkgutil.iter_modules([str(parsers_dir)]):
            if module_info.name in ("base", "registry"):
                continue
            module = importlib.import_module(f"{package}.{module_info.name}")
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, GameParser) and obj is not GameParser and not inspect.isabstract(obj):
                    instance = obj()
                    self._parsers[instance.game_id] = instance

    def get_parser(self, game_id: str) -> GameParser | None:
        return self._parsers.get(game_id)

    def all_parsers(self) -> list[GameParser]:
        return list(self._parsers.values())


registry = ParserRegistry()


def get_parser(game_id: str) -> GameParser | None:
    return registry.get_parser(game_id)


def all_parsers() -> list[GameParser]:
    return registry.all_parsers()
