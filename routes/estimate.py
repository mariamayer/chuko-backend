"""
POST /api/estimate-price
"""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lib.estimates import save_estimate, _generate_id
from lib.estimate_images import save_design_images
from lib.email_send import send_estimate_emails
from lib.vision import analyze_images
from lib.pricing import calculate_estimate
from lib.clients import get_client
from lib.shopify_products import fetch_variant_price_cents

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
    product_type: str | None = None      # e.g. "tshirt", "hoodie", "cap", "mug"
    product_variant: str | None = None   # e.g. "white", "black", "color"
    technique: str | None = None         # e.g. "dtg", "dtf", "serigrafia", "bordado", "grabado"
    # Lookup-mode fields (used when client has mode="lookup" in their pricing rules)
    product_name: str | None = None      # Spanish product name, e.g. "remera", "gorra", "buzo"
    logo_placement: str | None = None    # e.g. "1 logo", "2 logos frente y espalda", "diseño 30x40"
    logo_colors: str | None = None       # e.g. "1 color", "2 colores", "full color", "sin color (grabado)"
    client_id: str = "default"
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

    # ── Resolve base price from Shopify if not explicitly provided ────────────
    resolved_base_price_cents = req.base_price_cents
    if not resolved_base_price_cents and (req.variant_id or req.product_id):
        client = get_client(req.client_id)
        shopify_price = fetch_variant_price_cents(
            variant_id=req.variant_id,
            product_id=req.product_id,
            store_domain=client.get("shopify_store_domain") if client else None,
            storefront_token=client.get("shopify_storefront_token") if client else None,
        )
        if shopify_price:
            resolved_base_price_cents = shopify_price
            print(f"[estimate-price] Using Shopify price: {shopify_price} cents for variant={req.variant_id} product={req.product_id}")

    # ── Derive logo_colors from vision analysis when not explicitly provided ──
    resolved_logo_colors = req.logo_colors
    if not resolved_logo_colors and analysis:
        designs = [d for d in [analysis.get("front"), analysis.get("back")] if d]
        color_count = max((d.get("color_count", 1) for d in designs), default=1)
        technique_lower = (req.technique or "").lower()
        if technique_lower in ("dtf",):
            resolved_logo_colors = "full color"
        elif technique_lower in ("grabado", "laser", "grabado laser"):
            resolved_logo_colors = "sin color (grabado)"
        elif technique_lower in ("bordado",):
            resolved_logo_colors = ""
        elif color_count == 1:
            resolved_logo_colors = "1 color"
        elif color_count == 2:
            resolved_logo_colors = "2 colores"
        else:
            resolved_logo_colors = "3 colores"

    total_result, breakdown = calculate_estimate(
        analysis=analysis,
        quantity=req.quantity,
        size=req.size,
        color=req.color,
        base_price_cents=resolved_base_price_cents,
        product_type=req.product_type,
        product_variant=req.product_variant,
        technique=req.technique,
        product_name=req.product_name,
        logo_placement=req.logo_placement,
        logo_colors=resolved_logo_colors,
        client_id=req.client_id,
    )

    # ── Build response ────────────────────────────────────────────────────────
    is_consult = total_result == "consultar"
    currency_out = breakdown.get("currency", req.currency)
    estimate_value = total_result if not is_consult else "consultar"
    total_price = total_result if not is_consult else None

    response = {
        "estimate": estimate_value,
        "total": estimate_value,
        "currency": currency_out,
        "consultar": is_consult,
        "base_price_source": "lookup_table",
        "breakdown": breakdown,
        "analysis": analysis,
        "meta": {
            "product_id": req.product_id,
            "variant_id": req.variant_id,
        },
    }

    # Save estimate with ID and optionally send emails
    estimate_id = _generate_id()
    response["estimate_id"] = estimate_id

    design_saved = save_design_images(estimate_id, req.front_design, req.back_design)

    save_data = {
        "estimate_id": estimate_id,
        "client_id": req.client_id,
        "estimate": estimate_value,
        "total": total_price,
        "currency": currency_out,
        "consultar": is_consult,
        "breakdown": response["breakdown"],
        "analysis": analysis,
        "meta": response["meta"],
        "client_name": req.client_name,
        "client_email": req.client_email,
        "client_company": req.client_company,
        "design_images": design_saved,
    }
    save_estimate(estimate_id, save_data)

    if req.client_name or req.client_email:
        ok, msg = send_estimate_emails(estimate_id, save_data)
        if not ok:
            print("[estimate-price] email warning:", msg)

    print("[estimate-price] response:", response)
    return response
