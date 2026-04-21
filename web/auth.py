import json
import os
from datetime import date as date_type

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.config import Config

from bot.database import (
    Game,
    Submission,
    add_submission_manual,
    delete_submission,
    get_engine,
    get_leaderboard,
)

config = Config(environ=os.environ)

oauth = OAuth(config)
oauth.register(
    name="discord",
    client_id=os.environ.get("DISCORD_CLIENT_ID"),
    client_secret=os.environ.get("DISCORD_CLIENT_SECRET"),
    authorize_url="https://discord.com/api/oauth2/authorize",
    access_token_url="https://discord.com/api/oauth2/token",
    client_kwargs={"scope": "identify"},
)

router = APIRouter(prefix="/auth", tags=["auth"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])

templates = Jinja2Templates(directory="web/templates")

PAGE_SIZE = 50


class NotAuthenticated(Exception):
    pass


def _admin_ids() -> set[str]:
    raw = os.environ.get("ADMIN_DISCORD_IDS", "")
    return {uid.strip() for uid in raw.split(",") if uid.strip()}


def _db_session() -> Session:
    engine = get_engine()
    return Session(engine)


async def require_admin(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id:
        raise NotAuthenticated()
    return {"user_id": user_id, "username": request.session.get("username", "")}


@router.get("/login")
async def login(request: Request):
    redirect_uri = os.environ.get(
        "DISCORD_REDIRECT_URI", str(request.url_for("callback"))
    )
    return await oauth.discord.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="callback")
async def callback(request: Request):
    token = await oauth.discord.authorize_access_token(request)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
    resp.raise_for_status()
    user = resp.json()

    user_id = user["id"]
    username = user.get("username", user_id)

    if user_id not in _admin_ids():
        return HTMLResponse(
            content=f"<h1>403 Forbidden</h1><p>Discord ID {user_id} is not authorized.</p>",
            status_code=403,
        )

    request.session["user_id"] = user_id
    request.session["username"] = username
    return RedirectResponse(url="/admin", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


@admin_router.get("")
async def admin_index(session: dict = Depends(require_admin)):
    return RedirectResponse(url="/admin/submissions", status_code=302)


@admin_router.get("/submissions")
async def submissions_list(
    request: Request,
    game: str = "",
    user: str = "",
    date: str = "",
    page: int = 1,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        games = db.execute(select(Game).order_by(Game.name)).scalars().all()

        filters_list = []
        if game:
            filters_list.append(Submission.game_id == game)
        if user:
            filters_list.append(Submission.username.ilike(f"%{user}%"))
        if date:
            filters_list.append(Submission.date == date)

        count_stmt = select(func.count()).select_from(Submission)
        if filters_list:
            count_stmt = count_stmt.where(*filters_list)
        total_count = db.scalar(count_stmt)

        data_stmt = select(Submission).order_by(Submission.submitted_at.desc())
        if filters_list:
            data_stmt = data_stmt.where(*filters_list)
        offset = (page - 1) * PAGE_SIZE
        rows = db.execute(data_stmt.offset(offset).limit(PAGE_SIZE)).scalars().all()
    finally:
        db.close()

    def page_url(p: int) -> str:
        params = f"?page={p}"
        if game:
            params += f"&game={game}"
        if user:
            params += f"&user={user}"
        if date:
            params += f"&date={date}"
        return f"/admin/submissions{params}"

    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        request,
        "submissions.html",
        {
            "active": "submissions",
            "submissions": rows,
            "games": games,
            "filters": {"game": game, "user": user, "date": date},
            "page": page,
            "has_next": (page * PAGE_SIZE) < total_count,
            "total": total_count,
            "page_url": page_url,
            "flash": flash,
        },
    )


@admin_router.post("/submissions/{submission_id}/delete")
async def submission_delete(
    request: Request,
    submission_id: int,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        delete_submission(db, submission_id)
        db.commit()
    finally:
        db.close()
    request.session["flash"] = f"Submission #{submission_id} deleted."
    return RedirectResponse(url="/admin/submissions", status_code=303)


@admin_router.get("/submissions/new")
async def submission_new_form(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        games = db.execute(select(Game).order_by(Game.name)).scalars().all()
    finally:
        db.close()
    return templates.TemplateResponse(
        request,
        "submission_new.html",
        {
            "active": "submissions",
            "games": games,
            "today": date_type.today().isoformat(),
            "error": None,
        },
    )


@admin_router.post("/submissions/new")
async def submission_new_submit(
    request: Request,
    user_id: str = Form(...),
    username: str = Form(...),
    game_id: str = Form(...),
    date: str = Form(...),
    base_score: float = Form(...),
    raw_data: str = Form("{}"),
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        games = db.execute(select(Game).order_by(Game.name)).scalars().all()
        try:
            parsed_raw = json.loads(raw_data) if raw_data.strip() else {}
        except json.JSONDecodeError as e:
            return templates.TemplateResponse(
                request,
                "submission_new.html",
                {
                    "active": "submissions",
                    "games": games,
                    "today": date,
                    "error": f"Invalid JSON in raw_data: {e}",
                },
                status_code=422,
            )
        submission_date = date_type.fromisoformat(date)
        add_submission_manual(db, user_id, username, game_id, submission_date, base_score, parsed_raw)
        db.commit()
    finally:
        db.close()
    request.session["flash"] = f"Submission added for {username}."
    return RedirectResponse(url="/admin/submissions", status_code=303)


@admin_router.get("/games")
async def games_list(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        games = db.execute(select(Game).order_by(Game.name)).scalars().all()
        counts = {
            row.game_id: row.count
            for row in db.execute(
                select(Submission.game_id, func.count(Submission.id).label("count"))
                .group_by(Submission.game_id)
            ).all()
        }
    finally:
        db.close()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        request,
        "games.html",
        {
            "active": "games",
            "games": games,
            "counts": counts,
            "flash": flash,
        },
    )


@admin_router.post("/games/{game_id}/toggle")
async def game_toggle(
    request: Request,
    game_id: str,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        game = db.get(Game, game_id)
        if game:
            game.enabled = not game.enabled
            db.commit()
            state = "enabled" if game.enabled else "disabled"
            request.session["flash"] = f"{game.name} {state}."
    finally:
        db.close()
    return RedirectResponse(url="/admin/games", status_code=303)


@admin_router.get("/leaderboard")
async def leaderboard_view(
    request: Request,
    period: str = "weekly",
    game: str = "",
    session: dict = Depends(require_admin),
):
    if period not in ("daily", "weekly", "monthly", "alltime"):
        period = "weekly"

    db = _db_session()
    try:
        games = db.execute(select(Game).order_by(Game.name)).scalars().all()
        rows = get_leaderboard(db, period, game_id=game or None)
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
            "game": game,
        },
    )
