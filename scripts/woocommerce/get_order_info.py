#!/usr/bin/env python3
"""
Export WooCommerce products (+ variations) into a lean CSV
ready for Airtable.  — Python 3.9 compatible.
"""

import requests
from requests.auth import HTTPBasicAuth
import csv, json, sys, time
from typing import List, Dict, Optional   # ← added Optional
import os
from dotenv import load_dotenv
load_dotenv()

# ── CONFIG ────────────────────────────────────────────────────────────────────
SITE_URL         = 'https://aneeq.co'
CONSUMER_KEY     = os.getenv("WC_CONSUMER_KEY")
CONSUMER_SECRET  = os.getenv("WC_CONSUMER_SECRET")

PRODUCTS_API_URL   = f'{SITE_URL}/wp-json/wc/v3/products'
VARIATIONS_API_URL = f'{SITE_URL}/wp-json/wc/v3/products/{{pid}}/variations'

OUTPUT_CSV_FILE  = 'woocommerce_products_trimmed.csv'

CSV_FIELDS = [
    'id', 'name', 'slug', 'sku',
    'type', 'parent_id',
    'status', 'catalog_visibility',
    'regular_price', 'sale_price', 'price',
    '_subscription_price', '_subscription_period_interval', '_subscription_period',
    'stock_status', 'manage_stock', 'stock_quantity',
    'category_names', 'tag_names', 'image_primary', 'short_description',
    'date_created', 'date_modified',
]

SUB_META_KEYS = {
    '_subscription_price',
    '_subscription_period_interval',
    '_subscription_period',
}

# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────
def wc_get(url: str, params: Optional[dict] = None) -> list[dict]:
    """Authenticated GET with basic error handling."""
    try:
        resp = requests.get(
            url, params=params or {}, timeout=30,
            auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET)
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as err:
        sys.exit(f"❌ WooCommerce API error: {err}")


def fetch_paginated(endpoint: str, per_page: int = 100) -> list[dict]:
    """Fetch all pages from a WooCommerce collection."""
    items, page = [], 1
    while True:
        batch = wc_get(endpoint, params={'per_page': per_page, 'page': page})
        if not batch:
            break
        items.extend(batch)
        print(f"   • {endpoint.split('/')[-1]:10} page {page:>2} → {len(batch)} rows")
        page += 1
    return items


def fetch_all_products_and_variations() -> list[dict]:
    """Parents first, then variations for each variable product."""
    print("🚀 Fetching parent products …")
    parents = fetch_paginated(PRODUCTS_API_URL)
    all_items: List[Dict] = parents.copy()

    for p in parents:
        if p['type'] in ('variable', 'variable-subscription'):
            vid_endpoint = VARIATIONS_API_URL.format(pid=p['id'])
            variations = fetch_paginated(vid_endpoint)
            all_items.extend(variations)
            time.sleep(0.2)            # avoid rate-limit

    print(f"✅ Total rows fetched (parents + variations): {len(all_items)}\n")
    return all_items


def normalise(value):
    """Lists/dicts → JSON strings; scalars untouched."""
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value


def flatten_product(raw: dict) -> dict:
    """Return a row dict matching CSV_FIELDS."""
    row = {k: '' for k in CSV_FIELDS}

    for k in CSV_FIELDS:
        if k in raw:
            row[k] = normalise(raw[k])

    # Categories, tags, primary image
    if raw.get('categories'):
        row['category_names'] = '; '.join(c['name'] for c in raw['categories'])
    if raw.get('tags'):
        row['tag_names'] = '; '.join(t['name'] for t in raw['tags'])
    if raw.get('images'):
        row['image_primary'] = raw['images'][0]['src']

    # Subscription meta
    for meta in raw.get('meta_data', []):
        k, v = meta.get('key'), meta.get('value')
        if k in SUB_META_KEYS:
            row[k] = normalise(v)

    # De-weaponise parent prices
    if raw['type'] in ('variable', 'variable-subscription'):
        for fld in ('price', 'regular_price', 'sale_price', '_subscription_price'):
            row[fld] = ''

    return row


def write_csv(rows: list[dict], path: str):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"✨ Wrote {len(rows)} rows →  {path}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    raw_items      = fetch_all_products_and_variations()
    flattened_rows = [flatten_product(p) for p in raw_items]
    write_csv(flattened_rows, OUTPUT_CSV_FILE)


if __name__ == '__main__':
    main()
