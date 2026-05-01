import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from bot.db.models import (
    Game,
    MonthlyRankSnapshot,
    Submission,
    User,
    UserAchievement,
    UsageEvent,
)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return first, last


def prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


@dataclass
class MonthlyGameStat:
    game_id: str
    game_name: str
    submissions: int
    avg_base_score: float
    best_score: float
    score_delta: float | None  # vs prior month avg, None if no prior data


@dataclass
class MonthlyWrapped:
    year: int
    month: int
    username: str
    total_submissions: int
    total_points: float
    active_days: int
    days_in_month: int
    favorite_game_name: str | None
    best_score: float | None
    best_score_game: str | None
    best_score_date: date | None
    avg_score: float | None
    score_delta_pct: float | None  # overall avg % change vs prior period
    speed_bonuses: int
    rank: int | None
    player_count: int | None
    new_games: list[str]
    pbs_set: int
    achievements_earned: int
    peak_hour: int | None
    label: str = ""  # display label for embed title (e.g. "April 2026" or "Beta")
    game_stats: list[MonthlyGameStat] = field(default_factory=list)


@dataclass
class SnapshotBackfillResult:
    records_created: int
    months_processed: int
    months_skipped: int


def _fetch_month_subs(session: Session, user_id: str, first: date, last: date):
    return session.execute(
        select(
            Submission.game_id,
            Submission.date,
            Submission.base_score,
            Submission.total_score,
            Submission.speed_bonus,
            Submission.submitted_at,
            Game.name.label("game_name"),
        )
        .join(Game, Submission.game_id == Game.id)
        .where(Submission.user_id == user_id, Submission.date >= first, Submission.date <= last)
    ).all()


def _favorite_game_name(subs) -> str | None:
    if not subs:
        return None
    counts: dict[str, tuple[str, int]] = {}
    for s in subs:
        prev_entry = counts.get(s.game_id, (s.game_name, 0))
        counts[s.game_id] = (prev_entry[0], prev_entry[1] + 1)
    best_id = max(counts, key=lambda k: counts[k][1])
    return counts[best_id][0]


def _peak_hour(subs) -> int | None:
    hours = [s.submitted_at.hour for s in subs if s.submitted_at]
    if not hours:
        return None
    return max(set(hours), key=hours.count)


def _count_pbs_set(session: Session, user_id: str, subs, first: date) -> int:
    count = 0
    for game_id in {s.game_id for s in subs}:
        month_best = max(s.base_score for s in subs if s.game_id == game_id)
        prior_best = session.scalar(
            select(func.max(Submission.base_score)).where(
                Submission.user_id == user_id,
                Submission.game_id == game_id,
                Submission.date < first,
            )
        )
        if prior_best is None or month_best > prior_best:
            count += 1
    return count


def _new_games_this_month(
    session: Session, user_id: str, subs, first: date, last: date
) -> list[str]:
    game_ids = {s.game_id for s in subs}
    if not game_ids:
        return []
    rows = session.execute(
        select(
            Submission.game_id,
            Game.name.label("game_name"),
            func.min(Submission.date).label("first_date"),
        )
        .join(Game, Submission.game_id == Game.id)
        .where(Submission.user_id == user_id, Submission.game_id.in_(game_ids))
        .group_by(Submission.game_id)
    ).all()
    return [row.game_name for row in rows if first <= row.first_date <= last]


def _achievements_in_range(
    session: Session, user_id: str, start_dt: datetime, end_dt: datetime
) -> int:
    return (
        session.scalar(
            select(func.count(UserAchievement.id)).where(
                UserAchievement.user_id == user_id,
                UserAchievement.earned_at >= start_dt,
                UserAchievement.earned_at <= end_dt,
            )
        )
        or 0
    )


def _achievements_in_month(
    session: Session, user_id: str, year: int, month: int, days_in_month: int
) -> int:
    start_dt = datetime(year, month, 1)
    end_dt = datetime(year, month, days_in_month, 23, 59, 59)
    return _achievements_in_range(session, user_id, start_dt, end_dt)


def _build_game_stats(
    session: Session, user_id: str, subs, prev_first: date | None, prev_last: date | None
) -> list[MonthlyGameStat]:
    result = []
    for game_id in {s.game_id for s in subs}:
        game_subs = [s for s in subs if s.game_id == game_id]
        avg = sum(s.base_score for s in game_subs) / len(game_subs)
        best = max(s.base_score for s in game_subs)
        name = game_subs[0].game_name

        prev = (
            session.execute(
                select(Submission.base_score).where(
                    Submission.user_id == user_id,
                    Submission.game_id == game_id,
                    Submission.date >= prev_first,
                    Submission.date <= prev_last,
                )
            ).scalars().all()
            if prev_first and prev_last
            else []
        )
        prev_avg = sum(prev) / len(prev) if prev else None
        delta = round(avg - prev_avg, 1) if prev_avg is not None else None

        result.append(
            MonthlyGameStat(
                game_id=game_id,
                game_name=name,
                submissions=len(game_subs),
                avg_base_score=round(avg, 1),
                best_score=best,
                score_delta=delta,
            )
        )
    return sorted(result, key=lambda g: g.submissions, reverse=True)


