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

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

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
    limit: int = Query(default=100, ge=1, le=500),
):
    """Return all estimates sorted by date descending. Optionally filter by company."""
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
        # Return a lightweight summary row
        estimates.append({
            "estimate_id": data.get("estimate_id"),
            "created_at": data.get("created_at"),
            "client_name": data.get("client_name") or "",
            "client_email": data.get("client_email") or "",
            "client_company": data.get("client_company") or "",
            "estimate": data.get("estimate"),
            "currency": data.get("currency", "EUR"),
            "quantity": data.get("breakdown", {}).get("quantity"),
            "logo_size": data.get("breakdown", {}).get("logo_size"),
        })
        if len(estimates) >= limit:
            break

    return {"ok": True, "count": len(estimates), "estimates": estimates}


# ── Single estimate detail ────────────────────────────────────────────────────

@router.get("/api/estimates/{estimate_id}")
def get_estimate(estimate_id: str, token: str = Query(default="")):
    """Return full detail for a single estimate."""
    _check_token(token)
    path = ESTIMATES_DIR / f"{estimate_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Estimate not found")
    try:
        data = _load_estimate(path)
        return {"ok": True, "estimate": data}
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
