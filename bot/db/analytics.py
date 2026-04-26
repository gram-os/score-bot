import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from bot.db.models import Game, Submission, UserStreak


def _today() -> date:
    return datetime.now(timezone.utc).date()


# ---------------------------------------------------------------------------
# Stats dashboard
# ---------------------------------------------------------------------------

@dataclass
class KpiToday:
    total_submissions: int
    active_players: int
    most_popular_game: str | None
    games_with_zero: list[str]


def get_kpi_today(session: Session) -> KpiToday:
    today = _today()
    week_start = today - timedelta(days=today.weekday())

    total_submissions = session.scalar(
        select(func.count(Submission.id)).where(Submission.date == today)
    ) or 0

    active_players = session.scalar(
        select(func.count(distinct(Submission.user_id))).where(Submission.date == today)
    ) or 0

    popular_row = session.execute(
        select(Game.name, func.count(Submission.id).label("cnt"))
        .join(Submission, Submission.game_id == Game.id)
        .where(Submission.date >= week_start)
        .group_by(Game.id, Game.name)
        .order_by(func.count(Submission.id).desc())
        .limit(1)
    ).first()
    most_popular_game = popular_row.name if popular_row else None

    all_enabled = {
        row.id: row.name
        for row in session.execute(
            select(Game.id, Game.name).where(Game.enabled.is_(True))
        ).all()
    }
    submitted_today = {
        row.game_id
        for row in session.execute(
            select(Submission.game_id).where(Submission.date == today).distinct()
        ).all()
    }
    games_with_zero = [
        name for gid, name in sorted(all_enabled.items()) if gid not in submitted_today
    ]

    return KpiToday(
        total_submissions=total_submissions,
        active_players=active_players,
        most_popular_game=most_popular_game,
        games_with_zero=games_with_zero,
    )


@dataclass
class GameDifficultyRow:
    game_id: str
    game_name: str
    avg_base_score: float
    submission_count: int


def get_game_difficulty_comparison(session: Session) -> list[GameDifficultyRow]:
    rows = session.execute(
        select(
            Submission.game_id,
            Game.name.label("game_name"),
            func.avg(Submission.base_score).label("avg_base_score"),
            func.count(Submission.id).label("cnt"),
        )
        .join(Game, Submission.game_id == Game.id)
        .group_by(Submission.game_id, Game.name)
        .order_by(func.avg(Submission.base_score).asc())
    ).all()
    return [
        GameDifficultyRow(
            game_id=row.game_id,
            game_name=row.game_name,
            avg_base_score=round(row.avg_base_score, 1),
            submission_count=row.cnt,
        )
        for row in rows
    ]


@dataclass
class SpeedBonusLeader:
    username: str
    speed_bonus_count: int
    total_bonus_points: int


