from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from bot.db.analytics import get_score_anomalies
from web.deps import _db_session, require_admin, templates

router = APIRouter()


@router.get("/anomalies")
async def anomalies_view(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        anomalies = get_score_anomalies(db, lookback_days=30, threshold=2.5)
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "anomalies.html",
        {
            "active": "anomalies",
            "anomalies": anomalies,
        },
    )
