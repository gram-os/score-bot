import logging
import os

from fastapi import APIRouter, Depends, Request
from starlette.responses import RedirectResponse

from web.deps import require_homunculus_access
from web.routes import (
    dashboard,
    feedback,
    games,
    homunculus,
    leaderboard,
    live,
    monitoring,
    seasons,
    stats,
    submissions,
    suggestions,
    system,
    tools,
    users,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/logout")
async def logout(request: Request):
    email = request.session.get("email", "unknown")
    log.info("Admin logout: %s", email)
    request.session.clear()
    cf_team_domain = os.environ.get("CF_TEAM_DOMAIN", "")
    return RedirectResponse(url=f"{cf_team_domain}/cdn-cgi/access/logout", status_code=302)


@admin_router.get("")
async def admin_index(request: Request, session: dict = Depends(require_homunculus_access)):
    if session.get("role") == "homunculus_viewer":
        return RedirectResponse(url="/admin/homunculus", status_code=302)
    return RedirectResponse(url="/admin/dashboard", status_code=302)


admin_router.include_router(dashboard.router)
admin_router.include_router(submissions.router)
admin_router.include_router(games.router)
admin_router.include_router(stats.router)
admin_router.include_router(suggestions.router)
admin_router.include_router(feedback.router)
admin_router.include_router(live.router)
admin_router.include_router(leaderboard.router)
admin_router.include_router(tools.router)
admin_router.include_router(users.router)
admin_router.include_router(monitoring.router)
admin_router.include_router(system.router)
admin_router.include_router(homunculus.router)
admin_router.include_router(seasons.router)
