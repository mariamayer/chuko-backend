"""
Ad Copy Refresh Agent

Generates Meta Ads and Google Ads copy variations for Shopify products using OpenAI.
Uses estimates data to add demand context. Returns copy ready to paste into ad platforms.
"""

import json
import os

from openai import OpenAI

from lib.shopify_products import fetch_products
from lib.reports import load_all_estimates


def _demand_context(handle: str, estimates: list[dict]) -> str:
    """
    Build a demand summary for a product from estimate data.
    Matches by product_id or variant_id containing the handle string.
    """
    relevant = [
        e for e in estimates
        if handle in (e.get("meta", {}).get("product_id", "") or "").lower()
        or handle in (e.get("meta", {}).get("variant_id", "") or "").lower()
    ]
    if not relevant:
        return "No estimate history for this product yet."
    total_value = sum(e.get("estimate", 0) for e in relevant)
    quantities = [e.get("breakdown", {}).get("quantity", 0) for e in relevant if e.get("breakdown", {}).get("quantity")]
    avg_qty = round(sum(quantities) / len(quantities)) if quantities else 0
    return f"{len(relevant)} quote requests, €{total_value:.2f} total pipeline, avg order {avg_qty} units."


def generate_ad_copy(product: dict, performance_notes: str = "") -> dict:
    """
    Generate 3 Meta Ads + 2 Google Ads copy variations for a product.
    Returns structured dict ready to copy-paste into ad platforms.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not configured"}

    client = OpenAI(api_key=api_key)
    title = product.get("title", "")
    description = product.get("description", "")
    price = product.get("price", "")
    url = product.get("url", "")

    context_block = f"\nPerformance context: {performance_notes}" if performance_notes else ""

    prompt = f"""You are a performance marketing specialist for merch7am, a custom merchandise e-commerce store.

Product:
- Title: {title}
- Description: {description}
- Price: {price}
- URL: {url}{context_block}

Generate fresh, high-converting ad copy variations as JSON with this exact structure:
{{
  "meta_ads": [
    {{
      "variation": 1,
      "headline": "Attention-grabbing headline (max 40 chars)",
      "primary_text": "Engaging ad body copy (max 125 chars, conversational, benefit-focused)",
      "cta": "CTA button text (e.g. Shop Now, Get a Quote, Order Today)"
    }},
    {{
      "variation": 2,
      "headline": "...",
      "primary_text": "...",
      "cta": "..."
    }},
    {{
      "variation": 3,
      "headline": "...",
      "primary_text": "...",
      "cta": "..."
    }}
  ],
  "google_ads": [
    {{
      "variation": 1,
      "headline_1": "Headline 1 (max 30 chars)",
      "headline_2": "Headline 2 (max 30 chars)",
      "headline_3": "Headline 3 (max 30 chars)",
      "description": "Ad description (max 90 chars)"
    }},
    {{
      "variation": 2,
      "headline_1": "...",
      "headline_2": "...",
      "headline_3": "...",
      "description": "..."
    }}
  ],
  "copy_angles": ["3 distinct messaging angles used, e.g. price value, quality, fast turnaround"]
}}

Rules:
- Each Meta and Google variation must use a distinctly different angle and tone
- Keep all character limits strictly
- Write copy that speaks to business owners ordering custom merchandise
- Return ONLY valid JSON, no markdown, no text outside the JSON object"""

    try:
        resp = client.chat.completions.create(
            model=os.environ.get("CHAT_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        copy = json.loads(resp.choices[0].message.content)
        copy["product_handle"] = product.get("handle", "")
        copy["product_title"] = title
        copy["product_url"] = url
        return copy
    except Exception as e:
        print(f"[ad_copy] Error for '{title}': {e}")
        return {"error": str(e), "product_handle": product.get("handle", ""), "product_title": title}


def generate_ad_copy_for_handle(handle: str, performance_notes: str = "") -> dict:
    """Generate ad copy for a specific Shopify product handle."""
    products = fetch_products(limit=50)
    product = next((p for p in products if p.get("handle") == handle), None)
    if not product:
        return {"error": f"Product handle '{handle}' not found in Shopify catalog"}

    estimates = load_all_estimates()
    demand = _demand_context(handle, estimates)
    notes = f"{performance_notes} | Demand: {demand}".strip(" |") if performance_notes else f"Demand: {demand}"

    return generate_ad_copy(product, notes)


def generate_ad_copy_refresh_all() -> list[dict]:
    """Generate a fresh ad copy refresh for every Shopify product."""
    products = fetch_products(limit=50)
    if not products:
        return [{"error": "No products found — check SHOPIFY_STORE_DOMAIN and SHOPIFY_STOREFRONT_TOKEN"}]

    estimates = load_all_estimates()
    results = []
    for p in products:
        handle = p.get("handle", "")
        demand = _demand_context(handle, estimates)
        results.append(generate_ad_copy(p, f"Demand: {demand}"))
    return results
