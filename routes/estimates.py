"""
Estimates API — list saved estimates and manage pricing rules.

GET    /api/estimates              → list all estimates (sorted newest first)
GET    /api/estimates/{id}         → single estimate detail
GET    /api/estimates/{id}/design/{side} → design image (file or presigned S3 redirect)
DELETE /api/estimates/{id}         → delete estimate + images
GET    /api/pricing-rules          → current pricing rules
PUT    /api/pricing-rules          → update pricing rules

Storage: S3 when S3_BUCKET env var is set; local filesystem otherwise.
"""

import base64
import json
import os
import shutil
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel

from lib import s3_storage
from lib.estimate_images import (
    design_images_saved,
    media_type_for_path,
    resolve_design_image_path,
    resolve_design_image_s3_key,
)
from lib.pricing_lookup import normalize_breakdown_for_dashboard
from lib.pricing_rules import load_rules, save_rules

router = APIRouter(tags=["estimates"])

ESTIMATES_DIR = Path(os.environ.get("ESTIMATES_DIR", "data/estimates"))
_TOKEN = os.environ.get("AGENT_TOKEN") or os.environ.get("REPORT_TOKEN")


def _check_token(token: str) -> None:
    if _TOKEN and token != _TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing token")


def _add_created_at(data: dict) -> dict:
    """Derive created_at from estimate_id (EST-YYYYMMDD-XXXX)."""
    eid = data.get("estimate_id", "")
    created_at = ""
    if eid.startswith("EST-") and len(eid) >= 12:
        try:
            created_at = f"{eid[4:8]}-{eid[8:10]}-{eid[10:12]}"
        except Exception:
            pass
    data["created_at"] = created_at
    return data


