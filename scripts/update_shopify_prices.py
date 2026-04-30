#!/usr/bin/env python3
"""
update_shopify_prices.py
========================
Reads prices from the spreadsheet and updates Shopify product variant prices
via the Admin API.

Usage
-----
1. Create a Shopify Admin API token:
   Shopify Admin → Settings → Apps and sales channels → Develop apps
   → Create an app → Configure Admin API scopes → enable:
     write_products, read_products
   → Install app → copy the "Admin API access token"

2. Run:
   python scripts/update_shopify_prices.py --token YOUR_TOKEN [--dry-run]

   --dry-run  Shows what would be changed without actually updating Shopify.
"""

import argparse
import json
import time
import unicodedata
import sys
import os

try:
    import requests
except ImportError:
    print("Missing 'requests'. Install with:  pip install requests")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("Missing 'pandas'. Install with:  pip install pandas openpyxl")
    sys.exit(1)


# ── Config ────────────────────────────────────────────────────────────────────

STORE_DOMAIN = "20ghbp-m3.myshopify.com"
SPREADSHEET_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "costos web (1).xlsx")

# Fallback: prices hard-coded from spreadsheet (used if xlsx not found)
PRICES_FROM_SHEET = {
    "remera": 13900,
    "remera negra": 13900,
    "remera vintage": 17999,
    "buzo promocional": 13999,
    "campera con capucha": 19999,
    "gorra": 8999,
    "shopperbag lona": 14999,
    "totebag lona": 14999,
    "totebag canva beige 40x45": 6999,
    "totebag canva negra 40x45": 7999,
    "totebag plastica tipo chandon 50x37x10": 11990,
    "tote rigida": 18900,
    "bolso tejido": 12900,
    "rinonera": 12900,
    "morral sin logo": 13900,
    "mochila negra": 10900,
    "mochila gris": 10900,
    "bolso deportivo 40l sin logo": 27990,
    "bolso de cuero": 264900,
    "shoulder bag polyester 33x17x10": 11900,
    "bolsa cosmetica pu+cloth 25x12x14": 13900,
    "lona algodon": 17900,
    "delantal": 14900,
    "botella acero inoxidable blanca 750ml": 11900,
    "botella acero inoxidable negra 750ml": 11900,
    "botella de vidrio 500ml": 10900,
    "termo pajita acero inox 900ml": 18900,
    "vaso termico": 13900,
    "ice bucket zinc iron d23xh19xb17": 12990,
    "notebook a5 negro 14.2x21.2cm": 8999,
    "seahorse bottle opener": 3999,
    "bolsa 5l 23x19cm sin logo": 12990,
    "totebag de lienzo": 3999,
    "shopperbag lienzo": 6999,
    "shopperbag negra": 7999,
    "piluso de gabardina": 5690,
    "piluso vintage": 6790,
    "piluso": 6490,
    "vaso reutilizable": 1999,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    s = s.lower().strip()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(s.split())


def load_prices_from_sheet(path: str) -> dict[str, int]:
    """Load minimum-qty prices from the spreadsheet."""
    df = pd.read_excel(path, sheet_name="precios_base", header=None)
    df.columns = ["producto", "variante", "qty_min", "qty_max", "precio", "desc"]
    df = df[3:].copy()
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    df["qty_min"] = pd.to_numeric(df["qty_min"], errors="coerce").fillna(0).astype(int)
    df = df[df["precio"].notna() & df["producto"].notna()]

    prices = {}
    for _, row in df.iterrows():
        name = _norm(str(row["producto"]))
        if not name or name == "nan":
            continue
        qty = int(row["qty_min"])
        price = int(row["precio"])
        if name not in prices or qty < min(prices[name].keys()):
            prices.setdefault(name, {})[qty] = price

    # Return the lowest-tier price for each product
    return {name: tiers[min(tiers.keys())] for name, tiers in prices.items()}


# ── Shopify API ───────────────────────────────────────────────────────────────

class ShopifyAdmin:
    def __init__(self, domain: str, token: str):
        self.base = f"https://{domain}/admin/api/2024-01"
        self.headers = {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
        }

    def get_all_products(self) -> list[dict]:
        products = []
        url = f"{self.base}/products.json?limit=250&fields=id,title,variants"
        while url:
            r = self._get(url)
            products.extend(r.json().get("products", []))
            # Pagination via Link header
            link = r.headers.get("Link", "")
            url = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    url = part.strip().lstrip("<").split(">")[0]
        return products

    def update_variant_price(self, variant_id: int, price: float) -> dict:
        url = f"{self.base}/variants/{variant_id}.json"
        payload = {"variant": {"id": variant_id, "price": f"{price:.2f}"}}
        r = self._put(url, payload)
        r.raise_for_status()
        return r.json()

    def _get(self, url: str):
        r = requests.get(url, headers=self.headers, timeout=30)
        self._check_rate_limit(r)
        r.raise_for_status()
        return r

    def _put(self, url: str, payload: dict):
        r = requests.put(url, headers=self.headers, json=payload, timeout=30)
        self._check_rate_limit(r)
        return r

    @staticmethod
    def _check_rate_limit(response):
        """Respect Shopify's rate limit (40 req/s leaky bucket)."""
        limit_header = response.headers.get("X-Shopify-Shop-Api-Call-Limit", "")
        if limit_header:
            used, total = (int(x) for x in limit_header.split("/"))
            if used >= total - 5:
                print(f"  [rate limit] {used}/{total} — pausing 2s…")
                time.sleep(2)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Update Shopify product prices from spreadsheet")
    parser.add_argument("--token", required=True, help="Shopify Admin API access token")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without updating")
    parser.add_argument("--store", default=STORE_DOMAIN, help="Shopify store domain")
    args = parser.parse_args()

    # Load prices
    xlsx_path = SPREADSHEET_PATH
    if not os.path.exists(xlsx_path):
        # Try relative to script location
        here = os.path.dirname(os.path.abspath(__file__))
        xlsx_path = os.path.join(here, "costos web (1).xlsx")

    if os.path.exists(xlsx_path):
        print(f"Loading prices from: {xlsx_path}")
        prices = load_prices_from_sheet(xlsx_path)
    else:
        print("Spreadsheet not found — using hardcoded prices.")
        prices = {_norm(k): v for k, v in PRICES_FROM_SHEET.items()}

    print(f"  {len(prices)} products with prices from spreadsheet\n")

    # Fetch Shopify products
    print(f"Fetching products from Shopify ({args.store})…")
    shopify = ShopifyAdmin(args.store, args.token)
    try:
        products = shopify.get_all_products()
    except Exception as e:
        print(f"ERROR fetching products: {e}")
        sys.exit(1)
    print(f"  {len(products)} products found in Shopify\n")

    # Match and build update plan
    updates = []      # (variant_id, variant_title, product_title, old_price, new_price)
    unmatched_sheet = set(prices.keys())
    unmatched_shopify = []

    for product in products:
        title_norm = _norm(product["title"])
        matched_price = prices.get(title_norm)

        # Try partial match if exact fails
        if matched_price is None:
            for sheet_name, price in prices.items():
                if sheet_name in title_norm or title_norm in sheet_name:
                    matched_price = price
                    unmatched_sheet.discard(sheet_name)
                    break

        if matched_price is None:
            unmatched_shopify.append(product["title"])
            continue

        unmatched_sheet.discard(title_norm)
        for variant in product["variants"]:
            old_price = float(variant["price"])
            if old_price != float(matched_price):
                updates.append({
                    "variant_id": variant["id"],
                    "product_title": product["title"],
                    "variant_title": variant["title"],
                    "old_price": old_price,
                    "new_price": float(matched_price),
                })

    # Preview
    print("=" * 70)
    print(f"PRICE UPDATES ({len(updates)} variants will change):")
    print("=" * 70)
    for u in updates:
        vt = f" [{u['variant_title']}]" if u["variant_title"] != "Default Title" else ""
        print(f"  {u['product_title']}{vt}")
        print(f"    {u['old_price']:>10,.0f} ARS  →  {u['new_price']:>10,.0f} ARS")
    print()

    if unmatched_shopify:
        print(f"NOT MATCHED (Shopify products with no spreadsheet price — {len(unmatched_shopify)}):")
        for t in unmatched_shopify:
            print(f"  · {t}")
        print()

    if unmatched_sheet:
        print(f"NOT MATCHED (spreadsheet rows with no Shopify product — {len(unmatched_sheet)}):")
        for t in sorted(unmatched_sheet):
            print(f"  · {t}")
        print()

    if not updates:
        print("Nothing to update — all prices already match.")
        return

    if args.dry_run:
        print("DRY RUN — no changes made. Remove --dry-run to apply.")
        return

    # Confirm
    print(f"About to update {len(updates)} variant(s) in Shopify.")
    confirm = input("Type 'yes' to continue: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        return

    # Apply updates
    print("\nUpdating…")
    ok = 0
    for u in updates:
        try:
            shopify.update_variant_price(u["variant_id"], u["new_price"])
            print(f"  ✓ {u['product_title']} → {u['new_price']:,.0f} ARS")
            ok += 1
            time.sleep(0.25)  # stay well under rate limit
        except Exception as e:
            print(f"  ✗ {u['product_title']}: {e}")

    print(f"\nDone — {ok}/{len(updates)} variants updated.")


if __name__ == "__main__":
    main()
