"""
Estimates API — list saved estimates and manage pricing rules.

GET  /api/estimates              → list all estimates (sorted newest first)
GET  /api/estimates/{id}         → single estimate detail
GET  /api/pricing-rules          → current pricing rules
PUT  /api/pricing-rules          → update pricing rules
"""

import json
import os
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from lib.estimate_images import (
    design_images_saved,
    media_type_for_path,
    resolve_design_image_path,
)
from lib.pricing_lookup import normalize_breakdown_for_dashboard
from lib.pricing_rules import load_rules, save_rules

router = APIRouter(tags=["estimates"])

ESTIMATES_DIR = Path(os.environ.get("ESTIMATES_DIR", "data/estimates"))
_TOKEN = os.environ.get("AGENT_TOKEN") or os.environ.get("REPORT_TOKEN")


def _check_token(token: str) -> None:
    if _TOKEN and token != _TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing token")


def _load_estimate(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # Derive date from estimate_id (EST-YYYYMMDD-XXXX) as ISO string
    eid = data.get("estimate_id", "")
    created_at = ""
    if eid.startswith("EST-") and len(eid) >= 12:
        try:
            created_at = f"{eid[4:8]}-{eid[8:10]}-{eid[10:12]}"
        except Exception:
            pass
    data["created_at"] = created_at
    return data


# ── List estimates ────────────────────────────────────────────────────────────

@router.get("/api/estimates")
def list_estimates(
    token: str = Query(default=""),
    company: str = Query(default=""),
    client_id: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Return all estimates sorted by date descending. Optionally filter by company or client_id."""
    _check_token(token)
    if not ESTIMATES_DIR.exists():
        return {"ok": True, "count": 0, "estimates": []}

    paths = sorted(ESTIMATES_DIR.glob("EST-*.json"), reverse=True)
    estimates = []
    for path in paths:
        try:
            data = _load_estimate(path)
        except Exception:
            continue
        if company:
            client_company = (data.get("client_company") or "").strip().lower()
            if company.lower() not in client_company:
                continue
        if client_id:
            if (data.get("client_id") or "default") != client_id:
                continue
        bd = data.get("breakdown", {})
        eid = data.get("estimate_id") or ""
        imgs = design_images_saved(eid) if eid else {"front": False, "back": False}
        estimates.append({
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
        })
        if len(estimates) >= limit:
            break

    return {"ok": True, "count": len(estimates), "estimates": estimates}


# ── Design image file (for dashboard img src) ────────────────────────────────

@router.get("/api/estimates/{estimate_id}/design/{side}")
def get_estimate_design_image(
    estimate_id: str,
    side: str,
    token: str = Query(default=""),
):
    """Return saved front/back design upload (same token as other estimate APIs)."""
    _check_token(token)
    if side not in ("front", "back"):
        raise HTTPException(status_code=404, detail="Invalid side")
    img_path = resolve_design_image_path(estimate_id, side)
    if not img_path:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(img_path, media_type=media_type_for_path(img_path))


# ── Single estimate detail ────────────────────────────────────────────────────

def _absolute_base_url(request: Request) -> str:
    """Public origin for image URLs (works behind proxies if Forwarded headers are set)."""
    return str(request.base_url).rstrip("/")


def _design_image_href(eid: str, side: str, token: str, base: str) -> str:
    path = f"/api/estimates/{eid}/design/{side}"
    if token:
        return f"{base}{path}?{urlencode({'token': token})}"
    return f"{base}{path}"


def _enrich_estimate_payload(
    data: dict,
    *,
    token: str = "",
    public_base: str = "",
) -> dict:
    """Attach design image flags, relative paths, and ready-to-use image URLs."""
    eid = data.get("estimate_id") or ""
    imgs = design_images_saved(eid) if eid else {"front": False, "back": False}
    out = dict(data)
    if isinstance(out.get("breakdown"), dict):
        out["breakdown"] = normalize_breakdown_for_dashboard(out["breakdown"])
    out["design_images"] = imgs
    out["design_image_paths"] = {
        "front": f"/api/estimates/{eid}/design/front" if imgs["front"] else None,
        "back": f"/api/estimates/{eid}/design/back" if imgs["back"] else None,
    }
    # Ready-to-use URLs for <img src> (absolute when request URL is known). Omitted sides stay null.
    base = public_base or ""
    out["images"] = {
        "front": _design_image_href(eid, "front", token, base) if imgs["front"] else None,
        "back": _design_image_href(eid, "back", token, base) if imgs["back"] else None,
    }
    return out


@router.get("/api/estimates/{estimate_id}")
def get_estimate(estimate_id: str, request: Request, token: str = Query(default="")):
    """Return full detail for a single estimate."""
    _check_token(token)
    path = ESTIMATES_DIR / f"{estimate_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Estimate not found")
    try:
        data = _load_estimate(path)
        public_base = _absolute_base_url(request)
        return {
            "ok": True,
            "estimate": _enrich_estimate_payload(
                data,
                token=token,
                public_base=public_base,
            ),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
