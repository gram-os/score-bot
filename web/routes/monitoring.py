import json
from datetime import timezone

from fastapi import APIRouter, Depends, Request

from bot.database import get_logs, get_usage_events, get_usage_summary
from bot.db import audit as audit_db
from bot.db.config import SCORING_TZ
from web.deps import PAGE_SIZE, _db_session, build_page_url, require_admin, templates

router = APIRouter()


def _format_logs(rows: list, tz) -> list[dict]:
    result = []
    for entry in rows:
        ts = entry.timestamp.replace(tzinfo=timezone.utc).astimezone(tz)
        result.append(
            {
                "timestamp_str": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "level": entry.level,
                "logger": entry.logger,
                "message": entry.message,
                "exc_text": entry.exc_text,
            }
        )
    return result


def _format_events(rows: list, tz) -> list[dict]:
    result = []
    for row in rows:
        ts = row.timestamp.replace(tzinfo=timezone.utc).astimezone(tz)
        result.append(
            {
                "timestamp_str": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "event_type": row.event_type,
                "username": row.username or "—",
                "metadata": json.dumps(row.event_data) if row.event_data else "—",
            }
        )
    return result


@router.get("/monitoring")
async def monitoring_view(
    request: Request,
    tab: str = "logs",
    level: str = "",
    search: str = "",
    logger: str = "",
    event_type: str = "",
    audit_action: str = "",
    audit_actor: str = "",
    audit_from: str = "",
    audit_to: str = "",
    page: int = 1,
    session: dict = Depends(require_admin),
):
    if tab not in ("logs", "usage", "audit"):
        tab = "logs"

    db = _db_session()
    try:
        tz = SCORING_TZ

        if tab == "logs":
            rows, total = get_logs(
                db,
                level=level or None,
                logger_filter=logger or None,
                search=search or None,
                limit=PAGE_SIZE,
                offset=(page - 1) * PAGE_SIZE,
            )
            logs = _format_logs(rows, tz)
            usage_events = []
            usage_summary = []
            audit_entries = []
            audit_actions = []
        elif tab == "usage":
            rows, total = get_usage_events(
                db,
                event_type=event_type or None,
                limit=PAGE_SIZE,
                offset=(page - 1) * PAGE_SIZE,
            )
            usage_events = _format_events(rows, tz)
            usage_summary = get_usage_summary(db)
            logs = []
            audit_entries = []
            audit_actions = []
        else:
            audit_rows, total = audit_db.search_paginated(
                db,
                action_contains=audit_action or None,
                actor_email_contains=audit_actor or None,
                date_from=audit_from or None,
                date_to=audit_to or None,
                limit=PAGE_SIZE,
                offset=(page - 1) * PAGE_SIZE,
            )
            audit_entries = [
                {
                    "id": e.id,
                    "created_at": e.created_at.replace(tzinfo=timezone.utc)
                    .astimezone(tz)
                    .strftime("%Y-%m-%d %H:%M:%S"),
                    "actor_email": e.actor_email,
                    "actor_role": e.actor_role,
                    "action": e.action,
                    "target_type": e.target_type,
                    "target_id": e.target_id,
                    "details": e.details_json,
                }
                for e in audit_rows
            ]
            audit_actions = audit_db.distinct_actions(db)
            logs = []
            usage_events = []
            usage_summary = []
    finally:
        db.close()

    def page_url(p: int) -> str:
        if tab == "logs":
            return build_page_url("/admin/monitoring", p, tab=tab, level=level, search=search, logger=logger)
        if tab == "audit":
            return build_page_url(
                "/admin/monitoring",
                p,
                tab=tab,
                audit_action=audit_action,
                audit_actor=audit_actor,
                audit_from=audit_from,
                audit_to=audit_to,
            )
        return build_page_url("/admin/monitoring", p, tab=tab, event_type=event_type)

    return templates.TemplateResponse(
        request,
        "monitoring.html",
        {
            "active": "monitoring",
            "tab": tab,
            "tz_label": str(tz),
            "logs": logs,
            "log_filters": {"level": level, "search": search, "logger": logger},
            "usage_events": usage_events,
            "usage_summary": usage_summary,
            "filter_event_type": event_type,
            "audit_entries": audit_entries,
            "audit_actions": audit_actions,
            "audit_filters": {
                "action": audit_action,
                "actor": audit_actor,
                "date_from": audit_from,
                "date_to": audit_to,
            },
            "page": page,
            "has_next": (page * PAGE_SIZE) < total,
            "total": total,
            "page_url": page_url,
        },
    )
