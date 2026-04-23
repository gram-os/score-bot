from datetime import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from bot.database import get_config, get_logs
from web.deps import PAGE_SIZE, _db_session, build_page_url, require_admin, templates

router = APIRouter()

DISPLAY_TIMEZONES = [
    ("UTC", "UTC"),
    ("America/New_York", "Eastern Time (ET)"),
    ("America/Chicago", "Central Time (CT)"),
    ("America/Denver", "Mountain Time (MT)"),
    ("America/Los_Angeles", "Pacific Time (PT)"),
    ("America/Anchorage", "Alaska Time (AKT)"),
    ("Pacific/Honolulu", "Hawaii Time (HT)"),
    ("America/Phoenix", "Arizona (MST, no DST)"),
    ("Europe/London", "London (GMT/BST)"),
    ("Europe/Paris", "Paris (CET/CEST)"),
    ("Europe/Berlin", "Berlin (CET/CEST)"),
    ("Asia/Tokyo", "Tokyo (JST)"),
    ("Asia/Singapore", "Singapore (SGT)"),
    ("Asia/Seoul", "Seoul (KST)"),
    ("Asia/Shanghai", "Shanghai (CST)"),
    ("Australia/Sydney", "Sydney (AEST/AEDT)"),
]


def get_display_tz(db: Session) -> ZoneInfo:
    tz_name = get_config(db, "display_timezone", "America/New_York")
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        return ZoneInfo("America/New_York")


def convert_log_timestamps(rows: list, tz: ZoneInfo) -> list[dict]:
    result = []
    for entry in rows:
        ts = entry.timestamp.replace(tzinfo=timezone.utc).astimezone(tz)
        result.append(
            {
                "timestamp_str": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "level": entry.level,
                "logger": entry.logger,
                "message": entry.message,
            }
        )
    return result


@router.get("/logs")
async def logs_view(
    request: Request,
    level: str = "",
    search: str = "",
    logger: str = "",
    page: int = 1,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        rows, total = get_logs(
            db,
            level=level or None,
            logger_filter=logger or None,
            search=search or None,
            limit=PAGE_SIZE,
            offset=(page - 1) * PAGE_SIZE,
        )
        tz = get_display_tz(db)
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "logs.html",
        {
            "active": "logs",
            "logs": convert_log_timestamps(rows, tz),
            "tz_label": str(tz),
            "filters": {"level": level, "search": search, "logger": logger},
            "page": page,
            "has_next": (page * PAGE_SIZE) < total,
            "total": total,
            "page_url": lambda p: build_page_url("/admin/logs", p, level=level, search=search, logger=logger),
        },
    )
