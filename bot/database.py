import os
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from typing import Literal

from rapidfuzz import fuzz
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    func,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    selectinload,
    Session,
)
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    submissions: Mapped[list["Submission"]] = relationship(
        "Submission", back_populates="game"
    )


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("user_id", "game_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    game_id: Mapped[str] = mapped_column(String, ForeignKey("games.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    base_score: Mapped[float] = mapped_column(Float, nullable=False)
    speed_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    submission_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    game: Mapped["Game"] = relationship("Game", back_populates="submissions")


class DailyPoll(Base):
    __tablename__ = "daily_polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    message_id: Mapped[str] = mapped_column(String, nullable=False)
    is_yes_no: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    suggestions: Mapped[list["GameSuggestion"]] = relationship(
        "GameSuggestion", back_populates="poll"
    )


class GameSuggestion(Base):
    __tablename__ = "game_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    game_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    poll_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("daily_polls.id"), nullable=True
    )

    poll: Mapped["DailyPoll | None"] = relationship(
        "DailyPoll", back_populates="suggestions"
    )


def get_engine(db_path: str | None = None):
    path = db_path or os.environ.get("DATABASE_PATH", "/data/scores.db")
    return create_engine(f"sqlite:///{path}")


# ---------------------------------------------------------------------------
# Submission operations
# ---------------------------------------------------------------------------


def is_duplicate(
    session: Session, user_id: str, game_id: str, submission_date: date
) -> bool:
    return (
        session.scalar(
            select(func.count())
            .select_from(Submission)
            .where(
                Submission.user_id == user_id,
                Submission.game_id == game_id,
                Submission.date == submission_date,
            )
        )
        > 0
    )


def record_submission(
    session: Session, parse_result, username: str
) -> "Submission | None":
    from bot.scoring import assign_submission_rank

    submission = Submission(
        user_id=parse_result.user_id,
        username=username,
        game_id=parse_result.game_id,
        date=parse_result.date,
        base_score=parse_result.base_score,
        speed_bonus=0,
        total_score=parse_result.base_score,
        submission_rank=0,
        raw_data=parse_result.raw_data,
        submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(submission)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return None

    assign_submission_rank(session, parse_result.game_id, parse_result.date)
    return submission


def delete_submission(session: Session, submission_id: int) -> None:
    from bot.scoring import assign_submission_rank

    submission = session.get(Submission, submission_id)
    if submission is None:
        return

    game_id = submission.game_id
    submission_date = submission.date
    session.delete(submission)
    session.flush()
    assign_submission_rank(session, game_id, submission_date)


def add_submission_manual(
    session: Session,
    user_id: str,
    username: str,
    game_id: str,
    submission_date: date,
    base_score: float,
    raw_data: dict,
    submitted_at: datetime | None = None,
) -> "Submission":
    from bot.scoring import assign_submission_rank

    submission = Submission(
        user_id=user_id,
        username=username,
        game_id=game_id,
        date=submission_date,
        base_score=base_score,
        speed_bonus=0,
        total_score=base_score,
        submission_rank=0,
        raw_data=raw_data,
        submitted_at=submitted_at or datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(submission)
    session.flush()
    assign_submission_rank(session, game_id, submission_date)
    return submission


# ---------------------------------------------------------------------------
# Leaderboard queries
# ---------------------------------------------------------------------------


@dataclass
class LeaderboardRow:
    rank: int
    user_id: str
    username: str
    total_score: float
    submission_count: int


def _period_bounds(
    period: Literal["daily", "weekly", "monthly", "alltime"],
) -> tuple[date | None, date | None]:
    today = datetime.now(timezone.utc).date()
    if period == "daily":
        return today, today
    if period == "weekly":
        start = today - timedelta(days=today.weekday())  # Monday
        end = start + timedelta(days=6)
        return start, end
    if period == "monthly":
        start = today.replace(day=1)
        if today.month == 12:
            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return start, end
    return None, None  # alltime


def get_leaderboard(
    session: Session,
    period: Literal["daily", "weekly", "monthly", "alltime"],
    game_id: str | None = None,
) -> list[LeaderboardRow]:
    start, end = _period_bounds(period)

    stmt = (
        select(
            Submission.user_id,
            Submission.username,
            func.sum(Submission.total_score).label("total_score"),
            func.count(Submission.id).label("submission_count"),
        )
        .group_by(Submission.user_id, Submission.username)
        .order_by(func.sum(Submission.total_score).desc())
    )

    if game_id is not None:
        stmt = stmt.where(Submission.game_id == game_id)
    if start is not None:
        stmt = stmt.where(Submission.date >= start)
    if end is not None:
        stmt = stmt.where(Submission.date <= end)

    rows = session.execute(stmt).all()
    return [
        LeaderboardRow(
            rank=i + 1,
            user_id=row.user_id,
            username=row.username,
            total_score=row.total_score,
            submission_count=row.submission_count,
        )
        for i, row in enumerate(rows)
    ]


# ---------------------------------------------------------------------------
# Game suggestion operations
# ---------------------------------------------------------------------------

_FUZZY_THRESHOLD = 85


def find_similar_name(name: str, candidates: list[str]) -> str | None:
    """Return the first candidate with fuzzy similarity >= threshold, or None."""
    name_lower = name.lower()
    for candidate in candidates:
        if fuzz.ratio(name_lower, candidate.lower()) >= _FUZZY_THRESHOLD:
            return candidate
    return None


def add_suggestion(
    session: Session,
    user_id: str,
    username: str,
    game_name: str,
    description: str | None = None,
) -> GameSuggestion:
    suggestion = GameSuggestion(
        user_id=user_id,
        username=username,
        game_name=game_name,
        description=description,
        suggested_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(suggestion)
    session.flush()
    return suggestion


def get_unpolled_suggestions(session: Session) -> list[GameSuggestion]:
    return list(
        session.execute(
            select(GameSuggestion).where(GameSuggestion.poll_id.is_(None))
        ).scalars()
    )


def create_daily_poll(
    session: Session,
    message_id: str,
    is_yes_no: bool,
    suggestion_ids: list[int],
) -> DailyPoll:
    poll = DailyPoll(
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        message_id=message_id,
        is_yes_no=is_yes_no,
        notified=False,
    )
    session.add(poll)
    session.flush()
    session.execute(
        update(GameSuggestion)
        .where(GameSuggestion.id.in_(suggestion_ids))
        .values(poll_id=poll.id)
    )
    return poll


def get_latest_unnotified_poll(session: Session) -> DailyPoll | None:
    return session.scalar(
        select(DailyPoll)
        .options(selectinload(DailyPoll.suggestions))
        .where(DailyPoll.notified.is_(False))
        .order_by(DailyPoll.created_at.desc())
        .limit(1)
    )


def mark_poll_notified(session: Session, poll_id: int) -> None:
    poll = session.get(DailyPoll, poll_id)
    if poll:
        poll.notified = True
