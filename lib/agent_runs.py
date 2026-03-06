"""
Agent run history storage.

Each run is saved as a JSON file in data/agent_runs/{run_id}.json
List endpoints return lightweight summaries; the detail endpoint returns the full result.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

RUNS_DIR = Path("data/agent_runs")

AGENT_TYPES = ["performance_digest", "seo_brief", "ad_copy"]


def _ensure_dir() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def save_run(
    client_id: str,
    agent_type: str,
    result: dict,
    status: str = "success",
) -> dict:
    """Persist an agent run result. Returns the saved run dict."""
    _ensure_dir()
    run_id = (
        f"RUN-{agent_type.upper()[:6]}-"
        f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-"
        f"{uuid.uuid4().hex[:5].upper()}"
    )
    run = {
        "run_id": run_id,
        "client_id": client_id,
        "agent_type": agent_type,
        "status": status,
        "result": result,
        "created_at": datetime.utcnow().isoformat(),
    }
    path = RUNS_DIR / f"{run_id}.json"
    with open(path, encoding="utf-8", mode="w") as f:
        json.dump(run, f, indent=2, ensure_ascii=False)
    return run


def list_runs(
    client_id: Optional[str] = None,
    agent_type: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    List runs newest-first, optionally filtered by client_id and/or agent_type.
    Returns lightweight summaries (no full result payload).
    """
    _ensure_dir()
    runs: list[dict] = []
    for path in sorted(RUNS_DIR.glob("RUN-*.json"), reverse=True):
        try:
            with open(path, encoding="utf-8") as f:
                run = json.load(f)
        except Exception:
            continue

        if client_id and run.get("client_id") != client_id:
            continue
        if agent_type and run.get("agent_type") != agent_type:
            continue

        runs.append({
            "run_id": run["run_id"],
            "client_id": run.get("client_id", ""),
            "agent_type": run.get("agent_type", ""),
            "status": run.get("status", ""),
            "created_at": run.get("created_at", ""),
        })
        if len(runs) >= limit:
            break

    return runs


def get_run(run_id: str) -> Optional[dict]:
    """Return a full run record (including result payload) by ID."""
    _ensure_dir()
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
