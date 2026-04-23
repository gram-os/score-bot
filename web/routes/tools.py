import logging
from datetime import date as date_type
from datetime import datetime as dt

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from bot.database import bulk_delete_submissions
from bot.parsers.registry import all_parsers
from web.deps import _db_session, fetch_all_games, require_admin, templates

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/tools")
async def tools_view(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        games = fetch_all_games(db)
    finally:
        db.close()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        request,
        "tools.html",
        {
            "active": "tools",
            "games": games,
            "flash": flash,
            "tested": False,
            "message": "",
            "results": [],
        },
    )


@router.post("/tools/parse-test")
async def tools_parse_test(
    request: Request,
    message: str = Form(...),
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        games = fetch_all_games(db)
    finally:
        db.close()

    results = []
    for parser in all_parsers():
        matched = parser.can_parse(message)
        parse_result = parser.parse(message, "preview_user", dt.utcnow()) if matched else None
        results.append(
            {
                "game_id": parser.game_id,
                "game_name": parser.game_name,
                "matched": matched,
                "parse_result": parse_result,
            }
        )

    return templates.TemplateResponse(
        request,
        "tools.html",
        {
            "active": "tools",
            "games": games,
            "flash": None,
            "tested": True,
            "message": message,
            "results": results,
        },
    )


@router.post("/tools/bulk-delete")
async def tools_bulk_delete(
    request: Request,
    game_id: str = Form(...),
    date: str = Form(...),
    session: dict = Depends(require_admin),
):
    submission_date = date_type.fromisoformat(date)
    db = _db_session()
    try:
        count = bulk_delete_submissions(db, game_id, submission_date)
        db.commit()
    finally:
        db.close()
    log.info(
        "Admin %s bulk-deleted %d submission(s) for %s on %s",
        session["username"],
        count,
        game_id,
        date,
    )
    request.session["flash"] = f"Deleted {count} submission(s) for {game_id} on {date}."
    return RedirectResponse(url="/admin/tools", status_code=303)
