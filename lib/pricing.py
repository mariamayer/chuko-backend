"""
Pricing logic — additive model.

Formula:
    total = (shopify_base_per_unit + personalization_per_unit) × quantity

Where `personalization_per_unit` is looked up from a table stored in the
client's pricing rules JSON (editable from the dashboard).

The lookup finds the best-matching row by scoring:
  product   4 pts exact, 2 pts partial, 0 pts wildcard
  variant   4 pts exact, 1 pt fallback to 'standard', 0 pts mismatch
  technique 4 pts exact (required — skips non-matching rows)
  placement 4 pts exact, 2 pts partial
  colors    4 pts exact, 2 pts closest lower tier

Then selects the price from the quantity tier column closest to (and not
exceeding) the requested quantity.
"""

from __future__ import annotations

import unicodedata
from typing import Optional
from .pricing_rules import load_rules


# ── Normalisation helpers ────────────────────────────────────────────────────

def _norm(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    # strip accents
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


# Techniques that don't charge per colour — always mapped to "full"
_IGNORE_COLOR_TECHS = {"dtf", "dtg", "bordado", "grabado", "grabado laser", "laser"}

# Ordered list of canonical color keys (ascending complexity)
_COLOR_ORDER = ["1", "2", "3+", "full"]

# Colour-count integer → canonical key
def _color_key(n: int, technique: str) -> str:
    if _norm(technique) in {_norm(t) for t in _IGNORE_COLOR_TECHS}:
        return "full"
    if n <= 1:
        return "1"
    if n == 2:
        return "2"
    return "3+"


def _closest_lower_color(wanted: str, available: list[str]) -> str | None:
    """Return the highest color tier in *available* that is ≤ *wanted*."""
    order = _COLOR_ORDER
    try:
        wi = order.index(wanted)
    except ValueError:
        wi = len(order) - 1
    for key in reversed(order[: wi + 1]):
        if key in available:
            return key
    # fallback: any available key
    return available[0] if available else None


# ── Quantity tier lookup ─────────────────────────────────────────────────────

def _qty_price(row: dict, quantity: int) -> int | None:
    """Return the per-unit personalization price for the given quantity."""
    tiers = [(500, row.get("qty_500")), (200, row.get("qty_200")),
             (100, row.get("qty_100")), (50,  row.get("qty_50"))]
    for min_qty, price in tiers:
        if quantity >= min_qty and price is not None:
            return int(price)
    # below minimum tier — use smallest available
    for _, price in reversed(tiers):
        if price is not None:
            return int(price)
    return None


# ── Main lookup ──────────────────────────────────────────────────────────────

def _find_best_row(
    rows: list[dict],
    product: str,
    technique: str,
    variant: str,
    placement: str,
    colors: str,
) -> dict | None:
    product_n   = _norm(product)
    technique_n = _norm(technique)
    variant_n   = _norm(variant)
    placement_n = _norm(placement)
    colors_n    = colors  # already canonical ("1","2","3+","full")

    best_row   = None
    best_score = -1

    for row in rows:
        r_tech = _norm(row.get("technique", ""))
        # technique is required
        if r_tech != technique_n:
            continue

        score = 4  # technique matched

        # product
        r_prod = _norm(row.get("product", ""))
        if r_prod == "" or r_prod == "*":
            score += 0
        elif r_prod == product_n:
            score += 4
        elif r_prod in product_n or product_n in r_prod:
            score += 2
        else:
            score -= 1  # slight penalty for wrong product

        # variant
        r_var = _norm(row.get("variant", "standard"))
        if r_var == variant_n:
            score += 4
        elif r_var == "standard":
            score += 1  # generic fallback
        else:
            score -= 2  # wrong variant

        # placement (partial match ok)
        r_place = _norm(row.get("placement", ""))
        if r_place == placement_n:
            score += 4
        elif r_place in placement_n or placement_n in r_place:
            score += 2

        # colors
        r_colors = row.get("colors", "full")
        avail_colors = [r_colors]
        if r_colors == colors_n:
            score += 4
        elif r_colors in _COLOR_ORDER and colors_n in _COLOR_ORDER:
            ri = _COLOR_ORDER.index(r_colors)
            wi = _COLOR_ORDER.index(colors_n)
            if ri <= wi:
                score += 2  # can use a lower-color-count row as fallback
            else:
                score -= 1  # row needs more colors than requested

        if score > best_score:
            best_score = score
            best_row = row

    return best_row


# ── Public API ───────────────────────────────────────────────────────────────

def calculate_estimate(
    *,
    analysis: dict,
    quantity: int,
    base_price_cents: int | None = None,
    product_type: str | None = None,
    product_variant: str | None = None,
    technique: str | None = None,
    product_name: str | None = None,
    logo_placement: str | None = None,
    logo_colors: str | None = None,
    client_id: str = "default",
) -> tuple[int | str, dict]:
    """
    Returns (total_price_ars, breakdown_dict).
    total_price_ars is an integer (pesos) or the string "consultar".
    """
    rules = load_rules(client_id)
    personalization_prices: list[dict] = rules.get("personalization_prices", [])
    currency = rules.get("currency", "ARS")

    # ── Need base price from Shopify ─────────────────────────────────────────
    if not base_price_cents:
        return "consultar", {
            "reason": "no_base_price",
            "product": product_name or product_type,
            "technique": technique,
        }

    base_per_unit = base_price_cents / 100

    # ── Derive colour count ──────────────────────────────────────────────────
    front = analysis.get("front", {}) if isinstance(analysis, dict) else {}
    back  = analysis.get("back",  {}) if isinstance(analysis, dict) else {}

    def _color_count(side: dict) -> int:
        v = side.get("color_count", 0)
        try:
            return int(v) if v else 0
        except (TypeError, ValueError):
            return 0

    n_colors = max(_color_count(front), _color_count(back), 1)
    has_back  = bool(back and back.get("logo_size"))
    tech_key  = _norm(technique or "")
    color_key = _color_key(n_colors, tech_key)

    # Map placement
    placement_key = _norm(logo_placement or "frente")
    if has_back or "espalda" in placement_key or "2 logo" in placement_key:
        placement_lookup = "2 logos frente+espalda"
    elif "grande" in placement_key or "full" in placement_key:
        placement_lookup = "diseño 30x40"
    else:
        placement_lookup = "1 logo"

    # Normalize variant
    var_raw = _norm(product_variant or "")
    if var_raw in {"negra", "negro", "black", "oscura", "oscuro", "dark"}:
        variant_lookup = "negra"
    elif var_raw in {"plastico", "plástico", "plastic"}:
        variant_lookup = "plástico"
    elif var_raw in {"metal", "vidrio", "metal/vidrio"}:
        variant_lookup = "metal/vidrio"
    else:
        variant_lookup = "standard"

    product_lookup = _norm(product_type or product_name or "")

    # ── Look up personalization price ────────────────────────────────────────
    row = _find_best_row(
        personalization_prices,
        product=product_lookup,
        technique=tech_key,
        variant=variant_lookup,
        placement=placement_lookup,
        colors=color_key,
    )

    if row is None:
        # No matching technique at all → consultar
        return "consultar", {
            "reason": "no_matching_technique",
            "technique": technique,
            "product": product_lookup,
        }

    pers_per_unit = _qty_price(row, quantity)
    if pers_per_unit is None:
        return "consultar", {
            "reason": "no_price_for_quantity",
            "quantity": quantity,
            "row_matched": f"{row.get('product')} / {row.get('technique')} / {row.get('placement')}",
        }

    unit_price = base_per_unit + pers_per_unit
    total = round(unit_price * quantity)

    breakdown = {
        "base_price_per_unit":         round(base_per_unit, 2),
        "personalization_per_unit":    pers_per_unit,
        "unit_price":                  round(unit_price, 2),
        "quantity":                    quantity,
        "total":                       total,
        "currency":                    currency,
        "matched_row": {
            "product":   row.get("product"),
            "technique": row.get("technique"),
            "variant":   row.get("variant"),
            "placement": row.get("placement"),
            "colors":    row.get("colors"),
        },
        "lookup": {
            "product":   product_lookup,
            "technique": tech_key,
            "variant":   variant_lookup,
            "placement": placement_lookup,
            "colors":    color_key,
            "n_colors":  n_colors,
        },
    }

    return total, breakdown
