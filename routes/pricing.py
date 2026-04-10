"""
Pricing rules — GET/PUT per-client pricing configuration.
Visible to any user with the price_estimator module.
"""

from fastapi import APIRouter, HTTPException
from typing import Any

from lib.pricing_rules import load_rules, save_rules

router = APIRouter(prefix="/api/pricing-rules", tags=["pricing"])


@router.get("")
def get_rules(client_id: str = "default"):
    return {"ok": True, "rules": load_rules(client_id)}


@router.put("")
def update_rules(body: dict[str, Any], client_id: str = "default"):
    """Replace the pricing rules for a client. Accepts multiplier or shopify_base mode."""
    valid_modes = ("multiplier", "shopify_base", "lookup", "additive")
    if body.get("mode") not in valid_modes:
        raise HTTPException(status_code=400, detail=f"'mode' must be one of: {', '.join(valid_modes)}")
    if "personalization_prices" in body and not isinstance(body["personalization_prices"], list):
        raise HTTPException(status_code=400, detail="personalization_prices must be a list")
    try:
        save_rules(body, client_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True, "rules": load_rules(client_id)}
