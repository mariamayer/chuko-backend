"""
POST /api/estimate-price
"""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lib.estimates import save_estimate, _generate_id
from lib.email_send import send_estimate_emails
from lib.vision import analyze_images
from lib.pricing import calculate_estimate

router = APIRouter(prefix="/api", tags=["estimate"])


class EstimateRequest(BaseModel):
    product_id: str | None = None
    variant_id: str | None = None
    quantity: int = Field(..., ge=1, description="Quantity (min 1)")
    size: str | None = None
    color: str | None = None
    front_design: str | None = None  # base64 or data URL
    back_design: str | None = None
    no_designs: bool = False
    base_price_cents: int | None = None
    currency: str = "USD"
    client_name: str | None = None
    client_email: str | None = None
    client_company: str | None = None


@router.post("/estimate-price")
async def estimate_price(req: EstimateRequest):
    # Log request params in terminal (truncate base64 images)
    params = req.model_dump()
    for key in ("front_design", "back_design"):
        if params.get(key) and len(params[key]) > 80:
            params[key] = params[key][:80] + f"... ({len(params[key])} chars)"
    print("[estimate-price] request:", params)

    analysis = {}

    if not req.no_designs and (req.front_design or req.back_design):
        images = [img for img in [req.front_design, req.back_design] if img]
        if images and os.environ.get("OPENAI_API_KEY"):
            try:
                analysis = analyze_images(images)
            except Exception as err:
                raise HTTPException(
                    status_code=500,
                    detail=f"Image analysis failed: {err}",
                )
        elif images and not os.environ.get("OPENAI_API_KEY"):
            analysis = {
                "front": (
                    {"logo_size": "medium", "color_count": 2, "notes": "dummy (no API key)"}
                    if req.front_design
                    else None
                ),
                "back": (
                    {"logo_size": "small", "color_count": 1, "notes": "dummy (no API key)"}
                    if req.back_design
                    else None
                ),
            }
            analysis = {k: v for k, v in analysis.items() if v is not None}

    total_cents, breakdown = calculate_estimate(
        analysis=analysis,
        quantity=req.quantity,
        size=req.size,
        color=req.color,
        base_price_cents=req.base_price_cents,
    )

    estimate_value = round(total_cents / 100, 2)
    response = {
        "estimate": estimate_value,
        "total_cents": total_cents,
        "currency": req.currency,
        "breakdown": {
            "base_price_per_unit_cents": breakdown["base_price_per_unit_cents"],
            "logo_size": breakdown["logo_size"],
            "logo_multiplier": breakdown["logo_multiplier"],
            "color_count": breakdown["color_count"],
            "color_surcharge_cents": breakdown["color_surcharge_cents"],
            "quantity_multiplier": breakdown["quantity_multiplier"],
            "unit_price_cents": breakdown["unit_price_cents"],
            "quantity": breakdown["quantity"],
            "total_cents": breakdown["total_cents"],
            "size": breakdown["size"],
            "color": breakdown["color"],
        },
        "analysis": analysis,
        "meta": {
            "product_id": req.product_id,
            "variant_id": req.variant_id,
        },
    }

    # Save estimate with ID and optionally send emails
    estimate_id = _generate_id()
    response["estimate_id"] = estimate_id

    save_data = {
        "estimate_id": estimate_id,
        "estimate": estimate_value,
        "total_cents": total_cents,
        "currency": req.currency,
        "breakdown": response["breakdown"],
        "analysis": analysis,
        "meta": response["meta"],
        "client_name": req.client_name,
        "client_email": req.client_email,
        "client_company": req.client_company,
    }
    save_estimate(estimate_id, save_data)

    if req.client_name or req.client_email:
        ok, msg = send_estimate_emails(estimate_id, save_data)
        if not ok:
            print("[estimate-price] email warning:", msg)

    print("[estimate-price] response:", response)
    return response
