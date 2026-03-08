"""
Fetch products from Shopify Storefront API for chatbot recommendations.
"""

import os
from typing import Any, Optional

import httpx

SHOPIFY_STORE = os.environ.get("SHOPIFY_STORE_DOMAIN", "").strip().replace("https://", "").replace("http://", "").rstrip("/")
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_STOREFRONT_TOKEN", "").strip()


def _to_gid(raw_id: str, resource: str) -> str:
    """Convert a numeric ID or GID to a Shopify GID string."""
    if raw_id.startswith("gid://"):
        return raw_id
    return f"gid://shopify/{resource}/{raw_id}"


def fetch_variant_price_cents(
    variant_id: Optional[str] = None,
    product_id: Optional[str] = None,
    store_domain: Optional[str] = None,
    storefront_token: Optional[str] = None,
) -> Optional[int]:
    """
    Fetch the price of a specific Shopify variant (or product's first variant) in cents.
    Returns None if the lookup fails or credentials are missing.
    """
    domain = (store_domain or SHOPIFY_STORE or "").strip().replace("https://", "").replace("http://", "").rstrip("/")
    token = (storefront_token or SHOPIFY_TOKEN or "").strip()

    if not domain or not token:
        return None

    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Storefront-Access-Token": token,
    }
    url = f"https://{domain}/api/2024-01/graphql.json"

    try:
        if variant_id:
            gid = _to_gid(str(variant_id), "ProductVariant")
            query = """
            query GetVariant($id: ID!) {
              node(id: $id) {
                ... on ProductVariant {
                  id
                  price { amount currencyCode }
                }
              }
            }
            """
            r = httpx.post(url, headers=headers, json={"query": query, "variables": {"id": gid}}, timeout=10)
            r.raise_for_status()
            node = r.json().get("data", {}).get("node") or {}
            amount = node.get("price", {}).get("amount")
            if amount is not None:
                return round(float(amount) * 100)

        if product_id:
            gid = _to_gid(str(product_id), "Product")
            query = """
            query GetProductPrice($id: ID!) {
              node(id: $id) {
                ... on Product {
                  id
                  variants(first: 1) {
                    edges {
                      node {
                        price { amount currencyCode }
                      }
                    }
                  }
                }
              }
            }
            """
            r = httpx.post(url, headers=headers, json={"query": query, "variables": {"id": gid}}, timeout=10)
            r.raise_for_status()
            edges = (
                r.json()
                .get("data", {})
                .get("node", {})
                .get("variants", {})
                .get("edges", [])
            )
            if edges:
                amount = edges[0].get("node", {}).get("price", {}).get("amount")
                if amount is not None:
                    return round(float(amount) * 100)

    except Exception as e:
        print(f"[shopify_products] fetch_variant_price_cents error: {e}")

    return None


def fetch_products(limit: int = 50) -> list[dict[str, Any]]:
    """
    Fetch products from Shopify Storefront API.
    Returns list of {title, handle, description, price, url}.
    """
    if not SHOPIFY_STORE or not SHOPIFY_TOKEN:
        return []

    query = """
    query GetProducts($first: Int!) {
      products(first: $first) {
        edges {
          node {
            id
            title
            handle
            description
            priceRange {
              minVariantPrice {
                amount
                currencyCode
              }
            }
          }
        }
      }
    }
    """
    try:
        r = httpx.post(
            f"https://{SHOPIFY_STORE}/api/2024-01/graphql.json",
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Storefront-Access-Token": SHOPIFY_TOKEN,
            },
            json={"query": query, "variables": {"first": limit}},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        edges = data.get("data", {}).get("products", {}).get("edges", [])
        base_url = os.environ.get("SHOPIFY_STORE_URL", f"https://{SHOPIFY_STORE}")
        if not base_url.startswith("http"):
            base_url = f"https://{base_url}"
        products = []
        for edge in edges:
            node = edge.get("node", {})
            price_info = node.get("priceRange", {}).get("minVariantPrice", {})
            amount = price_info.get("amount", "0")
            currency = price_info.get("currencyCode", "USD")
            products.append({
                "title": node.get("title", ""),
                "handle": node.get("handle", ""),
                "description": (node.get("description") or "")[:300],
                "price": f"{currency} {amount}",
                "url": f"{base_url.rstrip('/')}/products/{node.get('handle', '')}",
            })
        return products
    except Exception as e:
        print(f"[shopify_products] Error: {e}")
        return []


def products_to_context(products: list[dict]) -> str:
    """Format products for LLM context."""
    if not products:
        return "No hay productos disponibles en este momento."
    lines = []
    for p in products:
        desc = (p.get("description") or "")[:150]
        if len(p.get("description") or "") > 150:
            desc += "..."
        lines.append(f"- {p['title']}: {desc} Precio desde {p.get('price', 'N/A')}. URL: {p.get('url', '')}")
    return "\n".join(lines)
