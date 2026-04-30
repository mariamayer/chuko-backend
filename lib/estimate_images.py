"""
Persist design uploads (data URLs) next to estimate JSON and resolve paths for serving.

When S3_BUCKET is set, images are stored in S3 and served via presigned URLs.
Falls back to local filesystem when S3 is not configured.
"""

import base64
import os
import re
from pathlib import Path

from lib import s3_storage

ESTIMATES_DIR = Path(os.environ.get("ESTIMATES_DIR", "data/estimates"))

_DATA_URL = re.compile(
    r"^data:image/(?P<fmt>png|jpeg|jpg|webp|gif);base64,(?P<b64>.+)$",
    re.IGNORECASE | re.DOTALL,
)

_MAX_BYTES = 12 * 1024 * 1024  # 12 MB per image

_CONTENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}


def _subdir(estimate_id: str) -> Path:
    return ESTIMATES_DIR / estimate_id


def _decode_data_url(data_url: str) -> tuple[bytes, str]:
    m = _DATA_URL.match(data_url.strip())
    if not m:
        raise ValueError("not a supported image data URL")
    fmt = m.group("fmt").lower()
    ext = "jpg" if fmt == "jpeg" else fmt
    raw = base64.b64decode(m.group("b64"), validate=False)
    return raw, ext


def save_design_images(
    estimate_id: str,
    front_design: str | None,
    back_design: str | None,
) -> dict[str, bool]:
    """
    Decode data URLs and store front/back images.
    Writes to S3 when configured, otherwise to local filesystem.
    Returns {"front": bool, "back": bool} indicating what was saved.
    """
    result = {"front": False, "back": False}

    for side, raw in (("front", front_design), ("back", back_design)):
        if not raw or not str(raw).strip():
            continue
        try:
            data, ext = _decode_data_url(str(raw).strip())
        except ValueError:
            continue
        if len(data) > _MAX_BYTES:
            continue

        if s3_storage.is_enabled():
            key = s3_storage.estimate_image_key(estimate_id, side, ext)
            s3_storage.put_bytes(key, data, _CONTENT_TYPES.get(ext, "image/jpeg"))
        else:
            sub = _subdir(estimate_id)
            sub.mkdir(parents=True, exist_ok=True)
            (sub / f"{side}.{ext}").write_bytes(data)

        result[side] = True

    return result


def design_images_saved(estimate_id: str) -> dict[str, bool]:
    """Return which sides have images stored (checks S3 or local filesystem)."""
    out = {"front": False, "back": False}

    if s3_storage.is_enabled():
        prefix = s3_storage.estimate_image_prefix(estimate_id)
        keys = s3_storage.list_keys(prefix)
        for key in keys:
            name = key.split("/")[-1]
            for side in ("front", "back"):
                if name.startswith(f"{side}."):
                    out[side] = True
    else:
        sub = _subdir(estimate_id)
        if sub.is_dir():
            for side in ("front", "back"):
                for ext in ("png", "jpg", "jpeg", "webp", "gif"):
                    if (sub / f"{side}.{ext}").is_file():
                        out[side] = True
                        break

    return out


def resolve_design_image_path(estimate_id: str, side: str) -> Path | None:
    """Return local Path to image file, or None (only meaningful in local-fs mode)."""
    if s3_storage.is_enabled():
        return None
    if side not in ("front", "back"):
        return None
    sub = _subdir(estimate_id)
    if not sub.is_dir():
        return None
    for ext in ("png", "jpg", "jpeg", "webp", "gif"):
        p = sub / f"{side}.{ext}"
        if p.is_file():
            return p
    return None


def resolve_design_image_s3_key(estimate_id: str, side: str) -> str | None:
    """Return S3 key for the given side, or None if not found."""
    if not s3_storage.is_enabled():
        return None
    prefix = s3_storage.estimate_image_prefix(estimate_id)
    keys = s3_storage.list_keys(prefix)
    for key in keys:
        name = key.split("/")[-1]
        if name.startswith(f"{side}."):
            return key
    return None


def media_type_for_path(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return _CONTENT_TYPES.get(ext, "application/octet-stream")
