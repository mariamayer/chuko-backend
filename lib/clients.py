"""
Client configuration management.

Each client is stored as a JSON file in data/clients/{client_id}.json
The "default" client is always available and reads from environment variables
for backward compatibility with the existing single-client setup.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

CLIENTS_DIR = Path("data/clients")

AVAILABLE_MODULES = [
    "price_estimator",
    "chat",
    "performance_digest",
    "seo_brief",
    "ad_copy",
]


def _ensure_dir() -> None:
    CLIENTS_DIR.mkdir(parents=True, exist_ok=True)


def get_default_config() -> dict:
    """Build the default client config from environment variables."""
    return {
        "client_id": "default",
        "name": os.environ.get("CLIENT_NAME", "merch7am"),
        "shopify_store_domain": os.environ.get("SHOPIFY_STORE_DOMAIN", ""),
        "shopify_storefront_token": os.environ.get("SHOPIFY_STOREFRONT_TOKEN", ""),
        "shopify_store_url": os.environ.get("SHOPIFY_STORE_URL", ""),
        "digest_email": (
            os.environ.get("DIGEST_EMAIL")
            or os.environ.get("REPORT_EMAIL")
            or os.environ.get("ADMIN_EMAIL", "")
        ),
        "enabled_modules": AVAILABLE_MODULES,
        "created_at": datetime.utcnow().isoformat(),
    }


def get_client(client_id: str) -> Optional[dict]:
    """
    Load client config by ID.
    Falls back to env-var config for client_id == 'default'.
    """
    _ensure_dir()
    path = CLIENTS_DIR / f"{client_id}.json"
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[clients] Failed to load {client_id}: {e}")
            return None
    if client_id == "default":
        return get_default_config()
    return None


def list_clients() -> list[dict]:
    """Return all saved clients, plus the default if not overridden."""
    _ensure_dir()
    clients: list[dict] = []
    seen_ids: set[str] = set()

    for path in sorted(CLIENTS_DIR.glob("*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                c = json.load(f)
            clients.append(c)
            seen_ids.add(c.get("client_id", ""))
        except Exception:
            continue

    # Always surface the default client
    if "default" not in seen_ids:
        clients.insert(0, get_default_config())

    return clients


def save_client(client_id: str, config: dict) -> dict:
    """Create or update a client config file. Returns the saved dict."""
    _ensure_dir()
    now = datetime.utcnow().isoformat()
    config = dict(config)
    config["client_id"] = client_id
    config.setdefault("created_at", now)
    config["updated_at"] = now

    path = CLIENTS_DIR / f"{client_id}.json"
    with open(path, encoding="utf-8", mode="w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    return config


def delete_client(client_id: str) -> bool:
    """Delete a client config. The 'default' client cannot be deleted."""
    if client_id == "default":
        return False
    path = CLIENTS_DIR / f"{client_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def sanitize(client: dict) -> dict:
    """Mask sensitive fields before returning to the API caller."""
    c = dict(client)
    if c.get("shopify_storefront_token"):
        c["shopify_storefront_token"] = "••••••••"
    if c.get("password"):
        c["password"] = "••••••••"
    return c
