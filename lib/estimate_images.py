"""
Persist design uploads (data URLs) next to estimate JSON and resolve paths for serving.
"""

import base64
import os
import re
from pathlib import Path

ESTIMATES_DIR = Path(os.environ.get("ESTIMATES_DIR", "data/estimates"))

_DATA_URL = re.compile(
    r"^data:image/(?P<fmt>png|jpeg|jpg|webp|gif);base64,(?P<b64>.+)$",
    re.IGNORECASE | re.DOTALL,
)

_MAX_BYTES = 12 * 1024 * 1024  # 12 MB per image


def _subdir(estimate_id: str) -> Path:
    return ESTIMATES_DIR / estimate_id


def save_design_images(
    estimate_id: str,
    front_design: str | None,
    back_design: str | None,
) -> dict[str, bool]:
    """
    Decode data URLs and write front.{ext} / back.{ext} under data/estimates/{estimate_id}/.
    Returns {"front": bool, "back": bool} for what was saved.
    """
    result = {"front": False, "back": False}
    sub = _subdir(estimate_id)
    sub.mkdir(parents=True, exist_ok=True)

    for side, raw in (("front", front_design), ("back", back_design)):
        if not raw or not str(raw).strip():
            continue
        try:
            data, ext = _decode_data_url(str(raw).strip())
        except ValueError:
            continue
        if len(data) > _MAX_BYTES:
            continue
        name = f"{side}.{ext}"
        path = sub / name
        path.write_bytes(data)
        result[side] = True

    return result


def _decode_data_url(data_url: str) -> tuple[bytes, str]:
    m = _DATA_URL.match(data_url.strip())
    if not m:
        raise ValueError("not a supported image data URL")
    fmt = m.group("fmt").lower()
    ext = "jpg" if fmt == "jpeg" else fmt
    raw = base64.b64decode(m.group("b64"), validate=False)
    return raw, ext


def design_images_saved(estimate_id: str) -> dict[str, bool]:
    """Return which sides have files on disk."""
    sub = _subdir(estimate_id)
    out = {"front": False, "back": False}
    if not sub.is_dir():
        return out
    for side in ("front", "back"):
        for ext in ("png", "jpg", "jpeg", "webp", "gif"):
            if (sub / f"{side}.{ext}").is_file():
                out[side] = True
                break
    return out


def resolve_design_image_path(estimate_id: str, side: str) -> Path | None:
    """Return path to image file or None."""
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


def media_type_for_path(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(ext, "application/octet-stream")
