"""
Performance Digest Agent — HTTP endpoints.

GET /api/agents/performance-digest/run     → build + email digest (saves run)
GET /api/agents/performance-digest/preview → return digest JSON without emailing
"""

import os

from fastapi import APIRouter, HTTPException, Query

from lib.agent_runs import save_run
from lib.performance_digest import build_digest, send_digest

router = APIRouter(prefix="/api/agents/performance-digest", tags=["agents"])

_AGENT_TOKEN = os.environ.get("AGENT_TOKEN") or os.environ.get("REPORT_TOKEN")


def _check_token(token: str) -> None:
    if _AGENT_TOKEN and token != _AGENT_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing token")


@router.get("/run")
def run_digest(
    token: str = Query(default=""),
    client_id: str = Query(default="default"),
    weeks: int = Query(default=4, ge=1, le=52),
):
    """Trigger digest build and send it via email. Saves the run to history."""
    _check_token(token)
    ok, msg = send_digest()
    status = "success" if ok else "error"
    try:
        digest = build_digest(weeks=weeks)
        save_run(client_id, "performance_digest", digest, status=status)
    except Exception as e:
        print(f"[performance_digest] Failed to save run: {e}")
    if not ok:
        raise HTTPException(status_code=500, detail=msg)
    return {"ok": True, "message": msg}


@router.get("/preview")
def preview_digest(
    token: str = Query(default=""),
    client_id: str = Query(default="default"),
    weeks: int = Query(default=4, ge=1, le=52),
    no_ai: bool = Query(default=False),
):
    """Preview digest data as JSON without sending email. Saves the run to history.
    Pass no_ai=true to skip the OpenAI call and return raw metrics only."""
    _check_token(token)
    try:
        digest = build_digest(weeks=weeks, no_ai=no_ai)
        save_run(client_id, "performance_digest", digest, status="preview")
        return {"ok": True, "digest": digest}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
