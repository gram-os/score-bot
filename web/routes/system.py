import asyncio
import logging
import time
from pathlib import Path

import psutil
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from bot.database import get_config, set_config
from web.deps import DISPLAY_TIMEZONES, _db_session, require_admin, templates

log = logging.getLogger(__name__)
router = APIRouter()


def _read_cpu_temp() -> float | None:
    temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        return int(temp_path.read_text().strip()) / 1000.0
    except (FileNotFoundError, ValueError, PermissionError):
        return None


def _format_uptime(seconds: float) -> str:
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _disk_path() -> str:
    return "/data" if Path("/data").exists() else "/"


async def _cpu_percent() -> float:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: psutil.cpu_percent(interval=0.1))


@router.get("/system/stats")
async def system_stats(session: dict = Depends(require_admin)):
    cpu = await _cpu_percent()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(_disk_path())
    uptime_secs = time.time() - psutil.boot_time()

    return JSONResponse(
        {
            "cpu_percent": round(cpu, 1),
            "mem_used_mb": mem.used // (1024 * 1024),
            "mem_total_mb": mem.total // (1024 * 1024),
            "mem_percent": round(mem.percent, 1),
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "disk_percent": round(disk.percent, 1),
            "cpu_temp": _read_cpu_temp(),
            "uptime": _format_uptime(uptime_secs),
        }
    )


@router.get("/system")
async def system_view(
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
        "system.html",
        {
            "active": "system",
            "display_timezone": display_timezone,
            "timezones": DISPLAY_TIMEZONES,
            "saved": bool(saved),
        },
    )


@router.post("/system/config")
async def system_config_update(
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
    log.info("Admin %s updated config: display_timezone=%s", session["email"], display_timezone)
    return RedirectResponse("/admin/system?saved=1", status_code=303)
