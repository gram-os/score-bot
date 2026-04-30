from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot.achievements import check_and_award_achievements
from bot.database import Game, is_duplicate, record_submission, update_streak_on_submission
from bot.db.config import get_scoring_tz
from bot.parsers.registry import all_parsers


@dataclass
class BackfillRow:
    username: str
    game_name: str
    date: date
    base_score: float
    status: str
    message_id: str = ""
    reaction: str = ""


@dataclass
class BackfillResult:
    messages_scanned: int = 0
    recorded: list[BackfillRow] = field(default_factory=list)
    duplicates: list[BackfillRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _parse_timestamp(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _enabled_game_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Game).where(Game.enabled.is_(True))) or 0


def process_messages(session: Session, messages: list[dict]) -> BackfillResult:
    """Process Discord messages (oldest first) and record any new submissions."""
    result = BackfillResult(messages_scanned=len(messages))
    parsers = all_parsers()
    enabled_count = _enabled_game_count(session)
    scoring_tz = get_scoring_tz(session)

    for msg in messages:
        if msg.get("author", {}).get("bot"):
            continue

        content = msg.get("content", "")
        user_id = msg["author"]["id"]
        username = msg["author"].get("global_name") or msg["author"]["username"]
        timestamp = _parse_timestamp(msg["timestamp"])

        for parser in parsers:
            if not parser.can_parse(content):
                continue

            parse_result = parser.parse(content, user_id, timestamp)
            if parse_result is None:
                result.errors.append(f"Parser {parser.game_id} matched but returned None for {username}")
                break

            parse_result.date = timestamp.astimezone(scoring_tz).date()
            game = session.get(Game, parse_result.game_id)
            if game is None or not game.enabled:
                break

            if is_duplicate(session, parse_result.user_id, parse_result.game_id, parse_result.date):
                result.duplicates.append(
                    BackfillRow(
                        username=username,
                        game_name=game.name,
                        date=parse_result.date,
                        base_score=parse_result.base_score,
                        status="duplicate",
                    )
                )
                break

            submission = record_submission(session, parse_result, username)
            if submission is None:
                result.errors.append(f"Failed to record {parser.game_id} for {username}")
                break

            user_streak, freeze_used = update_streak_on_submission(
                session, parse_result.user_id, parse_result.game_id, parse_result.date
            )
            check_and_award_achievements(
                session,
                parse_result.user_id,
                parse_result.game_id,
                parse_result.date,
                user_streak,
                submission,
                freeze_used,
                enabled_count,
            )

            result.recorded.append(
                BackfillRow(
                    username=username,
                    game_name=game.name,
                    date=parse_result.date,
                    base_score=parse_result.base_score,
                    status="recorded",
                    message_id=msg["id"],
                    reaction=parser.reaction,
                )
            )
            break

    return result
