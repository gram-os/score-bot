from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request

from bot.database import GameAnalysisRow, get_all_games_difficulty_analysis
from web.deps import _db_session, require_admin, templates

router = APIRouter()

_REFERENCE_AVG = 50.0
_BUCKET_LABELS = ["0–20", "20–40", "40–60", "60–80", "80–100", "100+"]


def _build_chart_data(game_stats: list[GameAnalysisRow]) -> tuple[str, str]:
    labels = [s.game_name for s in game_stats]
    datasets = []
    for i, label in enumerate(_BUCKET_LABELS):
        datasets.append(
            {
                "label": label,
                "data": [
                    round(s.distribution[i].count / s.submission_count * 100, 1) if s.submission_count > 0 else 0.0
                    for s in game_stats
                ],
            }
        )
    return json.dumps(labels), json.dumps(datasets)


@router.get("/difficulty")
async def difficulty_page(
    request: Request,
    session: dict = Depends(require_admin),
):
    db = _db_session()
    try:
        game_stats = get_all_games_difficulty_analysis(db, reference_avg=_REFERENCE_AVG)
    finally:
        db.close()

    chart_labels, chart_datasets = _build_chart_data(game_stats)

    return templates.TemplateResponse(
        request,
        "difficulty.html",
        {
            "active": "difficulty",
            "game_stats": game_stats,
            "reference_avg": _REFERENCE_AVG,
            "chart_labels_json": chart_labels,
            "chart_datasets_json": chart_datasets,
        },
    )
