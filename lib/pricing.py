"""
Dummy pricing rules for the price estimator.
Replace these with your real rules when ready.
"""

LOGO_SIZE_MULTIPLIERS = {
    "small": 1.0,
    "medium": 1.2,
    "large": 1.5,
    "full": 2.0,
}

PER_COLOR_SURCHARGE_CENTS = 50

DEFAULT_BASE_PRICE_CENTS = 1500  # $15.00

QUANTITY_TIERS = {
    15: 1.0,   # 15-49: no discount
    50: 0.95,  # 50-99: 5% off
    100: 0.90,  # 100+: 10% off
}


def calculate_estimate(
    *,
    analysis: dict,
    quantity: int,
    size: str | None = None,
    color: str | None = None,
    base_price_cents: int | None = None,
) -> tuple[int, dict]:
    """
    Calculate price estimate from analysis results and form data.

    Returns:
        (total_cents, breakdown_dict)
    """
    base_price = base_price_cents or DEFAULT_BASE_PRICE_CENTS

    logo_size = "small"
    color_count = 1

    if analysis.get("front") or analysis.get("back"):
        designs = [d for d in [analysis.get("front"), analysis.get("back")] if d]
        size_order = ["small", "medium", "large", "full"]
        sizes = [d.get("logo_size") for d in designs if d.get("logo_size")]
        if sizes:
            logo_size = max(sizes, key=lambda s: size_order.index(s) if s in size_order else -1)
        color_count = max(d.get("color_count", 1) for d in designs)

    logo_multiplier = LOGO_SIZE_MULTIPLIERS.get(logo_size, LOGO_SIZE_MULTIPLIERS["small"])
    color_surcharge = max(0, color_count - 1) * PER_COLOR_SURCHARGE_CENTS

    sorted_tiers = sorted(QUANTITY_TIERS.items(), key=lambda x: -int(x[0]))
    quantity_multiplier = 1.0
    for min_qty, mult in sorted_tiers:
        if quantity >= int(min_qty):
            quantity_multiplier = mult
            break

    unit_price_before_discount = (base_price * logo_multiplier) + color_surcharge
    unit_price_cents = round(unit_price_before_discount * quantity_multiplier)
    total_cents = round(unit_price_cents * quantity)

    breakdown = {
        "base_price_per_unit_cents": base_price,
        "logo_size": logo_size,
        "logo_multiplier": logo_multiplier,
        "color_count": color_count,
        "color_surcharge_cents": color_surcharge,
        "quantity_multiplier": quantity_multiplier,
        "unit_price_cents": unit_price_cents,
        "quantity": quantity,
        "total_cents": total_cents,
        "size": size,
        "color": color,
    }

    return total_cents, breakdown
