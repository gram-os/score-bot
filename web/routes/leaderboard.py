from datetime import date as date_type, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot.database import Game, Submission, User, get_leaderboard
from web.deps import _db_session, fetch_all_games, require_admin, templates

router = APIRouter()

VALID_PERIODS: tuple[str, ...] = ("daily", "weekly", "monthly", "alltime", "season")


def _normalize_period(period: str) -> str:
    return period if period in VALID_PERIODS else "alltime"


def _find_game(games: list[Game], game_id: str) -> Game | None:
    return next((g for g in games if g.id == game_id), None)


def _format_header(game: Game | None, period: str) -> str:
    if game is None:
        return "Leaderboard"
    return f"{game.name} — {period.capitalize()}"


def _fetch_daily_top(db: Session, game_id: str, limit: int = 5) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    rows = db.execute(
        select(
            Submission.user_id,
            User.username,
            Submission.total_score,
            Submission.submission_rank,
        )
        .join(User, Submission.user_id == User.user_id)
        .where(Submission.game_id == game_id, Submission.date == today)
        .order_by(Submission.total_score.desc())
        .limit(limit)
    ).all()
    return [
        {
            "rank": i + 1,
            "user_id": row.user_id,
            "username": row.username,
            "total_score": row.total_score,
            "submission_rank": row.submission_rank,
        }
        for i, row in enumerate(rows)
    ]


@router.get("/stats/submissions")
async def stats_submissions(
    days: int = Query(default=30),
    session: dict = Depends(require_admin),
):
    if days not in (7, 30, 90):
        days = 30
    cutoff = date_type.today() - timedelta(days=days)

    db = _db_session()
    try:
        rows = db.execute(
            select(
                Submission.date,
                Submission.game_id,
                Game.name.label("game_name"),
                func.count(Submission.id).label("count"),
            )
            .join(Game, Submission.game_id == Game.id)
            .where(Submission.date >= cutoff)
            .group_by(Submission.game_id, Game.name, Submission.date)
            .order_by(Submission.date.asc(), Game.name.asc())
        ).all()
    finally:
        db.close()

    return JSONResponse(
        [
            {
                "date": str(row.date),
                "game_id": row.game_id,
                "game": row.game_name,
                "count": row.count,
            }
            for row in rows
        ]
    )


@router.get("/leaderboard")
async def leaderboard_view(
    request: Request,
    period: str = "alltime",
    game: str | None = None,
    session: dict = Depends(require_admin),
):
    period = _normalize_period(period)
    game_id = game or None

    db = _db_session()
    try:
        games = fetch_all_games(db)
        rows = get_leaderboard(db, period, game_id=game_id)
        active_game = _find_game(games, game_id) if game_id else None
        daily_top = _fetch_daily_top(db, game_id) if active_game else []
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "leaderboard.html",
        {
            "active": "leaderboard",
            "rows": rows,
            "games": games,
            "period": period,
            "game": game_id or "",
            "active_game": active_game,
            "header": _format_header(active_game, period),
            "daily_top": daily_top,
            "periods": VALID_PERIODS,
        },
    )
