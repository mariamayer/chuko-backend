"""
Estimate storage - saves estimates to JSON with unique IDs.
"""

import json
import os
from datetime import datetime
from pathlib import Path

ESTIMATES_DIR = Path(os.environ.get("ESTIMATES_DIR", "data/estimates"))


def _ensure_dir():
    ESTIMATES_DIR.mkdir(parents=True, exist_ok=True)


def _generate_id() -> str:
    """Generate unique estimate ID: EST-YYYYMMDD-XXXX"""
    now = datetime.utcnow()
    date_part = now.strftime("%Y%m%d")
    # Simple counter from existing files today
    prefix = f"EST-{date_part}"
    existing = list(ESTIMATES_DIR.glob(f"{prefix}-*.json")) if ESTIMATES_DIR.exists() else []
    num = len(existing) + 1
    return f"{prefix}-{num:04d}"


def save_estimate(estimate_id: str, data: dict) -> None:
    """Save estimate to JSON file."""
    _ensure_dir()
    path = ESTIMATES_DIR / f"{estimate_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
