"""
Pricing rules persistence — per-client, stored in data/pricing_rules/{client_id}.json.
Falls back to hardcoded defaults if the file doesn't exist yet.
"""

import json
from pathlib import Path

RULES_DIR = Path("data/pricing_rules")

# ── Defaults (match the original hardcoded values in pricing.py) ─────────────

DEFAULTS: dict = {
    "base_price_cents": 1500,
    "per_color_surcharge_cents": 50,
    "double_sided_surcharge_cents": 300,
    "logo_size_multipliers": {
        "small": 1.0,
        "medium": 1.2,
        "large": 1.5,
        "full": 2.0,
    },
    "quantity_tiers": {
        "15": 1.0,
        "30": 0.97,
        "50": 0.95,
        "100": 0.90,
        "250": 0.85,
        "500": 0.80,
    },
    "product_type_multipliers": {
        "tshirt": 1.0,
        "hoodie": 1.8,
        "cap": 1.3,
        "mug": 1.1,
        "bag": 0.9,
        "polo": 1.4,
    },
    "technique_multipliers": {
        "dtg": 1.0,
        "dtf": 1.05,
        "serigrafia": 0.9,
        "bordado": 1.6,
        "grabado": 1.2,
    },
    # "charge_per_color" = surcharge applies | "ignore_colors" = no color surcharge
    "technique_color_logic": {
        "dtg": "ignore_colors",
        "dtf": "ignore_colors",
        "serigrafia": "charge_per_color",
        "bordado": "ignore_colors",
        "grabado": "ignore_colors",
    },
    # Multiplier applied on top of product type (e.g. black garments cost more to print on)
    "product_variant_multipliers": {
        "white": 1.0,
        "color": 1.05,
        "black": 1.15,
    },
}


def _path(client_id: str) -> Path:
    return RULES_DIR / f"{client_id}.json"


def load_rules(client_id: str = "default") -> dict:
    """Load pricing rules for a client, falling back to defaults."""
    path = _path(client_id)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults so any missing keys are always present
            merged = {**DEFAULTS}
            merged.update(data)
            for dict_key in ("logo_size_multipliers", "quantity_tiers",
                              "product_type_multipliers", "technique_multipliers",
                              "technique_color_logic", "product_variant_multipliers"):
                merged[dict_key] = {
                    **DEFAULTS[dict_key],
                    **data.get(dict_key, {}),
                }
            return merged
        except Exception as e:
            print(f"[pricing_rules] Failed to load rules for {client_id}, using defaults: {e}")
    return dict(DEFAULTS)


def save_rules(rules: dict, client_id: str = "default") -> None:
    """Persist pricing rules for a client."""
    RULES_DIR.mkdir(parents=True, exist_ok=True)
    with open(_path(client_id), "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