def _load_estimate_local(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return _add_created_at(data)


def _load_estimate_s3(estimate_id: str) -> dict | None:
    key = s3_storage.estimate_json_key(estimate_id)
    data = s3_storage.get_json(key)
    if data is None:
        return None
    return _add_created_at(data)


def _load_estimate(estimate_id: str) -> dict | None:
    """Load estimate from S3 or local filesystem."""
    if s3_storage.is_enabled():
        return _load_estimate_s3(estimate_id)
    path = ESTIMATES_DIR / f"{estimate_id}.json"
    if not path.exists():
        return None
    return _load_estimate_local(path)


def _estimate_summary(data: dict) -> dict:
    bd = data.get("breakdown", {})
    eid = data.get("estimate_id") or ""
    # Use JSON-stored flag (persists even after container restarts or S3 re-reads)
    imgs = data.get("design_images") or {"front": False, "back": False}
    return {
        "estimate_id": data.get("estimate_id"),
        "created_at": data.get("created_at"),
        "client_id": data.get("client_id") or "default",
        "client_name": data.get("client_name") or "",
        "client_email": data.get("client_email") or "",
        "client_company": data.get("client_company") or "",
        "estimate": data.get("estimate"),
        "currency": data.get("currency", "USD"),
        "quantity": bd.get("quantity"),
        "product_type": bd.get("product_type") or "",
        "product_variant": bd.get("product_variant") or "",
        "technique": bd.get("technique") or "",
        "logo_size": bd.get("logo_size") or "",
        "design_images": imgs,
    }


# ── List estimates ────────────────────────────────────────────────────────────

@router.get("/api/estimates")
def list_estimates(
    token: str = Query(default=""),
    company: str = Query(default=""),
    client_id: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Return all estimates sorted by date descending."""
    _check_token(token)

    estimates = []

    if s3_storage.is_enabled():
        # List all JSON keys from S3 (already sorted newest-first by key name)
        prefix = s3_storage.estimate_list_prefix()
        keys = s3_storage.list_keys(prefix)
        json_keys = [k for k in keys if k.endswith(".json")]
        for key in json_keys:
            try:
                data = s3_storage.get_json(key)
                if not data:
                    continue
                _add_created_at(data)
            except Exception:
                continue
            if company:
                cc = (data.get("client_company") or "").strip().lower()
                if company.lower() not in cc:
                    continue
            if client_id:
                if (data.get("client_id") or "default") != client_id:
                    continue
            estimates.append(_estimate_summary(data))
            if len(estimates) >= limit:
                break
    else:
        if not ESTIMATES_DIR.exists():
            return {"ok": True, "count": 0, "estimates": []}
        paths = sorted(ESTIMATES_DIR.glob("EST-*.json"), reverse=True)
        for path in paths:
            try:
                data = _load_estimate_local(path)
            except Exception:
                continue
            if company:
                cc = (data.get("client_company") or "").strip().lower()
                if company.lower() not in cc:
                    continue
            if client_id:
                if (data.get("client_id") or "default") != client_id:
                    continue
            estimates.append(_estimate_summary(data))
            if len(estimates) >= limit:
                break

    return {"ok": True, "count": len(estimates), "estimates": estimates}


# ── Design image ──────────────────────────────────────────────────────────────

@router.get("/api/estimates/{estimate_id}/design/{side}")
def get_estimate_design_image(
    estimate_id: str,
    side: str,
    token: str = Query(default=""),
):
    """Return the front/back design image."""
    _check_token(token)
    if side not in ("front", "back"):
        raise HTTPException(status_code=404, detail="Invalid side")

    # ── S3 path: redirect to presigned URL ───────────────────────────────────
    if s3_storage.is_enabled():
        key = resolve_design_image_s3_key(estimate_id, side)
        if key:
            url = s3_storage.presigned_url(key, expires_in=3600)
            return RedirectResponse(url=url, status_code=302)
        # Fall through to JSON b64 fallback below

    # ── Local filesystem path ────────────────────────────────────────────────
    img_path = resolve_design_image_path(estimate_id, side)
    if img_path:
        return FileResponse(img_path, media_type=media_type_for_path(img_path))

    # ── JSON-embedded base64 fallback (old estimates or local dev) ────────────
    data = _load_estimate(estimate_id)
    if data:
        b64_map = data.get("design_images_b64") or {}
        raw = b64_map.get(side)
        if raw and isinstance(raw, str) and raw.startswith("data:image/"):
            header, _, payload = raw.partition(",")
            media_type = header.removeprefix("data:").partition(";")[0]
            img_bytes = base64.b64decode(payload)
            return Response(content=img_bytes, media_type=media_type)

    raise HTTPException(status_code=404, detail="Image not found")


# ── Single estimate detail ────────────────────────────────────────────────────

def _absolute_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _design_image_href(eid: str, side: str, token: str, base: str) -> str:
    path = f"/api/estimates/{eid}/design/{side}"
    if token:
        return f"{base}{path}?{urlencode({'token': token})}"
    return f"{base}{path}"


def _enrich_estimate_payload(data: dict, *, token: str = "", public_base: str = "") -> dict:
    """Attach design image flags, paths, and ready-to-use image URLs."""
    eid = data.get("estimate_id") or ""
    imgs = data.get("design_images") or {"front": False, "back": False}
    out = dict(data)
    if isinstance(out.get("breakdown"), dict):
        out["breakdown"] = normalize_breakdown_for_dashboard(out["breakdown"])
    out["design_images"] = imgs
    out["design_image_paths"] = {
        "front": f"/api/estimates/{eid}/design/front" if imgs.get("front") else None,
        "back": f"/api/estimates/{eid}/design/back" if imgs.get("back") else None,
    }
    base = public_base or ""
    out["images"] = {
        "front": _design_image_href(eid, "front", token, base) if imgs.get("front") else None,
        "back": _design_image_href(eid, "back", token, base) if imgs.get("back") else None,
    }
    # Strip large b64 blobs from the detail response (not needed by the client)
    out.pop("design_images_b64", None)
    return out


@router.get("/api/estimates/{estimate_id}")
def get_estimate(estimate_id: str, request: Request, token: str = Query(default="")):
    """Return full detail for a single estimate."""
    _check_token(token)
    data = _load_estimate(estimate_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Estimate not found")
    try:
        public_base = _absolute_base_url(request)
        return {
            "ok": True,
            "estimate": _enrich_estimate_payload(data, token=token, public_base=public_base),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Delete estimate ───────────────────────────────────────────────────────────

@router.delete("/api/estimates/{estimate_id}")
def delete_estimate(estimate_id: str, token: str = Query(default="")):
    """Delete a single estimate and its associated design images."""
    _check_token(token)

    if s3_storage.is_enabled():
        key = s3_storage.estimate_json_key(estimate_id)
        if not s3_storage.object_exists(key):
            raise HTTPException(status_code=404, detail="Estimate not found")
        s3_storage.delete_object(key)
        s3_storage.delete_prefix(s3_storage.estimate_image_prefix(estimate_id))
    else:
        path = ESTIMATES_DIR / f"{estimate_id}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Estimate not found")
        path.unlink()
        img_dir = ESTIMATES_DIR / estimate_id
        if img_dir.is_dir():
            shutil.rmtree(img_dir)

    return {"ok": True, "deleted": estimate_id}


# ── Pricing rules ─────────────────────────────────────────────────────────────

@router.get("/api/pricing-rules")
def get_pricing_rules(token: str = Query(default="")):
    """Return current pricing rules."""
    _check_token(token)
    return {"ok": True, "rules": load_rules()}


class PricingRulesUpdate(BaseModel):
    base_price_cents: int
    per_color_surcharge_cents: int
    logo_size_multipliers: dict[str, float]
    quantity_tiers: dict[str, float]


@router.put("/api/pricing-rules")
def update_pricing_rules(body: PricingRulesUpdate, token: str = Query(default="")):
    """Save updated pricing rules. Changes take effect on the next estimate request."""
    _check_token(token)
    try:
        rules = {
            "base_price_cents": body.base_price_cents,
            "per_color_surcharge_cents": body.per_color_surcharge_cents,
            "logo_size_multipliers": body.logo_size_multipliers,
            "quantity_tiers": body.quantity_tiers,
        }
        save_rules(rules)
        return {"ok": True, "rules": rules}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
