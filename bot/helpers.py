from typing import NamedTuple

from discord import app_commands

from bot.achievements import ACHIEVEMENTS
from bot.database import get_leaderboard


class UserOverview(NamedTuple):
    total_pts: float
    overall_rank: int | None
    total_subs: int


def get_user_overview(session, user_id: str) -> UserOverview:
    all_rows = get_leaderboard(session, period="alltime")
    row = next((r for r in all_rows if r.user_id == user_id), None)
    return UserOverview(
        total_pts=row.total_score if row else 0.0,
        overall_rank=row.rank if row else None,
        total_subs=row.submission_count if row else 0,
    )


def format_badges(user_achievements, separator: str = "  ·  ") -> str:
    parts = [f"{ach.icon} {ach.name}" for ua in user_achievements if (ach := ACHIEVEMENTS.get(ua.achievement_slug))]
    return separator.join(parts) if parts else "None yet — keep playing!"


def resolve_game_label(registry, game_id: str | None) -> str:
    if not game_id or game_id == "all":
        return "All Games"
    parser = registry.get_parser(game_id)
    return parser.game_name if parser else game_id


def game_autocomplete_choices(
    registry,
    current: str,
    include_all: bool = False,
) -> list[app_commands.Choice[str]]:
    choices: list[app_commands.Choice[str]] = []
    if include_all:
        choices.append(app_commands.Choice(name="All Games", value="all"))
    choices += [app_commands.Choice(name=p.game_name, value=p.game_id) for p in registry.all_parsers()]
    if current:
        q = current.lower()
        choices = [c for c in choices if q in c.name.lower() or q in c.value.lower()]
    return choices[:25]
