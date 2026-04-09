"""
Lookup-table pricing engine for clients that use exact price tables
instead of the multiplier formula.

Rules file format (data/pricing_rules/{client_id}.json):
  {
    "mode": "lookup",
    "currency": "ARS",
    "min_quantity": 50,
    "quantity_tiers": [50, 100, 200, 500],
    "base_prices": [
      { "product": "remera", "variant": "algodón",
        "qty_50": 13900, "qty_100": 13900, "qty_200": 12900, "qty_500": 12900 },
      ...
    ],
    "personalization_prices": [
      { "product": "remera", "variant": "blanca", "technique": "serigrafia",
        "logo_placement": "1 logo", "colors": "1 color",
        "qty_50": 960, "qty_100": 850, "qty_200": 750, "qty_500": 700 },
      ...
    ]
  }

Total = base_price + personalization_price  (both per unit, for the given quantity tier)
If either price is missing / None  → return "consultar"
"""

from __future__ import annotations
import unicodedata


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(s: str | None) -> str:
    """Lowercase + strip accents + collapse whitespace for fuzzy matching."""
    if not s:
        return ""
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


def _qty_tier(quantity: int, tiers: list[int]) -> str:
    """Return the tier key (e.g. 'qty_500') for the given quantity."""
    sorted_tiers = sorted(tiers, reverse=True)
    for t in sorted_tiers:
        if quantity >= t:
            return f"qty_{t}"
    return f"qty_{sorted_tiers[-1]}"  # below minimum — use smallest tier


def normalize_breakdown_for_dashboard(bd: dict | None) -> dict:
    """Copy breakdown and add defaults for admin UI (safe for saved JSON from older APIs)."""
    out = dict(bd or {})
    _ensure_dashboard_breakdown_fields(out)
    return out


def _ensure_dashboard_breakdown_fields(bd: dict) -> None:
    """
    Admin dashboard expects multiplier-style fields; lookup tables use additive
    pricing instead. Provide stable defaults so UI does not crash on .toFixed().
    """
    bd.setdefault("product_multiplier", 1.0)
    bd.setdefault("variant_multiplier", 1.0)
    if "base_price_per_unit_cents" not in bd:
        base = bd.get("base_price_per_unit")
        if isinstance(base, (int, float)):
            bd["base_price_per_unit_cents"] = int(base)
        else:
            bd["base_price_per_unit_cents"] = 0


def _get_price(row: dict, tier_key: str) -> int | None:
    """Return price from a row dict, None if not present or empty."""
    val = row.get(tier_key)
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def lookup_base_price(
    rules: dict,
    product: str,
    variant: str | None,
    quantity: int,
) -> int | None:
    """
    Find the base price per unit for product+variant at the given quantity.
    Returns None if not found (→ 'consultar').
    Tries exact product+variant match first, then product-only.
    """
    tiers: list[int] = rules.get("quantity_tiers", [50, 100, 200, 500])
    tier_key = _qty_tier(quantity, tiers)
    p_norm = _norm(product)
    v_norm = _norm(variant)

    # 1. Exact product + variant match
    for row in rules.get("base_prices", []):
        if _norm(row.get("product")) == p_norm and _norm(row.get("variant")) == v_norm:
            price = _get_price(row, tier_key)
            if price is not None:
                return price

    # 2. Product match, ignore variant
    for row in rules.get("base_prices", []):
        if _norm(row.get("product")) == p_norm:
            price = _get_price(row, tier_key)
            if price is not None:
                return price

    return None


def lookup_personalization_price(
    rules: dict,
    product: str,
    variant: str | None,
    technique: str,
    logo_placement: str | None,
    colors: str | None,
    quantity: int,
) -> int | None:
    """
    Find the personalization price per unit for the exact combination.
    Returns None if the combination doesn't exist at all.
    Returns -1 as a sentinel when the combination exists but price is blank (→ 'consultar').
    """
    tiers: list[int] = rules.get("quantity_tiers", [50, 100, 200, 500])
    tier_key = _qty_tier(quantity, tiers)
    p_norm = _norm(product)
    v_norm = _norm(variant)
    t_norm = _norm(technique)
    l_norm = _norm(logo_placement)
    c_norm = _norm(colors)

    # 1. Full exact match
    for row in rules.get("personalization_prices", []):
        if (
            _norm(row.get("product")) == p_norm
            and _norm(row.get("variant")) == v_norm
            and _norm(row.get("technique")) == t_norm
            and _norm(row.get("logo_placement")) == l_norm
            and _norm(row.get("colors")) == c_norm
        ):
            price = _get_price(row, tier_key)
            if price is not None:
                return price
            return -1  # combination exists but price is blank

    # 2. Ignore variant (some products have no variant in the pers. table)
    for row in rules.get("personalization_prices", []):
        if (
            _norm(row.get("product")) == p_norm
            and _norm(row.get("technique")) == t_norm
            and _norm(row.get("logo_placement")) == l_norm
            and _norm(row.get("colors")) == c_norm
        ):
            price = _get_price(row, tier_key)
            if price is not None:
                return price
            return -1

    return None


def calculate_lookup_estimate(
    *,
    product: str,
    variant: str | None,
    quantity: int,
    technique: str | None,
    logo_placement: str | None,
    colors: str | None,
    rules: dict,
) -> tuple[int | str, dict]:
    """
    Calculate price using the lookup table.

    Returns:
        ("consultar", breakdown)  — when any required price is missing
        (total_cents, breakdown)  — when all prices are found

    total_cents is in the same currency unit as the prices in the table
    (already in whole pesos for ARS clients, not cents).
    The field is named total_cents for API consistency but holds the raw value.
    """
    min_qty: int = rules.get("min_quantity", 50)
    currency: str = rules.get("currency", "ARS")

    if quantity < min_qty:
        err_bd = {
            "error": f"Cantidad mínima: {min_qty} unidades",
            "quantity": quantity,
            "min_quantity": min_qty,
            "currency": currency,
        }
        _ensure_dashboard_breakdown_fields(err_bd)
        return "consultar", err_bd

    base = lookup_base_price(rules, product, variant, quantity)
    needs_personalization = bool(technique and technique.lower() != "sin personalizacion")

    pers: int | None | str = None
    if needs_personalization:
        result = lookup_personalization_price(
            rules, product, variant, technique or "",
            logo_placement, colors, quantity
        )
        if result is None:
            pers = "consultar"
        elif result == -1:
            pers = "consultar"
        else:
            pers = result

    # Determine whether we can calculate
    consult = False
    if base is None:
        consult = True
    if needs_personalization and pers == "consultar":
        consult = True

    tiers: list[int] = rules.get("quantity_tiers", [50, 100, 200, 500])
    tier_key = _qty_tier(quantity, tiers)
    tier_label = tier_key.replace("qty_", "") + "u"

    breakdown: dict = {
        "product": product,
        "variant": variant,
        "technique": technique,
        "logo_placement": logo_placement,
        "colors": colors,
        "quantity": quantity,
        "quantity_tier": tier_label,
        "base_price_per_unit": base,
        "personalization_price_per_unit": pers,
        "currency": currency,
    }

    if consult:
        breakdown["unit_price"] = "consultar"
        breakdown["total_price"] = "consultar"
        _ensure_dashboard_breakdown_fields(breakdown)
        return "consultar", breakdown

    pers_value = pers if isinstance(pers, int) else 0
    unit_price = (base or 0) + pers_value
    total_price = unit_price * quantity

    breakdown["unit_price"] = unit_price
    breakdown["total_price"] = total_price
    _ensure_dashboard_breakdown_fields(breakdown)
    return total_price, breakdown
