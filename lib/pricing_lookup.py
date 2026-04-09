"""
Personalization price lookup engine.

In shopify_base mode:
  total = (shopify_base_price_per_unit + personalization_per_unit) × quantity

Base price comes from the Shopify variant price sent with the request.
Personalization price is looked up from the client's pricing rules table by:
  (technique, logo_placement, colors, quantity_tier)
"""

import unicodedata


def _norm(s: str | None) -> str:
    """Lowercase + strip accents for fuzzy matching."""
    if not s:
        return ""
    s = s.lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _qty_tier(quantity: int, tiers: list[int]) -> str:
    """Return the qty_NNN column key for the given quantity."""
    sorted_tiers = sorted(tiers)
    chosen = sorted_tiers[0]
    for t in sorted_tiers:
        if quantity >= t:
            chosen = t
    return f"qty_{chosen}"


def lookup_personalization_price(
    rules: dict,
    technique: str | None,
    logo_placement: str | None,
    colors: str | None,
    quantity: int,
) -> int | None:
    """
    Look up the personalization cost per unit.

    Returns:
        int   — price per unit in the rules currency
        None  — no matching row found → return "consultar"
    """
    rows = rules.get("personalization_prices", [])
    tiers = rules.get("quantity_tiers", [50, 100, 200, 500])
    tier_key = _qty_tier(quantity, tiers)

    t_norm = _norm(technique)
    p_norm = _norm(logo_placement)
    c_norm = _norm(colors)

    # Priority 1: exact match on all three
    for row in rows:
        if (
            _norm(row.get("technique")) == t_norm
            and _norm(row.get("logo_placement")) == p_norm
            and _norm(row.get("colors")) == c_norm
        ):
            val = row.get(tier_key)
            if val is None or val == "":
                return None  # consultar
            return int(val)

    # Priority 2: match technique + placement, ignore colors
    for row in rows:
        if (
            _norm(row.get("technique")) == t_norm
            and _norm(row.get("logo_placement")) == p_norm
            and not row.get("colors")
        ):
            val = row.get(tier_key)
            if val is None or val == "":
                return None
            return int(val)

    # Priority 3: match technique only (blank placement)
    for row in rows:
        if (
            _norm(row.get("technique")) == t_norm
            and not row.get("logo_placement")
            and not row.get("colors")
        ):
            val = row.get(tier_key)
            if val is None or val == "":
                return None
            return int(val)

    return None  # no match → consultar


def calculate_shopify_base_estimate(
    *,
    base_price_per_unit: float,   # from Shopify, in the rules currency (e.g. ARS pesos)
    quantity: int,
    technique: str | None,
    logo_placement: str | None,
    colors: str | None,
    rules: dict,
) -> tuple[int | str, dict]:
    """
    Compute total = (base_per_unit + personalization_per_unit) × quantity.

    Returns:
        (total_int, breakdown)   — numeric total
        ("consultar", breakdown) — when personalization price is unknown
    """
    currency = rules.get("currency", "ARS")
    tiers = rules.get("quantity_tiers", [50, 100, 200, 500])
    tier_key = _qty_tier(quantity, tiers)

    personalization = lookup_personalization_price(
        rules, technique, logo_placement, colors, quantity
    )

    breakdown = {
        "base_price_per_unit": round(base_price_per_unit),
        "personalization_per_unit": personalization,
        "quantity": quantity,
        "tier": tier_key,
        "technique": technique,
        "logo_placement": logo_placement,
        "colors": colors,
        "currency": currency,
    }

    if personalization is None:
        return "consultar", breakdown

    total = round((base_price_per_unit + personalization) * quantity)
    breakdown["total"] = total
    return total, breakdown
