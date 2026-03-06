"""
SEO Content Brief Agent

Generates structured SEO briefs for Shopify products using OpenAI.
Each brief includes target keywords, meta tags, content sections, and FAQ suggestions.
"""

import json
import os

from openai import OpenAI

from lib.shopify_products import fetch_products


def generate_seo_brief(product: dict) -> dict:
    """
    Generate an SEO content brief for a single product dict.
    Returns structured dict with keywords, meta tags, content outline, and FAQs.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not configured"}

    client = OpenAI(api_key=api_key)
    title = product.get("title", "")
    description = product.get("description", "")
    price = product.get("price", "")
    url = product.get("url", "")

    prompt = f"""You are an SEO specialist for merch7am, a custom merchandise e-commerce store in Spain/Latin America.

Product details:
- Title: {title}
- Description: {description}
- Price: {price}
- URL: {url}

Generate a detailed SEO content brief as JSON with these exact keys:
{{
  "target_keywords": ["list of 8-10 primary and long-tail keywords in Spanish and English"],
  "meta_title": "SEO-optimized page title under 60 characters",
  "meta_description": "Compelling meta description under 155 characters",
  "h1_suggestions": ["2-3 H1 heading options"],
  "content_sections": [
    {{"heading": "Section heading", "key_points": ["point 1", "point 2", "point 3"]}}
  ],
  "faq_suggestions": [
    {{"question": "Common customer question?", "answer": "Concise answer."}}
  ],
  "internal_link_anchors": ["2-3 anchor text ideas for internal linking"],
  "content_tone": "Recommended tone description"
}}

Return ONLY valid JSON. No markdown fences, no explanation outside the JSON object."""

    try:
        resp = client.chat.completions.create(
            model=os.environ.get("CHAT_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=900,
            response_format={"type": "json_object"},
        )
        brief = json.loads(resp.choices[0].message.content)
        brief["product_handle"] = product.get("handle", "")
        brief["product_title"] = title
        brief["product_url"] = url
        return brief
    except Exception as e:
        print(f"[seo_brief] Error for '{title}': {e}")
        return {"error": str(e), "product_handle": product.get("handle", ""), "product_title": title}


def generate_seo_brief_for_handle(handle: str) -> dict:
    """Fetch product by Shopify handle and generate its SEO brief."""
    products = fetch_products(limit=50)
    product = next((p for p in products if p.get("handle") == handle), None)
    if not product:
        return {"error": f"Product handle '{handle}' not found in Shopify catalog"}
    return generate_seo_brief(product)


def generate_seo_briefs_for_all() -> list[dict]:
    """Generate SEO briefs for all Shopify products."""
    products = fetch_products(limit=50)
    if not products:
        return [{"error": "No products found — check SHOPIFY_STORE_DOMAIN and SHOPIFY_STOREFRONT_TOKEN"}]
    return [generate_seo_brief(p) for p in products]
