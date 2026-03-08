"""
Pricing logic for the price estimator.
Rules are loaded per-client from data/pricing_rules/{client_id}.json (editable via dashboard),
falling back to hardcoded defaults if the file doesn't exist.
"""

from lib.pricing_rules import load_rules


def calculate_estimate(
    *,
    analysis: dict,
    quantity: int,
    size: str | None = None,
    color: str | None = None,
    base_price_cents: int | None = None,
    product_type: str | None = None,
    product_variant: str | None = None,  # e.g. "white", "black", "color"
    technique: str | None = None,
    client_id: str = "default",
) -> tuple[int, dict]:
    """
    Calculate price estimate from analysis results and form data.

    Returns:
        (total_cents, breakdown_dict)
    """
    rules = load_rules(client_id)

    base_price = base_price_cents or rules["base_price_cents"]
    logo_size_multipliers: dict = rules["logo_size_multipliers"]
    per_color_surcharge: int = rules["per_color_surcharge_cents"]
    double_sided_surcharge: int = rules.get("double_sided_surcharge_cents", 300)
    quantity_tiers: dict = rules["quantity_tiers"]
    product_type_multipliers: dict = rules.get("product_type_multipliers", {})
    product_variant_multipliers: dict = rules.get("product_variant_multipliers", {})
    technique_multipliers: dict = rules.get("technique_multipliers", {})
    technique_color_logic: dict = rules.get("technique_color_logic", {})

    # ── Design analysis ───────────────────────────────────────────────────────
    logo_size = "small"
    color_count = 1
    is_double_sided = bool(analysis.get("front") and analysis.get("back"))

    if analysis.get("front") or analysis.get("back"):
        designs = [d for d in [analysis.get("front"), analysis.get("back")] if d]
        size_order = ["small", "medium", "large", "full"]
        sizes = [d.get("logo_size") for d in designs if d.get("logo_size")]
        if sizes:
            logo_size = max(sizes, key=lambda s: size_order.index(s) if s in size_order else -1)
        color_count = max(d.get("color_count", 1) for d in designs)

    # ── Multipliers ───────────────────────────────────────────────────────────
    logo_multiplier = logo_size_multipliers.get(logo_size, 1.0)

    product_multiplier = 1.0
    if product_type:
        product_multiplier = product_type_multipliers.get(product_type, 1.0)

    variant_multiplier = 1.0
    if product_variant:
        variant_multiplier = product_variant_multipliers.get(product_variant, 1.0)

    technique_multiplier = 1.0
    if technique:
        technique_multiplier = technique_multipliers.get(technique, 1.0)

    # Color surcharge only applies when technique charges per color (e.g. screen print)
    color_logic = technique_color_logic.get(technique or "", "charge_per_color")
    color_surcharge = (
        max(0, color_count - 1) * per_color_surcharge
        if color_logic == "charge_per_color"
        else 0
    )

    # Double-sided surcharge when both front and back designs are provided
    sided_surcharge = double_sided_surcharge if is_double_sided else 0

    # ── Quantity discount tier ────────────────────────────────────────────────
    sorted_tiers = sorted(quantity_tiers.items(), key=lambda x: -int(x[0]))
    quantity_multiplier = 1.0
    for min_qty, mult in sorted_tiers:
        if quantity >= int(min_qty):
            quantity_multiplier = mult
            break

    # ── Final calculation ─────────────────────────────────────────────────────
    # Unit price: base × product × variant × technique × logo + color charge + double-sided
    unit_price_before_discount = (
        base_price * product_multiplier * variant_multiplier * technique_multiplier * logo_multiplier
        + color_surcharge
        + sided_surcharge
    )
    unit_price_cents = round(unit_price_before_discount * quantity_multiplier)
    total_cents = round(unit_price_cents * quantity)

    breakdown = {
        "base_price_per_unit_cents": base_price,
        "logo_size": logo_size,
        "logo_multiplier": logo_multiplier,
        "product_type": product_type,
        "product_multiplier": product_multiplier,
        "product_variant": product_variant,
        "variant_multiplier": variant_multiplier,
        "technique": technique,
        "technique_multiplier": technique_multiplier,
        "color_count": color_count,
        "color_surcharge_cents": color_surcharge,
        "double_sided": is_double_sided,
        "double_sided_surcharge_cents": sided_surcharge,
        "quantity_multiplier": quantity_multiplier,
        "unit_price_cents": unit_price_cents,
        "quantity": quantity,
        "total_cents": total_cents,
        "size": size,
        "color": color,
    }

    return total_cents, breakdown
