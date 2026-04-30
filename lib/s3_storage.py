"""
Optional S3 storage backend for estimates and design images.

When S3_BUCKET is set, all reads/writes go to S3.
Falls back to the local filesystem when S3_BUCKET is not set (local dev).

Required IAM permissions on the AppRunner task role:
  s3:GetObject, s3:PutObject, s3:DeleteObject, s3:ListBucket
"""

from __future__ import annotations

import json
import os
from typing import Any

_S3_BUCKET: str = os.environ.get("S3_BUCKET", "").strip()
_S3_PREFIX: str = os.environ.get("S3_PREFIX", "estimates/").strip("/") + "/"


def is_enabled() -> bool:
    return bool(_S3_BUCKET)


def _client():
    import boto3  # lazy import — only needed when S3 is configured
    return boto3.client("s3")


# ── JSON objects ─────────────────────────────────────────────────────────────

def put_json(key: str, data: dict[str, Any]) -> None:
    body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    _client().put_object(
        Bucket=_S3_BUCKET,
        Key=key,
        Body=body,
        ContentType="application/json",
    )


def get_json(key: str) -> dict[str, Any] | None:
    try:
        r = _client().get_object(Bucket=_S3_BUCKET, Key=key)
        return json.loads(r["Body"].read())
    except Exception:
        return None


def list_keys(prefix: str) -> list[str]:
    """Return all object keys under *prefix*, sorted newest-first (by key name)."""
    paginator = _client().get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=_S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return sorted(keys, reverse=True)


def object_exists(key: str) -> bool:
    try:
        _client().head_object(Bucket=_S3_BUCKET, Key=key)
        return True
    except Exception:
        return False


def delete_object(key: str) -> None:
    _client().delete_object(Bucket=_S3_BUCKET, Key=key)


def delete_prefix(prefix: str) -> None:
    """Delete all objects under *prefix* (used to wipe an estimate's image dir)."""
    keys = list_keys(prefix)
    if not keys:
        return
    client = _client()
    client.delete_objects(
        Bucket=_S3_BUCKET,
        Delete={"Objects": [{"Key": k} for k in keys]},
    )


# ── Binary objects (images) ───────────────────────────────────────────────────

def put_bytes(key: str, data: bytes, content_type: str) -> None:
    _client().put_object(
        Bucket=_S3_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def presigned_url(key: str, expires_in: int = 3600) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _S3_BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )


# ── Key helpers ───────────────────────────────────────────────────────────────

def estimate_json_key(estimate_id: str) -> str:
    return f"{_S3_PREFIX}{estimate_id}.json"


def estimate_image_key(estimate_id: str, side: str, ext: str) -> str:
    return f"{_S3_PREFIX}{estimate_id}/{side}.{ext}"


def estimate_image_prefix(estimate_id: str) -> str:
    return f"{_S3_PREFIX}{estimate_id}/"


def estimate_list_prefix() -> str:
    return _S3_PREFIX
