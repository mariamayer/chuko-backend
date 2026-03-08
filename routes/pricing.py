"""
Pricing rules — GET/PUT per-client pricing configuration.
Visible to any user with the price_estimator module.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lib.pricing_rules import load_rules, save_rules

router = APIRouter(prefix="/api/pricing-rules", tags=["pricing"])


class PricingRules(BaseModel):
    base_price_cents: int
    per_color_surcharge_cents: int
    double_sided_surcharge_cents: int
    logo_size_multipliers: dict[str, float]
    quantity_tiers: dict[str, float]
    product_type_multipliers: dict[str, float]
    technique_multipliers: dict[str, float]
    technique_color_logic: dict[str, str]


@router.get("")
def get_rules(client_id: str = "default"):
    return {"ok": True, "rules": load_rules(client_id)}


@router.put("")
def update_rules(body: PricingRules, client_id: str = "default"):
    try:
        save_rules(body.model_dump(), client_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True, "rules": load_rules(client_id)}
