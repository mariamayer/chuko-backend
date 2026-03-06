"""
Pricing logic for the price estimator.
Rules are loaded from data/pricing_rules.json (editable via dashboard),
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
) -> tuple[int, dict]:
    """
    Calculate price estimate from analysis results and form data.

    Returns:
        (total_cents, breakdown_dict)
    """
    rules = load_rules()

    base_price = base_price_cents or rules["base_price_cents"]
    logo_size_multipliers: dict = rules["logo_size_multipliers"]
    per_color_surcharge: int = rules["per_color_surcharge_cents"]
    quantity_tiers: dict = rules["quantity_tiers"]

    logo_size = "small"
    color_count = 1

    if analysis.get("front") or analysis.get("back"):
        designs = [d for d in [analysis.get("front"), analysis.get("back")] if d]
        size_order = ["small", "medium", "large", "full"]
        sizes = [d.get("logo_size") for d in designs if d.get("logo_size")]
        if sizes:
            logo_size = max(sizes, key=lambda s: size_order.index(s) if s in size_order else -1)
        color_count = max(d.get("color_count", 1) for d in designs)

    logo_multiplier = logo_size_multipliers.get(logo_size, logo_size_multipliers.get("small", 1.0))
    color_surcharge = max(0, color_count - 1) * per_color_surcharge

    sorted_tiers = sorted(quantity_tiers.items(), key=lambda x: -int(x[0]))
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
