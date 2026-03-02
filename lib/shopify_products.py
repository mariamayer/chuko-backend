"""
Fetch products from Shopify Storefront API for chatbot recommendations.
"""

import os
from typing import Any

import httpx

SHOPIFY_STORE = os.environ.get("SHOPIFY_STORE_DOMAIN", "").strip().replace("https://", "").replace("http://", "").rstrip("/")
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_STOREFRONT_TOKEN", "").strip()


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
