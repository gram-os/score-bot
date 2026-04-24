import json
from datetime import timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request

from bot.database import get_usage_events, get_usage_summary
from web.deps import PAGE_SIZE, _db_session, build_page_url, require_admin, templates
from web.routes.logs import get_display_tz

router = APIRouter()


@router.get("/usage")
async def usage_view(
    request: Request,
    event_type: str = "",
    page: int = 1,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        rows, total = get_usage_events(
            db,
            event_type=event_type or None,
            limit=PAGE_SIZE,
            offset=(page - 1) * PAGE_SIZE,
        )
        summary = get_usage_summary(db)
        tz = get_display_tz(db)
    finally:
        db.close()

    events = _format_events(rows, tz)

    return templates.TemplateResponse(
        request,
        "usage.html",
        {
            "active": "usage",
            "events": events,
            "summary": summary,
            "filter_event_type": event_type,
            "page": page,
            "has_next": (page * PAGE_SIZE) < total,
            "total": total,
            "page_url": lambda p: build_page_url("/admin/usage", p, event_type=event_type),
        },
    )


def _format_events(rows: list, tz: ZoneInfo) -> list[dict]:
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
