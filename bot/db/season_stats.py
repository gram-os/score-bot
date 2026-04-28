from dataclasses import dataclass
from datetime import date

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from bot.db.models import Game, Season, Submission, User


@dataclass
class SeasonSummary:
    season: Season
    total_submissions: int
    unique_players: int
    total_points: float
    champion_username: str | None
    champion_points: float


@dataclass
class SeasonStats:
    total_submissions: int
    unique_players: int
    total_points: float
    games_active: int
    most_active_date: date | None
    most_active_date_count: int
    avg_daily_submissions: float


@dataclass
class SeasonPlayerRow:
    rank: int
    user_id: str
    username: str
    total_score: float
    submission_count: int
    games_played: int


@dataclass
class SeasonGameRow:
    game_id: str
    game_name: str
    submission_count: int
    unique_players: int
    top_scorer_username: str | None
    top_score: float


@dataclass
class SeasonDailyPoint:
    date: str
    count: int


def get_seasons_summary(session: Session) -> list[SeasonSummary]:
    seasons = session.scalars(select(Season).order_by(Season.start_date.desc())).all()
    results = []
    for s in seasons:
        row = session.execute(
            select(
                func.count(Submission.id).label("total"),
                func.count(distinct(Submission.user_id)).label("players"),
                func.coalesce(func.sum(Submission.total_score), 0).label("points"),
            ).where(Submission.date >= s.start_date, Submission.date <= s.end_date)
        ).first()
        champion = session.execute(
            select(User.username, func.sum(Submission.total_score).label("pts"))
            .join(User, Submission.user_id == User.user_id)
            .where(Submission.date >= s.start_date, Submission.date <= s.end_date)
            .group_by(Submission.user_id)
            .order_by(func.sum(Submission.total_score).desc())
            .limit(1)
        ).first()
        results.append(
            SeasonSummary(
                season=s,
                total_submissions=row.total or 0,
                unique_players=row.players or 0,
                total_points=row.points or 0.0,
                champion_username=champion.username if champion else None,
                champion_points=champion.pts if champion else 0.0,
            )
        )
    return results


def get_season_stats(session: Session, season: Season) -> SeasonStats:
    agg = session.execute(
        select(
            func.count(Submission.id).label("total"),
            func.count(distinct(Submission.user_id)).label("players"),
            func.coalesce(func.sum(Submission.total_score), 0).label("points"),
            func.count(distinct(Submission.game_id)).label("games"),
        ).where(Submission.date >= season.start_date, Submission.date <= season.end_date)
    ).first()

    busy_day = session.execute(
        select(Submission.date, func.count(Submission.id).label("cnt"))
        .where(Submission.date >= season.start_date, Submission.date <= season.end_date)
        .group_by(Submission.date)
        .order_by(func.count(Submission.id).desc())
        .limit(1)
    ).first()

    total_days = (season.end_date - season.start_date).days + 1
    avg_daily = (agg.total or 0) / total_days if total_days > 0 else 0.0

    return SeasonStats(
        total_submissions=agg.total or 0,
        unique_players=agg.players or 0,
        total_points=agg.points or 0.0,
        games_active=agg.games or 0,
        most_active_date=busy_day.date if busy_day else None,
        most_active_date_count=busy_day.cnt if busy_day else 0,
        avg_daily_submissions=round(avg_daily, 1),
    )


def get_season_leaderboard(session: Session, season: Season) -> list[SeasonPlayerRow]:
    rows = session.execute(
        select(
            Submission.user_id,
            User.username,
            func.sum(Submission.total_score).label("pts"),
            func.count(Submission.id).label("cnt"),
            func.count(distinct(Submission.game_id)).label("games"),
        )
        .join(User, Submission.user_id == User.user_id)
        .where(Submission.date >= season.start_date, Submission.date <= season.end_date)
        .group_by(Submission.user_id)
        .order_by(func.sum(Submission.total_score).desc())
    ).all()
    return [
        SeasonPlayerRow(
            rank=i + 1,
            user_id=r.user_id,
            username=r.username,
            total_score=r.pts,
            submission_count=r.cnt,
            games_played=r.games,
        )
        for i, r in enumerate(rows)
    ]


def get_season_game_breakdown(session: Session, season: Season) -> list[SeasonGameRow]:
    games = session.scalars(select(Game).where(Game.enabled.is_(True))).all()
    results = []
    for game in games:
        agg = session.execute(
            select(
                func.count(Submission.id).label("cnt"),
                func.count(distinct(Submission.user_id)).label("players"),
            ).where(
                Submission.game_id == game.id,
                Submission.date >= season.start_date,
                Submission.date <= season.end_date,
            )
        ).first()
        if not agg or agg.cnt == 0:
            continue
        top = session.execute(
            select(User.username, Submission.total_score)
            .join(User, Submission.user_id == User.user_id)
            .where(
                Submission.game_id == game.id,
                Submission.date >= season.start_date,
                Submission.date <= season.end_date,
            )
            .order_by(Submission.total_score.desc())
            .limit(1)
        ).first()
        results.append(
            SeasonGameRow(
                game_id=game.id,
                game_name=game.name,
                submission_count=agg.cnt,
                unique_players=agg.players,
                top_scorer_username=top.username if top else None,
                top_score=top.total_score if top else 0.0,
            )
        )
    results.sort(key=lambda r: r.submission_count, reverse=True)
    return results


def get_season_daily_activity(session: Session, season: Season) -> list[SeasonDailyPoint]:
    rows = session.execute(
        select(Submission.date, func.count(Submission.id).label("cnt"))
        .where(Submission.date >= season.start_date, Submission.date <= season.end_date)
        .group_by(Submission.date)
        .order_by(Submission.date.asc())
    ).all()
    return [SeasonDailyPoint(date=str(r.date), count=r.cnt) for r in rows]
