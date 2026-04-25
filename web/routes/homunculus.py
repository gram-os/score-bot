from fastapi import APIRouter, Depends, Request

from bot.db.homunculus import get_homunculus_upgrades
from web.deps import _db_session, require_homunculus_access, templates

router = APIRouter()


@router.get("/homunculus")
async def homunculus_view(
    request: Request,
    session: dict = Depends(require_homunculus_access),
):
    db = _db_session()
    try:
        upgrades = get_homunculus_upgrades(db)
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "homunculus.html",
        {
            "active": "homunculus",
            "upgrades": upgrades,
            "role": session.get("role", "admin"),
        },
    )