def get_speed_bonus_leaders(session: Session, limit: int = 5) -> list[SpeedBonusLeader]:
    rows = session.execute(
        select(
            Submission.username,
            func.count(Submission.id).label("cnt"),
            func.sum(Submission.speed_bonus).label("total"),
        )
        .where(Submission.speed_bonus > 0)
        .group_by(Submission.user_id, Submission.username)
        .order_by(func.count(Submission.id).desc())
        .limit(limit)
    ).all()
    return [
        SpeedBonusLeader(
            username=row.username,
            speed_bonus_count=row.cnt,
            total_bonus_points=int(row.total),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Game detail
# ---------------------------------------------------------------------------

@dataclass
class GameDifficultyMetrics:
    avg_base_score: float
    stddev_base_score: float
    fail_rate: float
    perfect_rate: float
    median_score: float
    total_submissions: int


def get_game_difficulty_metrics(session: Session, game_id: str) -> GameDifficultyMetrics | None:
    scores = [
        row.base_score
        for row in session.execute(
            select(Submission.base_score).where(Submission.game_id == game_id)
        ).all()
    ]
    if not scores:
        return None
    n = len(scores)
    avg = sum(scores) / n
    stddev = statistics.stdev(scores) if n > 1 else 0.0
    fail_rate = sum(1 for s in scores if s == 0) / n
    perfect_rate = sum(1 for s in scores if s >= 100) / n
    median = statistics.median(scores)
    return GameDifficultyMetrics(
        avg_base_score=round(avg, 1),
        stddev_base_score=round(stddev, 1),
        fail_rate=round(fail_rate, 4),
        perfect_rate=round(perfect_rate, 4),
        median_score=round(median, 1),
        total_submissions=n,
    )


@dataclass
class ScoreBucket:
    label: str
    count: int


def get_score_distribution(session: Session, game_id: str) -> list[ScoreBucket]:
    scores = [
        row.base_score
        for row in session.execute(
            select(Submission.base_score).where(Submission.game_id == game_id)
        ).all()
    ]
    buckets = [
        ("0–20", 0),
        ("20–40", 0),
        ("40–60", 0),
        ("60–80", 0),
        ("80–100", 0),
        ("100+", 0),
    ]
    counts = [0] * 6
    for s in scores:
        if s < 20:
            counts[0] += 1
        elif s < 40:
            counts[1] += 1
        elif s < 60:
            counts[2] += 1
        elif s < 80:
            counts[3] += 1
        elif s <= 100:
            counts[4] += 1
        else:
            counts[5] += 1
    return [ScoreBucket(label=label, count=counts[i]) for i, (label, _) in enumerate(buckets)]


@dataclass
class ScoreTimePoint:
    date: str
    avg_base_score: float
    submission_count: int


def get_avg_score_over_time(session: Session, game_id: str, days: int = 60) -> list[ScoreTimePoint]:
    cutoff = _today() - timedelta(days=days)
    rows = session.execute(
        select(
            Submission.date,
            func.avg(Submission.base_score).label("avg_score"),
            func.count(Submission.id).label("cnt"),
        )
        .where(Submission.game_id == game_id, Submission.date >= cutoff)
        .group_by(Submission.date)
        .order_by(Submission.date.asc())
    ).all()
    return [
        ScoreTimePoint(
            date=str(row.date),
            avg_base_score=round(row.avg_score, 1),
            submission_count=row.cnt,
        )
        for row in rows
    ]


def get_game_raw_data_breakdown(session: Session, game_id: str) -> dict:
    raw_datas = [
        row.raw_data
        for row in session.execute(
            select(Submission.raw_data).where(Submission.game_id == game_id)
        ).all()
        if row.raw_data
    ]
    if not raw_datas:
        return {}

    if game_id == "wordle":
        attempts: dict = {}
        hard_mode: dict = {True: 0, False: 0}
        for rd in raw_datas:
            a = rd.get("attempts")
            if a is not None:
                attempts[a] = attempts.get(a, 0) + 1
            hm = rd.get("hard_mode", False)
            hard_mode[bool(hm)] = hard_mode[bool(hm)] + 1
        return {"attempts": attempts, "hard_mode": hard_mode}

    if game_id == "connections":
        misses: dict = {"0": 0, "1": 0, "2": 0, "3+": 0}
        for rd in raw_datas:
            m = rd.get("misses", 0)
            key = str(m) if m < 3 else "3+"
            misses[key] = misses.get(key, 0) + 1
        return {"misses": misses}

    if game_id == "glyph":
        attempts = {}
        for rd in raw_datas:
            a = rd.get("attempts")
            if a is not None:
                attempts[a] = attempts.get(a, 0) + 1
        return {"attempts": attempts}

    if game_id == "betweenle":
        buckets = {"1–2": 0, "3–4": 0, "5–6": 0, "7–8": 0, "9–10": 0, "11–14": 0}
        for rd in raw_datas:
            g = rd.get("total_guesses")
            if g is None:
                continue
            if g <= 2:
                buckets["1–2"] += 1
            elif g <= 4:
                buckets["3–4"] += 1
            elif g <= 6:
                buckets["5–6"] += 1
            elif g <= 8:
                buckets["7–8"] += 1
            elif g <= 10:
                buckets["9–10"] += 1
            else:
                buckets["11–14"] += 1
        return {"total_guesses": buckets}

    if game_id == "mini_crossword":
        sec_buckets = {"<30s": 0, "30–60s": 0, "60–120s": 0, ">120s": 0}
        for rd in raw_datas:
            s = rd.get("total_seconds")
            if s is None:
                continue
            if s < 30:
                sec_buckets["<30s"] += 1
            elif s < 60:
                sec_buckets["30–60s"] += 1
            elif s < 120:
                sec_buckets["60–120s"] += 1
            else:
                sec_buckets[">120s"] += 1
        return {"seconds_buckets": sec_buckets}

    if game_id == "quordle":
        failed = {True: 0, False: 0}
        for rd in raw_datas:
            f = bool(rd.get("failed", False))
            failed[f] = failed[f] + 1
        return {"failed": failed}

    return {}


@dataclass
class GameSpeedBonusStats:
    total_submissions: int
    speed_bonus_count: int
    speed_bonus_pct: float
    rank1_count: int
    rank2_count: int
    rank3_count: int


def get_game_speed_bonus_stats(session: Session, game_id: str) -> GameSpeedBonusStats:
    rows = session.execute(
        select(
            Submission.submission_rank,
            func.count(Submission.id).label("cnt"),
        )
        .where(Submission.game_id == game_id)
        .group_by(Submission.submission_rank)
    ).all()

    rank_counts: dict[int, int] = {row.submission_rank: row.cnt for row in rows}
    total = sum(rank_counts.values())
    rank1 = rank_counts.get(1, 0)
    rank2 = rank_counts.get(2, 0)
    rank3 = rank_counts.get(3, 0)
    bonus_count = rank1 + rank2 + rank3
    pct = round(bonus_count / total, 4) if total > 0 else 0.0

    return GameSpeedBonusStats(
        total_submissions=total,
        speed_bonus_count=bonus_count,
        speed_bonus_pct=pct,
        rank1_count=rank1,
        rank2_count=rank2,
        rank3_count=rank3,
    )


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

@dataclass
class UserScorePoint:
    date: str
    game_id: str
    total_score: float


def get_user_score_history(
    session: Session, user_id: str, game_id: str | None = None
) -> list[UserScorePoint]:
    stmt = (
        select(Submission.date, Submission.game_id, Submission.total_score)
        .where(Submission.user_id == user_id)
        .order_by(Submission.date.asc())
    )
    if game_id is not None:
        stmt = stmt.where(Submission.game_id == game_id)
    rows = session.execute(stmt).all()
    return [
        UserScorePoint(date=str(row.date), game_id=row.game_id, total_score=row.total_score)
        for row in rows
    ]


def get_user_submission_dates(session: Session, user_id: str) -> list[str]:
    rows = session.execute(
        select(Submission.date)
        .where(Submission.user_id == user_id)
        .distinct()
        .order_by(Submission.date.asc())
    ).all()
    return [str(row.date) for row in rows]


@dataclass
class UserGameRow:
    game_id: str
    avg_score: float
    best_score: float
    submission_count: int
    current_streak: int
    longest_streak: int


def get_user_per_game_stats(session: Session, user_id: str) -> list[UserGameRow]:
    score_rows = session.execute(
        select(
            Submission.game_id,
            func.avg(Submission.total_score).label("avg_score"),
            func.max(Submission.total_score).label("best_score"),
            func.count(Submission.id).label("cnt"),
        )
        .where(Submission.user_id == user_id)
        .group_by(Submission.game_id)
        .order_by(Submission.game_id.asc())
    ).all()

    streak_rows = session.execute(
        select(UserStreak).where(UserStreak.user_id == user_id)
    ).scalars().all()

    today = _today()
    streak_map = {
        r.game_id: (
            r.current_streak if r.last_submission_date and (today - r.last_submission_date).days <= 1 else 0,
            r.longest_streak,
        )
        for r in streak_rows
    }

    return [
        UserGameRow(
            game_id=row.game_id,
            avg_score=round(row.avg_score, 1),
            best_score=row.best_score,
            submission_count=row.cnt,
            current_streak=streak_map.get(row.game_id, (0, 0))[0],
            longest_streak=streak_map.get(row.game_id, (0, 0))[1],
        )
        for row in score_rows
    ]


def get_users_for_h2h(session: Session, exclude_user_id: str) -> list[dict]:
    rows = session.execute(
        select(Submission.user_id, Submission.username)
        .where(Submission.user_id != exclude_user_id)
        .distinct()
        .order_by(Submission.username.asc())
    ).all()
    return [{"user_id": row.user_id, "username": row.username} for row in rows]
