from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import get_db
from app.services.ai_company_monitor import collect_ai_company_monitor, get_ai_company_run_detail

router = APIRouter(prefix="/api", tags=["gg-company"])


@router.get("/ai-company-monitor")
def ai_company_monitor():
    with get_db() as connection:
        return collect_ai_company_monitor(connection)


@router.get("/ai-company-monitor/runs/{run_id}")
def ai_company_run_detail(run_id: str):
    with get_db() as connection:
        try:
            return get_ai_company_run_detail(connection, run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found") from exc