def _get_rank_snapshot(
    session: Session, user_id: str, year: int, month: int
) -> MonthlyRankSnapshot | None:
    return session.execute(
        select(MonthlyRankSnapshot).where(
            MonthlyRankSnapshot.user_id == user_id,
            MonthlyRankSnapshot.year == year,
            MonthlyRankSnapshot.month == month,
        )
    ).scalar_one_or_none()


def get_monthly_wrapped(
    session: Session, user_id: str, year: int, month: int
) -> MonthlyWrapped | None:
    first, last = month_bounds(year, month)
    subs = _fetch_month_subs(session, user_id, first, last)
    if not subs:
        return None

    days_in_month = calendar.monthrange(year, month)[1]
    py, pm = prev_month(year, month)
    pf, pl = month_bounds(py, pm)

    avg_score = sum(s.base_score for s in subs) / len(subs)
    prev_all = session.execute(
        select(Submission.base_score).where(
            Submission.user_id == user_id, Submission.date >= pf, Submission.date <= pl
        )
    ).scalars().all()
    prev_avg = sum(prev_all) / len(prev_all) if prev_all else None
    score_delta_pct = (
        round((avg_score - prev_avg) / prev_avg * 100, 1) if prev_avg else None
    )

    best_sub = max(subs, key=lambda s: s.total_score)
    snap = _get_rank_snapshot(session, user_id, year, month)
    user = session.get(User, user_id)
    month_name = calendar.month_name[month]

    return MonthlyWrapped(
        year=year,
        month=month,
        label=f"{month_name} {year}",
        username=user.username if user else "Unknown",
        total_submissions=len(subs),
        total_points=sum(s.total_score for s in subs),
        active_days=len({s.date for s in subs}),
        days_in_month=days_in_month,
        favorite_game_name=_favorite_game_name(subs),
        best_score=best_sub.total_score,
        best_score_game=best_sub.game_name,
        best_score_date=best_sub.date,
        avg_score=round(avg_score, 1),
        score_delta_pct=score_delta_pct,
        speed_bonuses=sum(1 for s in subs if s.speed_bonus > 0),
        rank=snap.rank if snap else None,
        player_count=snap.player_count if snap else None,
        new_games=_new_games_this_month(session, user_id, subs, first, last),
        pbs_set=_count_pbs_set(session, user_id, subs, first),
        achievements_earned=_achievements_in_month(session, user_id, year, month, days_in_month),
        peak_hour=_peak_hour(subs),
        game_stats=_build_game_stats(session, user_id, subs, pf, pl),
    )


def get_monthly_active_user_ids(session: Session, year: int, month: int) -> list[str]:
    first, last = month_bounds(year, month)
    return session.execute(
        select(distinct(Submission.user_id)).where(
            Submission.date >= first, Submission.date <= last
        )
    ).scalars().all()


def snapshot_month(session: Session, year: int, month: int) -> int:
    """Insert rank snapshots for all active users in the given month.

    Idempotent — skips the month if snapshots already exist.
    Returns the number of snapshot records inserted.
    """
    existing = session.scalar(
        select(func.count()).select_from(MonthlyRankSnapshot).where(
            MonthlyRankSnapshot.year == year, MonthlyRankSnapshot.month == month
        )
    )
    if existing:
        return 0

    first, last = month_bounds(year, month)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    rows = session.execute(
        select(
            Submission.user_id,
            Submission.username,
            func.sum(Submission.total_score).label("total"),
            func.count(Submission.id).label("cnt"),
        )
        .where(Submission.date >= first, Submission.date <= last)
        .group_by(Submission.user_id, Submission.username)
        .order_by(func.sum(Submission.total_score).desc())
    ).all()

    player_count = len(rows)
    for rank, row in enumerate(rows, start=1):
        session.add(
            MonthlyRankSnapshot(
                user_id=row.user_id,
                username=row.username,
                year=year,
                month=month,
                rank=rank,
                total_score=row.total,
                submission_count=row.cnt,
                player_count=player_count,
                snapshotted_at=now,
            )
        )
    session.flush()
    return player_count


