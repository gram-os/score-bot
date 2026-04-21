import os
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from typing import Literal

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
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session
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


def get_engine(db_path: str | None = None):
    path = db_path or os.environ.get("DATABASE_PATH", "/data/scores.db")
    return create_engine(f"sqlite:///{path}")


# ---------------------------------------------------------------------------
# Submission operations
# ---------------------------------------------------------------------------

def is_duplicate(session: Session, user_id: str, game_id: str, submission_date: date) -> bool:
    return session.scalar(
        select(func.count()).select_from(Submission).where(
            Submission.user_id == user_id,
            Submission.game_id == game_id,
            Submission.date == submission_date,
        )
    ) > 0


def record_submission(session: Session, parse_result, username: str) -> "Submission | None":
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


def _period_bounds(period: Literal["daily", "weekly", "monthly", "alltime"]) -> tuple[date | None, date | None]:
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
