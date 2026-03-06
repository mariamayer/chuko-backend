"""
Pricing rules persistence — loads/saves rules from data/pricing_rules.json.
Falls back to hardcoded defaults if the file doesn't exist yet.
"""

import json
import os
from pathlib import Path

RULES_FILE = Path(os.environ.get("RULES_FILE", "data/pricing_rules.json"))

# ── Defaults (match the original hardcoded values in pricing.py) ─────────────

DEFAULTS: dict = {
    "base_price_cents": 1500,
    "per_color_surcharge_cents": 50,
    "logo_size_multipliers": {
        "small": 1.0,
        "medium": 1.2,
        "large": 1.5,
        "full": 2.0,
    },
    "quantity_tiers": {
        "15": 1.0,
        "50": 0.95,
        "100": 0.90,
    },
}


def load_rules() -> dict:
    """Load pricing rules from file, falling back to defaults."""
    if RULES_FILE.exists():
        try:
            with open(RULES_FILE, encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults so any missing keys are always present
            merged = {**DEFAULTS}
            merged.update(data)
            merged["logo_size_multipliers"] = {
                **DEFAULTS["logo_size_multipliers"],
                **data.get("logo_size_multipliers", {}),
            }
            merged["quantity_tiers"] = {
                **DEFAULTS["quantity_tiers"],
                **data.get("quantity_tiers", {}),
            }
            return merged
        except Exception as e:
            print(f"[pricing_rules] Failed to load rules file, using defaults: {e}")
    return dict(DEFAULTS)


def save_rules(rules: dict) -> None:
    """Persist pricing rules to file."""
    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