def backfill_monthly_rank_snapshots(session: Session) -> SnapshotBackfillResult:
    """Create rank snapshots for all completed months found in the submissions table.

    Idempotent — months that already have snapshots are skipped.
    The current in-progress month is excluded.
    """
    all_dates = session.scalars(select(distinct(Submission.date))).all()
    months = sorted({(d.year, d.month) for d in all_dates})

    today = date.today()
    records_created = 0
    months_processed = 0
    months_skipped = 0

    for year, month in months:
        if year == today.year and month == today.month:
            continue
        created = snapshot_month(session, year, month)
        if created:
            records_created += created
            months_processed += 1
        else:
            months_skipped += 1

    return SnapshotBackfillResult(
        records_created=records_created,
        months_processed=months_processed,
        months_skipped=months_skipped,
    )


def monthly_report_already_sent(
    session: Session, user_id: str, year: int, month: int
) -> bool:
    events = session.execute(
        select(UsageEvent.event_data).where(
            UsageEvent.event_type == "monthly_report.sent",
            UsageEvent.user_id == user_id,
        )
    ).scalars().all()
    return any(
        e is not None and e.get("year") == year and e.get("month") == month
        for e in events
    )


def season_report_already_sent(session: Session, user_id: str, season_id: int) -> bool:
    events = session.execute(
        select(UsageEvent.event_data).where(
            UsageEvent.event_type == "season_report.sent",
            UsageEvent.user_id == user_id,
        )
    ).scalars().all()
    return any(e is not None and e.get("season_id") == season_id for e in events)


def get_season_active_user_ids(
    session: Session, start_date: date, end_date: date
) -> list[str]:
    return session.execute(
        select(distinct(Submission.user_id)).where(
            Submission.date >= start_date, Submission.date <= end_date
        )
    ).scalars().all()


def _get_season_rank(
    session: Session, user_id: str, start_date: date, end_date: date
) -> tuple[int | None, int | None]:
    rows = session.execute(
        select(Submission.user_id, func.sum(Submission.total_score).label("total"))
        .where(Submission.date >= start_date, Submission.date <= end_date)
        .group_by(Submission.user_id)
        .order_by(func.sum(Submission.total_score).desc())
    ).all()
    player_count = len(rows)
    for rank, row in enumerate(rows, start=1):
        if row.user_id == user_id:
            return rank, player_count
    return None, None


def get_season_wrapped(
    session: Session,
    user_id: str,
    season_id: int,
    season_name: str,
    start_date: date,
    end_date: date,
    prev_start: date | None,
    prev_end: date | None,
) -> MonthlyWrapped | None:
    subs = _fetch_month_subs(session, user_id, start_date, end_date)
    if not subs:
        return None

    total_days = (end_date - start_date).days + 1
    avg_score = sum(s.base_score for s in subs) / len(subs)

    prev_all = (
        session.execute(
            select(Submission.base_score).where(
                Submission.user_id == user_id,
                Submission.date >= prev_start,
                Submission.date <= prev_end,
            )
        ).scalars().all()
        if prev_start and prev_end
        else []
    )
    prev_avg = sum(prev_all) / len(prev_all) if prev_all else None
    score_delta_pct = round((avg_score - prev_avg) / prev_avg * 100, 1) if prev_avg else None

    best_sub = max(subs, key=lambda s: s.total_score)
    rank, player_count = _get_season_rank(session, user_id, start_date, end_date)
    user = session.get(User, user_id)
    start_dt = datetime(start_date.year, start_date.month, start_date.day)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)

    return MonthlyWrapped(
        year=end_date.year,
        month=end_date.month,
        label=season_name,
        username=user.username if user else "Unknown",
        total_submissions=len(subs),
        total_points=sum(s.total_score for s in subs),
        active_days=len({s.date for s in subs}),
        days_in_month=total_days,
        favorite_game_name=_favorite_game_name(subs),
        best_score=best_sub.total_score,
        best_score_game=best_sub.game_name,
        best_score_date=best_sub.date,
        avg_score=round(avg_score, 1),
        score_delta_pct=score_delta_pct,
        speed_bonuses=sum(1 for s in subs if s.speed_bonus > 0),
        rank=rank,
        player_count=player_count,
        new_games=_new_games_this_month(session, user_id, subs, start_date, end_date),
        pbs_set=_count_pbs_set(session, user_id, subs, start_date),
        achievements_earned=_achievements_in_range(session, user_id, start_dt, end_dt),
        peak_hour=_peak_hour(subs),
        game_stats=_build_game_stats(session, user_id, subs, prev_start, prev_end),
    )
