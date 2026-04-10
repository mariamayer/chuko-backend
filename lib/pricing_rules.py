"""
Pricing rules persistence — per-client, stored in data/pricing_rules/{client_id}.json.
"""

import json
from pathlib import Path

RULES_DIR = Path("data/pricing_rules")


def _path(client_id: str) -> Path:
    return RULES_DIR / f"{client_id}.json"


_EMPTY_RULES: dict = {
    "mode": "additive",
    "currency": "ARS",
    "quantity_tiers": [50, 100, 200, 500],
    "personalization_prices": [],
}


def load_rules(client_id: str = "default") -> dict:
    """Load pricing rules for a client. Returns safe empty defaults if the file doesn't exist."""
    path = _path(client_id)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[pricing_rules] Failed to load rules for {client_id}: {e}")
    return dict(_EMPTY_RULES)


def save_rules(rules: dict, client_id: str = "default") -> None:
    """Persist pricing rules for a client."""
    RULES_DIR.mkdir(parents=True, exist_ok=True)
    with open(_path(client_id), "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
