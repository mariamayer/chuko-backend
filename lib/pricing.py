"""
Pricing logic for the price estimator.
Rules are loaded per-client from data/pricing_rules/{client_id}.json.

Uses a lookup-table engine: total = base_price + personalization_price
for the exact (product, variant, technique, logo_placement, colors, quantity_tier)
combination. Returns "consultar" when a price is missing from the table.
"""

from lib.pricing_rules import load_rules
from lib.pricing_lookup import calculate_lookup_estimate


def calculate_estimate(
    *,
    analysis: dict,
    quantity: int,
    size: str | None = None,
    color: str | None = None,
    base_price_cents: int | None = None,
    product_type: str | None = None,
    product_variant: str | None = None,
    technique: str | None = None,
    product_name: str | None = None,    # Spanish product name, e.g. "remera", "gorra"
    logo_placement: str | None = None,  # e.g. "1 logo", "2 logos frente y espalda"
    logo_colors: str | None = None,     # e.g. "1 color", "2 colores", "full color"
    client_id: str = "default",
) -> tuple[int | str, dict]:
    """
    Calculate price estimate using the client's lookup table.

    Returns:
        (total_price, breakdown_dict)   — price in the table's currency (e.g. ARS pesos)
        ("consultar", breakdown_dict)   — when a price is missing from the table
    """
    rules = load_rules(client_id)
    return calculate_lookup_estimate(
        product=product_name or product_type or "",
        variant=product_variant,
        quantity=quantity,
        technique=technique,
        logo_placement=logo_placement,
        colors=logo_colors,
        rules=rules,
    )
