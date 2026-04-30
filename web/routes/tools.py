import logging
import os
from datetime import date as date_type
from datetime import datetime as dt

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from bot.database import backfill_monthly_rank_snapshots, bulk_delete_submissions, redate_submissions
from bot.parsers.registry import all_parsers
from web.backfill import process_messages
from web.deps import _db_session, fetch_all_games, require_admin, templates
from web.discord_api import add_reaction, fetch_channel_messages

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
            "backfill_result": None,
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
            "backfill_result": None,
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
        session["email"],
        count,
        game_id,
        date,
    )
    request.session["flash"] = f"Deleted {count} submission(s) for {game_id} on {date}."
    return RedirectResponse(url="/admin/tools", status_code=303)


@router.post("/tools/backfill")
async def tools_backfill(
    request: Request,
    start_date: str = Form(...),
    end_date: str = Form(...),
    admin_session: dict = Depends(require_admin),
):
    token = os.environ.get("DISCORD_TOKEN", "")
    channel_id = int(os.environ.get("DISCORD_CHANNEL_ID", "0"))

    db = _db_session()
    try:
        games = fetch_all_games(db)
    finally:
        db.close()

    start = date_type.fromisoformat(start_date)
    end = date_type.fromisoformat(end_date)

    if start > end:
        return templates.TemplateResponse(
            request,
            "tools.html",
            {
                "active": "tools",
                "games": games,
                "flash": "Start date must be on or before end date.",
                "tested": False,
                "message": "",
                "results": [],
                "backfill_result": None,
            },
        )

    try:
        messages = await fetch_channel_messages(token, channel_id, start, end)
    except httpx.HTTPStatusError as exc:
        log.error("Discord API error during backfill: %s", exc)
        return templates.TemplateResponse(
            request,
            "tools.html",
            {
                "active": "tools",
                "games": games,
                "flash": f"Discord API error: {exc.response.status_code} — check token and channel ID.",
                "tested": False,
                "message": "",
                "results": [],
                "backfill_result": None,
            },
        )

    db = _db_session()
    try:
        backfill_result = process_messages(db, messages)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    log.info(
        "Admin %s backfilled %s–%s: %d recorded, %d duplicates, %d errors",
        admin_session["email"],
        start_date,
        end_date,
        len(backfill_result.recorded),
        len(backfill_result.duplicates),
        len(backfill_result.errors),
    )

    for row in backfill_result.recorded:
        if row.message_id and row.reaction:
            try:
                await add_reaction(token, channel_id, row.message_id, row.reaction)
            except Exception:
                log.warning("Could not react to message %s", row.message_id)

    return templates.TemplateResponse(
        request,
        "tools.html",
        {
            "active": "tools",
            "games": games,
            "flash": None,
            "tested": False,
            "message": "",
            "results": [],
            "backfill_result": backfill_result,
            "backfill_range": f"{start_date} → {end_date}",
        },
    )


@router.post("/tools/redate-submissions")
async def tools_redate_submissions(
    request: Request,
    admin_session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        result = redate_submissions(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    log.info(
        "Admin %s ran submission redate: %d fixed, %d skipped",
        admin_session["email"],
        result.fixed,
        result.skipped,
    )
    msg = f"Redate complete: {result.fixed} submission(s) updated to Eastern dates."
    if result.skipped:
        msg += f" {result.skipped} skipped due to conflicts."
    request.session["flash"] = msg
    return RedirectResponse(url="/admin/tools", status_code=303)


@router.post("/tools/backfill-monthly-ranks")
async def tools_backfill_monthly_ranks(
    request: Request,
    admin_session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        result = backfill_monthly_rank_snapshots(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    log.info(
        "Admin %s ran monthly rank backfill: %d records created across %d months (%d already existed)",
        admin_session["email"],
        result.records_created,
        result.months_processed,
        result.months_skipped,
    )
    request.session["flash"] = (
        f"Monthly rank backfill complete: {result.records_created} snapshot records created "
        f"across {result.months_processed} month(s). "
        f"{result.months_skipped} month(s) already had snapshots and were skipped."
    )
    return RedirectResponse(url="/admin/tools", status_code=303)
