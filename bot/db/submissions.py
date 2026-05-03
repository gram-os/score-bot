from dataclasses import dataclass, field
from datetime import datetime, date, timezone

from sqlalchemy import delete, distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bot.db.config import SCORING_TZ
from bot.db.models import MonthlyRankSnapshot, Submission, User, UserAchievement, UserStreak
from bot.scoring import assign_submission_rank


def upsert_user(session: Session, user_id: str, username: str) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = session.get(User, user_id)
    if user is None:
        session.add(User(user_id=user_id, username=username, updated_at=now))
    else:
        user.username = username
        user.updated_at = now
    session.flush()


def is_duplicate(session: Session, user_id: str, game_id: str, submission_date: date) -> bool:
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


def record_submission(session: Session, parse_result, username: str) -> "Submission | None":
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
        message_text=parse_result.message_text,
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
) -> Submission:
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


def bulk_delete_submissions(session: Session, game_id: str, submission_date: date) -> int:
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


def recalculate_game_ranks(
    session: Session,
    game_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    stmt = select(Submission.date).where(Submission.game_id == game_id)
    if start_date is not None:
        stmt = stmt.where(Submission.date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Submission.date <= end_date)
    dates = session.scalars(stmt.distinct()).all()
    for d in dates:
        assign_submission_rank(session, game_id, d)
    return len(dates)


@dataclass
class RedateResult:
    fixed: int = 0
    skipped: int = 0
    skipped_details: list[str] = field(default_factory=list)


def redate_submissions(session: Session) -> RedateResult:
    result = RedateResult()
    all_subs = session.scalars(select(Submission)).all()
    affected_game_dates: set[tuple[str, date]] = set()

    for sub in all_subs:
        eastern_date = sub.submitted_at.replace(tzinfo=timezone.utc).astimezone(SCORING_TZ).date()
        if eastern_date == sub.date:
            continue

        conflict = session.scalar(
            select(func.count())
            .select_from(Submission)
            .where(
                Submission.user_id == sub.user_id,
                Submission.game_id == sub.game_id,
                Submission.date == eastern_date,
                Submission.id != sub.id,
            )
        )
        if conflict:
            result.skipped += 1
            result.skipped_details.append(f"{sub.username} / {sub.game_id}: {sub.date} → {eastern_date} (conflict)")
            continue

        affected_game_dates.add((sub.game_id, sub.date))
        affected_game_dates.add((sub.game_id, eastern_date))
        sub.date = eastern_date
        result.fixed += 1

    session.flush()
    for game_id, d in affected_game_dates:
        assign_submission_rank(session, game_id, d)

    return result


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


@dataclass
class ResetResult:
    submissions_deleted: int
    streaks_deleted: int
    achievements_deleted: int
    snapshots_deleted: int


def reset_all_submissions(session: Session) -> ResetResult:
    snapshots = session.scalar(select(func.count()).select_from(MonthlyRankSnapshot)) or 0
    achievements = session.scalar(select(func.count()).select_from(UserAchievement)) or 0
    streaks = session.scalar(select(func.count()).select_from(UserStreak)) or 0
    submissions = session.scalar(select(func.count()).select_from(Submission)) or 0

    session.execute(delete(MonthlyRankSnapshot))
    session.execute(delete(UserAchievement))
    session.execute(delete(UserStreak))
    session.execute(delete(Submission))
    session.flush()

    return ResetResult(
        submissions_deleted=submissions,
        streaks_deleted=streaks,
        achievements_deleted=achievements,
        snapshots_deleted=snapshots,
    )
