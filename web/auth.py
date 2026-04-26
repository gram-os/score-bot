import logging
import os

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.config import Config

from web.deps import _admin_ids, _homunculus_viewer_ids, require_homunculus_access
from web.routes import (
    games,
    homunculus,
    leaderboard,
    live,
    monitoring,
    stats,
    submissions,
    suggestions,
    system,
    tools,
    users,
)

log = logging.getLogger(__name__)

_config = Config(environ=os.environ)
oauth = OAuth(_config)
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


@router.get("/login")
async def login(request: Request):
    redirect_uri = os.environ.get("DISCORD_REDIRECT_URI", str(request.url_for("callback")))
    return await oauth.discord.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="callback")
async def callback(request: Request):
    try:
        token = await oauth.discord.authorize_access_token(request)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
        resp.raise_for_status()
    except Exception:
        log.exception("OAuth callback failed")
        return HTMLResponse(
            content="<h1>Login failed</h1><p>Could not complete Discord authentication.</p>",
            status_code=400,
        )
    user = resp.json()

    user_id = user["id"]
    username = user.get("username", user_id)

    if user_id in _admin_ids():
        role = "admin"
    elif user_id in _homunculus_viewer_ids():
        role = "homunculus_viewer"
    else:
        log.warning("Unauthorized login attempt by %s (id=%s)", username, user_id)
        return HTMLResponse(
            content="<h1>403 Forbidden</h1><p>Your account is not authorized to access this panel.</p>",
            status_code=403,
        )

    request.session["user_id"] = user_id
    request.session["username"] = username
    request.session["role"] = role
    log.info("Login: %s (id=%s, role=%s)", username, user_id, role)
    return RedirectResponse(url="/admin", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    username = request.session.get("username", "unknown")
    log.info("Admin logout: %s", username)
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


@admin_router.get("")
async def admin_index(request: Request, session: dict = Depends(require_homunculus_access)):
    if session.get("role") == "homunculus_viewer":
        return RedirectResponse(url="/admin/homunculus", status_code=302)
    return RedirectResponse(url="/admin/submissions", status_code=302)


admin_router.include_router(submissions.router)
admin_router.include_router(games.router)
admin_router.include_router(stats.router)
admin_router.include_router(suggestions.router)
admin_router.include_router(live.router)
admin_router.include_router(leaderboard.router)
admin_router.include_router(tools.router)
admin_router.include_router(users.router)
admin_router.include_router(monitoring.router)
admin_router.include_router(system.router)
admin_router.include_router(homunculus.router)
