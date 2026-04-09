"""
Pricing logic for the price estimator.

Mode: shopify_base
  - Base price per unit comes from the Shopify variant price (base_price_cents / 100)
  - Personalization cost per unit is looked up from the client's rules table
  - total = (base_per_unit + personalization_per_unit) × quantity

Personalization rules are stored in data/pricing_rules/{client_id}.json
and are editable from the dashboard.
"""

from lib.pricing_rules import load_rules
from lib.pricing_lookup import calculate_shopify_base_estimate


def calculate_estimate(
    *,
    analysis: dict,
    quantity: int,
    size: str | None = None,
    color: str | None = None,
    base_price_cents: int | None = None,   # Shopify variant price in minor units (centavos)
    product_type: str | None = None,
    product_variant: str | None = None,
    technique: str | None = None,
    product_name: str | None = None,
    logo_placement: str | None = None,
    logo_colors: str | None = None,
    client_id: str = "default",
) -> tuple[int | str, dict]:
    """
    Calculate price estimate.

    Base price is the Shopify variant price (base_price_cents / 100 = pesos per unit).
    Personalization cost is looked up by technique + logo_placement + colors.

    Returns:
        (total_price, breakdown_dict)   — total in ARS pesos
        ("consultar", breakdown_dict)   — when personalization price is unknown
    """
    rules = load_rules(client_id)

    # Convert Shopify price from centavos to pesos
    # {{ variant.price }} in Liquid returns the price in the store's minor currency unit
    base_per_unit = (base_price_cents or 0) / 100

    return calculate_shopify_base_estimate(
        base_price_per_unit=base_per_unit,
        quantity=quantity,
        technique=technique,
        logo_placement=logo_placement,
        colors=logo_colors,
        rules=rules,
    )
