"""
Estimate storage — saves estimates to JSON.

When S3_BUCKET is set, data goes to S3 (survives AppRunner deployments).
Falls back to local filesystem (data/estimates/) when S3 is not configured.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from lib import s3_storage

ESTIMATES_DIR = Path(os.environ.get("ESTIMATES_DIR", "data/estimates"))


def _ensure_dir() -> None:
    ESTIMATES_DIR.mkdir(parents=True, exist_ok=True)


def _generate_id() -> str:
    """Generate unique estimate ID: EST-YYYYMMDD-XXXX"""
    now = datetime.utcnow()
    date_part = now.strftime("%Y%m%d")
    prefix = f"EST-{date_part}"
    if s3_storage.is_enabled():
        # Count today's objects in S3
        keys = s3_storage.list_keys(s3_storage.estimate_list_prefix())
        basename = f"{prefix}-"
        count = sum(1 for k in keys if k.split("/")[-1].startswith(basename))
        return f"{prefix}-{count + 1:04d}"
    else:
        existing = list(ESTIMATES_DIR.glob(f"{prefix}-*.json")) if ESTIMATES_DIR.exists() else []
        return f"{prefix}-{len(existing) + 1:04d}"


def save_estimate(estimate_id: str, data: dict) -> None:
    """Save estimate — to S3 when configured, otherwise to local filesystem."""
    if s3_storage.is_enabled():
        key = s3_storage.estimate_json_key(estimate_id)
        s3_storage.put_json(key, data)
    else:
        _ensure_dir()
        path = ESTIMATES_DIR / f"{estimate_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
