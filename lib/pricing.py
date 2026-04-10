"""
Pricing logic for the price estimator.

Mode: multiplier (shopify_base)
  - Base price per unit comes from the Shopify variant price (base_price_cents / 100)
  - Multipliers for logo size, technique, color count, and quantity are loaded
    from the client's rules JSON (editable from the dashboard)
  - Formula:
      unit_price = (shopify_base × logo_size_mult × technique_mult × variant_mult)
                   + color_surcharge × color_count   (if charge_per_color)
                   + double_sided_surcharge           (if both sides uploaded)
      total = unit_price × quantity_tier_mult × quantity

Rules are stored in data/pricing_rules/{client_id}.json
"""

from lib.pricing_rules import load_rules


# ── Defaults (used when a key is missing from the rules JSON) ─────────────────

_DEFAULT_LOGO_SIZE_MULTIPLIERS = {
    "small":  0.95,
    "medium": 1.2,
    "large":  1.3,
    "full":   2.0,
}

_DEFAULT_QUANTITY_TIERS = {
    15:  1.0,
    30:  0.97,
    50:  0.93,
    100: 0.88,
    250: 0.83,
    500: 0.78,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _logo_size(analysis: dict) -> str:
    """Derive logo size label from vision-analysis coverage."""
    designs = [d for d in [analysis.get("front"), analysis.get("back")] if d]
    if not designs:
        return "medium"
    coverage = max((d.get("coverage_pct") or d.get("logo_coverage_pct") or 0) for d in designs)
    if coverage < 15:
        return "small"
    if coverage < 40:
        return "medium"
    if coverage < 70:
        return "large"
    return "full"


def _color_count(analysis: dict) -> int:
    designs = [d for d in [analysis.get("front"), analysis.get("back")] if d]
    if not designs:
        return 1
    return max((d.get("color_count") or 1) for d in designs)


def _qty_tier_mult(rules: dict, quantity: int) -> float:
    """Return the quantity discount multiplier for the given quantity."""
    raw = rules.get("quantity_tiers") or {}
    # Support both {"50": 0.9} and {50: 0.9} key formats
    tiers = {int(k): float(v) for k, v in raw.items()}
    if not tiers:
        tiers = _DEFAULT_QUANTITY_TIERS
    chosen_mult = 1.0
    for min_qty in sorted(tiers.keys()):
        if quantity >= min_qty:
            chosen_mult = tiers[min_qty]
    return chosen_mult


# ── Main calculation ──────────────────────────────────────────────────────────

def calculate_estimate(
    *,
    analysis: dict,
    quantity: int,
    size: str | None = None,
    color: str | None = None,
    base_price_cents: int | None = None,   # Shopify variant price in centavos
    product_type: str | None = None,
    product_variant: str | None = None,
    technique: str | None = None,
    product_name: str | None = None,
    logo_placement: str | None = None,
    logo_colors: str | None = None,
    client_id: str = "default",
) -> tuple[int | str, dict]:
    """
    Calculate price estimate using multipliers applied to the Shopify base price.

    Returns:
        (total_price, breakdown_dict)   — total in ARS pesos
        ("consultar", breakdown_dict)   — when base price is missing
    """
    rules = load_rules(client_id)
    currency = rules.get("currency", "ARS")

    # ── Base price from Shopify ───────────────────────────────────────────────
    # base_price_cents is {{ variant.price }} from Shopify Liquid (centavos)
    if not base_price_cents:
        breakdown = {"error": "no_base_price", "currency": currency, "quantity": quantity}
        return "consultar", breakdown

    base_per_unit = base_price_cents / 100  # centavos → pesos

    # ── Logo size multiplier ─────────────────────────────────────────────────
    logo_size = _logo_size(analysis) if analysis else "medium"
    logo_size_mults = {**_DEFAULT_LOGO_SIZE_MULTIPLIERS, **(rules.get("logo_size_multipliers") or {})}
    logo_mult = logo_size_mults.get(logo_size, 1.0)

    # ── Technique multiplier ─────────────────────────────────────────────────
    tech_key = (technique or "").lower().strip()
    technique_mults = rules.get("technique_multipliers") or {}
    tech_mult = float(technique_mults.get(tech_key, 1.0))

    # ── Product variant multiplier (e.g. black garments cost more) ───────────
    variant_key = (product_variant or color or "").lower().strip()
    variant_mults = rules.get("product_variant_multipliers") or {}
    variant_mult = float(variant_mults.get(variant_key, 1.0))

    # ── Product type multiplier ───────────────────────────────────────────────
    ptype_key = (product_name or product_type or "").lower().strip()
    ptype_mults = rules.get("product_type_multipliers") or {}
    ptype_mult = float(ptype_mults.get(ptype_key, 1.0))

    # ── Color surcharge ───────────────────────────────────────────────────────
    color_logic = rules.get("technique_color_logic") or {}
    charge_per_color = color_logic.get(tech_key, "charge_per_color") == "charge_per_color"
    color_surcharge_cents = float(rules.get("per_color_surcharge_cents") or 0)
    n_colors = _color_count(analysis) if analysis else 1
    color_add = (color_surcharge_cents / 100) * max(0, n_colors - 1) if charge_per_color else 0

    # ── Double-sided surcharge ────────────────────────────────────────────────
    has_back = bool(analysis.get("back")) if analysis else False
    double_surcharge_cents = float(rules.get("double_sided_surcharge_cents") or 0)
    double_add = double_surcharge_cents / 100 if has_back else 0

    # ── Unit price ────────────────────────────────────────────────────────────
    unit_price = (base_per_unit * logo_mult * tech_mult * variant_mult * ptype_mult) + color_add + double_add

    # ── Quantity tier discount ────────────────────────────────────────────────
    qty_mult = _qty_tier_mult(rules, quantity)
    total = round(unit_price * qty_mult * quantity)

    breakdown = {
        "base_price_per_unit": round(base_per_unit),
        "logo_size": logo_size,
        "logo_size_multiplier": logo_mult,
        "technique": technique,
        "technique_multiplier": tech_mult,
        "variant_multiplier": variant_mult,
        "product_type_multiplier": ptype_mult,
        "color_count": n_colors,
        "color_surcharge": round(color_add),
        "double_sided_surcharge": round(double_add),
        "unit_price": round(unit_price),
        "quantity": quantity,
        "quantity_tier_multiplier": qty_mult,
        "total": total,
        "currency": currency,
    }

    return total, breakdown
