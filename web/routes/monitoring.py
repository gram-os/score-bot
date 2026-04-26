import json
from datetime import timezone

from fastapi import APIRouter, Depends, Request

from bot.database import get_logs, get_usage_events, get_usage_summary
from web.deps import PAGE_SIZE, _db_session, build_page_url, get_display_tz, require_admin, templates

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
    page: int = 1,
    session: dict = Depends(require_admin),
):
    if tab not in ("logs", "usage"):
        tab = "logs"

    db = _db_session()
    try:
        tz = get_display_tz(db)

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
        else:
            rows, total = get_usage_events(
                db,
                event_type=event_type or None,
                limit=PAGE_SIZE,
                offset=(page - 1) * PAGE_SIZE,
            )
            usage_events = _format_events(rows, tz)
            usage_summary = get_usage_summary(db)
            logs = []
    finally:
        db.close()

    def page_url(p: int) -> str:
        if tab == "logs":
            return build_page_url("/admin/monitoring", p, tab=tab, level=level, search=search, logger=logger)
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
            "page": page,
            "has_next": (page * PAGE_SIZE) < total,
            "total": total,
            "page_url": page_url,
        },
    )
