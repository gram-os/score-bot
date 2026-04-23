import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from bot.database import get_config, set_config
from web.deps import _db_session, require_admin, templates
from web.routes.logs import DISPLAY_TIMEZONES

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/config")
async def config_view(
    request: Request,
    saved: str = "",
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        display_timezone = get_config(db, "display_timezone", "America/New_York")
    finally:
        db.close()
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "active": "config",
            "display_timezone": display_timezone,
            "timezones": DISPLAY_TIMEZONES,
            "saved": bool(saved),
        },
    )


@router.post("/config")
async def config_update(
    request: Request,
    display_timezone: str = Form(...),
    session: dict = Depends(require_admin),
):
    valid_zones = {tz for tz, _ in DISPLAY_TIMEZONES}
    if display_timezone not in valid_zones:
        display_timezone = "America/New_York"

    db = _db_session()
    try:
        set_config(db, "display_timezone", display_timezone)
    finally:
        db.close()

    log.info(
        "Admin %s updated config: display_timezone=%s",
        session["username"],
        display_timezone,
    )
    return RedirectResponse("/admin/config?saved=1", status_code=303)
