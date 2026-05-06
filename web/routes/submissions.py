import csv
import io
import json
import logging
from datetime import date as date_type

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import func, select

from bot.database import Game, Submission, add_submission_manual, delete_submission
from bot.db import audit
from web.deps import PAGE_SIZE, _db_session, build_page_url, fetch_all_games, require_admin, templates

log = logging.getLogger(__name__)
router = APIRouter()


def _build_submission_filters(game: str, user: str, date: str) -> list:
    filters = []
    if game:
        filters.append(Submission.game_id == game)
    if user:
        filters.append(Submission.username.ilike(f"%{user}%"))
    if date:
        filters.append(Submission.date == date)
    return filters


@router.get("/submissions")
async def submissions_list(
    request: Request,
    game: str = "",
    user: str = "",
    date: str = "",
    page: int = 1,
    session: dict = Depends(require_admin),
):
    filters_list = _build_submission_filters(game, user, date)
    db = _db_session()
    try:
        games = fetch_all_games(db)
        count_stmt = select(func.count()).select_from(Submission)
        if filters_list:
            count_stmt = count_stmt.where(*filters_list)
        total_count = db.scalar(count_stmt) or 0

        data_stmt = select(Submission).order_by(Submission.submitted_at.desc())
        if filters_list:
            data_stmt = data_stmt.where(*filters_list)
        offset = (page - 1) * PAGE_SIZE
        rows = db.execute(data_stmt.offset(offset).limit(PAGE_SIZE)).scalars().all()
    finally:
        db.close()

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
            "page_url": lambda p: build_page_url("/admin/submissions", p, game=game, user=user, date=date),
            "flash": flash,
        },
    )


@router.get("/submissions/export")
async def submissions_export(
    request: Request,
    game: str = "",
    user: str = "",
    date: str = "",
    session: dict = Depends(require_admin),
):
    filters_list = _build_submission_filters(game, user, date)
    db = _db_session()
    try:
        stmt = select(Submission, Game.name.label("game_name")).join(Game, Submission.game_id == Game.id)
        if filters_list:
            stmt = stmt.where(*filters_list)
        rows = db.execute(stmt.order_by(Submission.submitted_at.desc())).all()
    finally:
        db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "username",
            "game",
            "date",
            "base_score",
            "speed_bonus",
            "total_score",
            "submission_rank",
            "submitted_at",
        ]
    )
    for sub, game_name in rows:
        writer.writerow(
            [
                sub.id,
                sub.username,
                game_name,
                sub.date,
                sub.base_score,
                sub.speed_bonus,
                sub.total_score,
                sub.submission_rank,
                sub.submitted_at,
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=submissions.csv"},
    )


@router.get("/submissions/new")
async def submission_new_form(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        games = fetch_all_games(db)
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


@router.post("/submissions/new")
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
        games = fetch_all_games(db)
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
        new_sub = add_submission_manual(db, user_id, username, game_id, submission_date, base_score, parsed_raw)
        audit.record(
            db,
            actor_email=session["email"],
            actor_role=session.get("role", "admin"),
            action="submission.added",
            target_type="submission",
            target_id=str(new_sub.id),
            details={
                "user_id": user_id,
                "username": username,
                "game_id": game_id,
                "date": date,
                "base_score": base_score,
            },
        )
        db.commit()
    finally:
        db.close()
    log.info(
        "Admin %s added submission: user=%s game=%s date=%s score=%s",
        session["email"],
        username,
        game_id,
        date,
        base_score,
    )
    request.session["flash"] = f"Submission added for {username}."
    return RedirectResponse(url="/admin/submissions", status_code=303)


@router.post("/submissions/{submission_id}/delete")
async def submission_delete(
    request: Request,
    submission_id: int,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        sub = db.get(Submission, submission_id)
        details = (
            {
                "user_id": sub.user_id,
                "username": sub.username,
                "game_id": sub.game_id,
                "date": sub.date.isoformat(),
                "base_score": sub.base_score,
            }
            if sub
            else {}
        )
        delete_submission(db, submission_id)
        audit.record(
            db,
            actor_email=session["email"],
            actor_role=session.get("role", "admin"),
            action="submission.deleted",
            target_type="submission",
            target_id=str(submission_id),
            details=details,
        )
        db.commit()
    finally:
        db.close()
    log.info("Admin %s deleted submission #%d", session["email"], submission_id)
    request.session["flash"] = f"Submission #{submission_id} deleted."
    return RedirectResponse(url="/admin/submissions", status_code=303)
