"""
Agent run history endpoints.

GET /api/agent-runs               → list runs (filterable by client_id, agent_type)
GET /api/agent-runs/{run_id}      → get full run detail including result payload
"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from lib.agent_runs import get_run, list_runs

router = APIRouter(prefix="/api/agent-runs", tags=["agent-runs"])

_TOKEN = os.environ.get("AGENT_TOKEN") or os.environ.get("REPORT_TOKEN")


def _check_token(token: str) -> None:
    if _TOKEN and token != _TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing token")


@router.get("")
def get_runs(
    token: str = Query(default=""),
    client_id: Optional[str] = Query(default=None),
    agent_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List agent runs newest-first, optionally filtered."""
    _check_token(token)
    runs = list_runs(client_id=client_id, agent_type=agent_type, limit=limit)
    return {"ok": True, "count": len(runs), "runs": runs}


@router.get("/{run_id}")
def get_run_detail(run_id: str, token: str = Query(default="")):
    """Return the full run record, including the result payload."""
    _check_token(token)
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return {"ok": True, "run": run}
