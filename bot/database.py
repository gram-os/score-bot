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
    distinct,
    func,
    select,
    update,
    and_,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    selectinload,
    Session,
    aliased,
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


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    remind_streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


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


class UserStreak(Base):
    __tablename__ = "user_streaks"
    __table_args__ = (UniqueConstraint("user_id", "game_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    game_id: Mapped[str] = mapped_column(String, ForeignKey("games.id"), nullable=False)
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    freeze_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    achievement_slug: Mapped[str] = mapped_column(String, nullable=False)
    earned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AppLog(Base):
    __tablename__ = "app_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    level: Mapped[str] = mapped_column(String, nullable=False)
    logger: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)


def get_engine(db_path: str | None = None):
    path = db_path or os.environ.get("DATABASE_PATH", "/data/scores.db")
    return create_engine(f"sqlite:///{path}")


# ---------------------------------------------------------------------------
# Submission operations
# ---------------------------------------------------------------------------


def upsert_user(session: Session, user_id: str, username: str) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = session.get(User, user_id)
    if user is None:
        session.add(User(user_id=user_id, username=username, updated_at=now))
    else:
        user.username = username
        user.updated_at = now
    session.flush()


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

    upsert_user(session, parse_result.user_id, username)
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

    upsert_user(session, user_id, username)
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


def bulk_delete_submissions(
    session: Session, game_id: str, submission_date: date
) -> int:
    submissions = session.scalars(
        select(Submission).where(
            Submission.game_id == game_id,
            Submission.date == submission_date,
        )
    ).all()
    count = len(submissions)
    for sub in submissions:
        session.delete(sub)
    session.flush()
    return count


def recalculate_game_ranks(session: Session, game_id: str) -> int:
    from bot.scoring import assign_submission_rank

    dates = session.scalars(
        select(Submission.date).where(Submission.game_id == game_id).distinct()
    ).all()
    for d in dates:
        assign_submission_rank(session, game_id, d)
    return len(dates)


@dataclass
class UserSummary:
    user_id: str
    username: str
    total_score: float
    submission_count: int
    game_count: int
    last_date: date | None


def get_users_summary(session: Session) -> list[UserSummary]:
    rows = session.execute(
        select(
            Submission.user_id,
            User.username,
            func.sum(Submission.total_score).label("total_score"),
            func.count(Submission.id).label("submission_count"),
            func.count(distinct(Submission.game_id)).label("game_count"),
            func.max(Submission.date).label("last_date"),
        )
        .join(User, Submission.user_id == User.user_id)
        .group_by(Submission.user_id)
        .order_by(func.sum(Submission.total_score).desc())
    ).all()
    return [
        UserSummary(
            user_id=row.user_id,
            username=row.username,
            total_score=row.total_score,
            submission_count=row.submission_count,
            game_count=row.game_count,
            last_date=row.last_date,
        )
        for row in rows
    ]


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
    period: Literal["daily", "weekly", "monthly", "alltime", "season"],
    game_id: str | None = None,
) -> list[LeaderboardRow]:
    if period == "season":
        season = get_current_season(session)
        start = season.start_date if season else None
        end = season.end_date if season else None
    else:
        start, end = _period_bounds(period)

    stmt = (
        select(
            Submission.user_id,
            User.username,
            func.sum(Submission.total_score).label("total_score"),
            func.count(Submission.id).label("submission_count"),
        )
        .join(User, Submission.user_id == User.user_id)
        .group_by(Submission.user_id)
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
# Streak queries
# ---------------------------------------------------------------------------

MAX_FREEZES = 3


def _is_streak_active(row: "UserStreak") -> bool:
    """A streak is active if the user submitted today or yesterday."""
    if row.last_submission_date is None:
        return False
    today = datetime.now(timezone.utc).date()
    return (today - row.last_submission_date).days <= 1


def get_streak(session: Session, user_id: str, game_id: str) -> int:
    row = session.scalar(
        select(UserStreak).where(
            UserStreak.user_id == user_id,
            UserStreak.game_id == game_id,
        )
    )
    if row is None:
        return 0
    return row.current_streak if _is_streak_active(row) else 0


def get_user_streak(
    session: Session, user_id: str, game_id: str
) -> "UserStreak | None":
    return session.scalar(
        select(UserStreak).where(
            UserStreak.user_id == user_id,
            UserStreak.game_id == game_id,
        )
    )


def get_all_streaks(session: Session, game_id: str) -> list[tuple[str, str, int]]:
    today = datetime.now(timezone.utc).date()
    rows = session.execute(
        select(
            UserStreak.user_id,
            User.username,
            UserStreak.current_streak,
            UserStreak.last_submission_date,
        )
        .join(User, UserStreak.user_id == User.user_id)
        .where(UserStreak.game_id == game_id)
    ).all()
    results = []
    for r in rows:
        days_since = (
            (today - r.last_submission_date).days if r.last_submission_date else 999
        )
        active = r.current_streak if days_since <= 1 else 0
        results.append((r.user_id, r.username, active))
    results.sort(key=lambda x: x[2], reverse=True)
    return results


def update_streak_on_submission(
    session: Session, user_id: str, game_id: str, submission_date: date
) -> tuple["UserStreak", bool]:
    """Update stored streak state for a new submission. Returns (streak, freeze_used)."""
    streak = session.scalar(
        select(UserStreak).where(
            UserStreak.user_id == user_id,
            UserStreak.game_id == game_id,
        )
    )
    freeze_used = False

    if streak is None:
        streak = UserStreak(
            user_id=user_id,
            game_id=game_id,
            current_streak=1,
            longest_streak=1,
            last_submission_date=submission_date,
            freeze_count=0,
        )
        session.add(streak)
        session.flush()
        return streak, False

    if streak.last_submission_date is None:
        streak.current_streak = 1
        streak.longest_streak = max(streak.longest_streak, 1)
        streak.last_submission_date = submission_date
        session.flush()
        return streak, False

    days_gap = (submission_date - streak.last_submission_date).days

    if days_gap <= 0:
        return streak, False
    elif days_gap == 1:
        streak.current_streak += 1
        if streak.current_streak % 7 == 0 and streak.freeze_count < MAX_FREEZES:
            streak.freeze_count += 1
    elif days_gap == 2:
        if streak.freeze_count > 0:
            streak.freeze_count -= 1
            streak.current_streak += 1
            freeze_used = True
        else:
            streak.current_streak = 1
    else:
        streak.current_streak = 1

    streak.longest_streak = max(streak.longest_streak, streak.current_streak)
    streak.last_submission_date = submission_date
    session.flush()
    return streak, freeze_used


@dataclass
class GameDigestData:
    game_id: str
    game_name: str
    winner_username: str | None
    winner_score: float
    participant_count: int
    top_streak: int


def get_yesterday_digest(session: Session) -> list["GameDigestData"]:
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    games = session.execute(select(Game).where(Game.enabled.is_(True))).scalars().all()

    results = []
    for game in games:
        subs = (
            session.execute(
                select(Submission)
                .where(Submission.game_id == game.id, Submission.date == yesterday)
                .order_by(Submission.total_score.desc())
            )
            .scalars()
            .all()
        )

        if not subs:
            results.append(
                GameDigestData(
                    game_id=game.id,
                    game_name=game.name,
                    winner_username=None,
                    winner_score=0.0,
                    participant_count=0,
                    top_streak=0,
                )
            )
            continue

        top_streak = max(get_streak(session, sub.user_id, game.id) for sub in subs)
        winner_user = session.get(User, subs[0].user_id)
        results.append(
            GameDigestData(
                game_id=game.id,
                game_name=game.name,
                winner_username=(
                    winner_user.username if winner_user else subs[0].username
                ),
                winner_score=subs[0].total_score,
                participant_count=len(subs),
                top_streak=top_streak,
            )
        )

    return results


@dataclass
class WeeklyDigestData:
    week_start: date
    week_end: date
    top_scorer_username: str | None
    top_scorer_points: float
    most_active_username: str | None
    most_active_submissions: int
    best_single_score: float
    best_single_username: str | None
    best_single_game: str | None
    top_streak_username: str | None
    top_streak_days: int
    total_submissions: int
    unique_players: int


def get_weekly_digest(session: Session) -> "WeeklyDigestData":
    today = datetime.now(timezone.utc).date()
    # Previous Mon–Sun
    week_end = today - timedelta(days=today.weekday() + 1)
    week_start = week_end - timedelta(days=6)

    # Top scorer
    scorer_row = session.execute(
        select(User.username, func.sum(Submission.total_score).label("pts"))
        .join(User, Submission.user_id == User.user_id)
        .where(Submission.date >= week_start, Submission.date <= week_end)
        .group_by(Submission.user_id)
        .order_by(func.sum(Submission.total_score).desc())
        .limit(1)
    ).first()

    # Most active
    active_row = session.execute(
        select(User.username, func.count(Submission.id).label("cnt"))
        .join(User, Submission.user_id == User.user_id)
        .where(Submission.date >= week_start, Submission.date <= week_end)
        .group_by(Submission.user_id)
        .order_by(func.count(Submission.id).desc())
        .limit(1)
    ).first()

    # Best single score
    best_sub = session.execute(
        select(Submission, User.username, Game.name.label("game_name"))
        .join(User, Submission.user_id == User.user_id)
        .join(Game, Submission.game_id == Game.id)
        .where(Submission.date >= week_start, Submission.date <= week_end)
        .order_by(Submission.total_score.desc())
        .limit(1)
    ).first()

    # Top streak (current streaks for all users)
    streak_row = session.execute(
        select(User.username, UserStreak.current_streak)
        .join(User, UserStreak.user_id == User.user_id)
        .order_by(UserStreak.current_streak.desc())
        .limit(1)
    ).first()

    total_subs = (
        session.scalar(
            select(func.count())
            .select_from(Submission)
            .where(Submission.date >= week_start, Submission.date <= week_end)
        )
        or 0
    )

    unique_players = (
        session.scalar(
            select(func.count(distinct(Submission.user_id))).where(
                Submission.date >= week_start, Submission.date <= week_end
            )
        )
        or 0
    )

    return WeeklyDigestData(
        week_start=week_start,
        week_end=week_end,
        top_scorer_username=scorer_row.username if scorer_row else None,
        top_scorer_points=scorer_row.pts if scorer_row else 0.0,
        most_active_username=active_row.username if active_row else None,
        most_active_submissions=active_row.cnt if active_row else 0,
        best_single_score=best_sub[0].total_score if best_sub else 0.0,
        best_single_username=best_sub.username if best_sub else None,
        best_single_game=best_sub.game_name if best_sub else None,
        top_streak_username=streak_row.username if streak_row else None,
        top_streak_days=streak_row.current_streak if streak_row else 0,
        total_submissions=total_subs,
        unique_players=unique_players,
    )


# ---------------------------------------------------------------------------
# Season queries
# ---------------------------------------------------------------------------


def get_current_season(session: Session) -> "Season | None":
    today = datetime.now(timezone.utc).date()
    return session.scalar(
        select(Season).where(and_(Season.start_date <= today, Season.end_date >= today))
    )


def get_season_ending_yesterday(session: Session) -> "Season | None":
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    return session.scalar(select(Season).where(Season.end_date == yesterday))


# ---------------------------------------------------------------------------
# Achievement queries
# ---------------------------------------------------------------------------


def get_user_achievements(session: Session, user_id: str) -> list["UserAchievement"]:
    return list(
        session.scalars(
            select(UserAchievement)
            .where(UserAchievement.user_id == user_id)
            .order_by(UserAchievement.earned_at)
        ).all()
    )


def award_season_champion(session: Session, user_id: str) -> bool:
    """Award season_champion achievement. Returns True if newly awarded."""
    from datetime import datetime, timezone

    existing = session.scalar(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_slug == "season_champion",
        )
    )
    if existing:
        return False
    session.add(
        UserAchievement(
            user_id=user_id,
            achievement_slug="season_champion",
            earned_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    session.flush()
    return True


# ---------------------------------------------------------------------------
# Personal bests queries
# ---------------------------------------------------------------------------


@dataclass
class PersonalBests:
    best_score: float
    best_date: date
    best_raw_data: dict
    avg_score: float
    count: int


def get_personal_bests(
    session: Session, user_id: str, game_id: str
) -> "PersonalBests | None":
    rows = (
        session.execute(
            select(Submission)
            .where(Submission.user_id == user_id, Submission.game_id == game_id)
            .order_by(Submission.total_score.desc())
        )
        .scalars()
        .all()
    )

    if not rows:
        return None

    best = rows[0]
    avg = sum(r.total_score for r in rows) / len(rows)
    return PersonalBests(
        best_score=best.total_score,
        best_date=best.date,
        best_raw_data=best.raw_data,
        avg_score=avg,
        count=len(rows),
    )


# ---------------------------------------------------------------------------
# Head-to-head queries
# ---------------------------------------------------------------------------


@dataclass
class HeadToHeadResult:
    caller_username: str
    opponent_username: str
    caller_total_score: float
    opponent_total_score: float
    caller_wins: int
    opponent_wins: int
    ties: int
    overlapping_days: int


def get_head_to_head(
    session: Session,
    caller_id: str,
    opponent_id: str,
    game_id: str | None = None,
) -> HeadToHeadResult | None:
    caller_sub = aliased(Submission, name="caller_sub")
    opponent_sub = aliased(Submission, name="opponent_sub")

    stmt = (
        select(caller_sub, opponent_sub)
        .join(
            opponent_sub,
            (caller_sub.date == opponent_sub.date)
            & (caller_sub.game_id == opponent_sub.game_id),
        )
        .where(
            caller_sub.user_id == caller_id,
            opponent_sub.user_id == opponent_id,
        )
    )
    if game_id is not None:
        stmt = stmt.where(caller_sub.game_id == game_id)

    rows = session.execute(stmt).all()
    if not rows:
        return None

    caller_user = session.get(User, caller_id)
    opponent_user = session.get(User, opponent_id)
    caller_username = caller_user.username if caller_user else rows[0][0].username
    opponent_username = opponent_user.username if opponent_user else rows[0][1].username
    caller_wins = caller_losses = ties = 0
    caller_total = opponent_total = 0.0

    for c_sub, o_sub in rows:
        caller_total += c_sub.total_score
        opponent_total += o_sub.total_score
        if c_sub.total_score > o_sub.total_score:
            caller_wins += 1
        elif o_sub.total_score > c_sub.total_score:
            caller_losses += 1
        else:
            ties += 1

    return HeadToHeadResult(
        caller_username=caller_username,
        opponent_username=opponent_username,
        caller_total_score=caller_total,
        opponent_total_score=opponent_total,
        caller_wins=caller_wins,
        opponent_wins=caller_losses,
        ties=ties,
        overlapping_days=len(rows),
    )


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


# ---------------------------------------------------------------------------
# User preference operations
# ---------------------------------------------------------------------------


def get_opted_in_preferences(session: Session) -> list["UserPreference"]:
    return list(
        session.execute(
            select(UserPreference).where(UserPreference.remind_streak_days > 0)
        ).scalars()
    )


def get_preference(session: Session, user_id: str) -> "UserPreference | None":
    return session.get(UserPreference, user_id)


def set_preference(
    session: Session, user_id: str, remind_streak_days: int
) -> "UserPreference":
    pref = session.get(UserPreference, user_id)
    if pref is None:
        pref = UserPreference(user_id=user_id, remind_streak_days=remind_streak_days)
        session.add(pref)
    else:
        pref.remind_streak_days = remind_streak_days
    session.flush()
    return pref


# ---------------------------------------------------------------------------
# Log queries
# ---------------------------------------------------------------------------


def get_logs(
    session: Session,
    level: str | None = None,
    logger_filter: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AppLog], int]:
    filters = []
    if level:
        filters.append(AppLog.level == level)
    if logger_filter:
        filters.append(AppLog.logger.ilike(f"%{logger_filter}%"))
    if search:
        filters.append(AppLog.message.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(AppLog)
    data_stmt = select(AppLog).order_by(AppLog.timestamp.desc())
    if filters:
        count_stmt = count_stmt.where(*filters)
        data_stmt = data_stmt.where(*filters)

    total = session.scalar(count_stmt) or 0
    rows = session.execute(data_stmt.offset(offset).limit(limit)).scalars().all()
    return rows, total
