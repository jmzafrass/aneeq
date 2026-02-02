import requests
from requests.auth import HTTPBasicAuth
import csv, json, sys
import os
from dotenv import load_dotenv
load_dotenv()

# --- Configuration ----------------------------------------------------------
SITE_URL         = 'https://aneeq.co'
CONSUMER_KEY     = os.getenv("WC_CONSUMER_KEY")
CONSUMER_SECRET  = os.getenv("WC_CONSUMER_SECRET")
PRODUCTS_API_URL = f'{SITE_URL}/wp-json/wc/v3/products'
OUTPUT_CSV_FILE  = 'woocommerce_products_trimmed.csv'

# Keep-list (in the order you’ll see them in the CSV)
FIELDS_TO_KEEP = [
    # ── Identity ───────────────────
    'id', 'name', 'slug', 'sku',
    # ── Hierarchy ──────────────────
    'type', 'parent_id',
    # ── Status / visibility ────────
    'status', 'catalog_visibility',
    # ── Pricing (one-time & subs) ──
    'regular_price', 'sale_price', 'price',      # core product fields
    '_subscription_price', '_subscription_period_interval', '_subscription_period',   # meta
    # ── Stock  ─────────────────────
    'stock_status', 'manage_stock', 'stock_quantity',
    # ── Classification / content ───
    'categories', 'tags', 'short_description',
    # ── Media  ─────────────────────
    'images',
    # ── Timestamps ─────────────────
    'date_created', 'date_modified'
]

# ---------------------------------------------------------------------------

def fetch_all_products(api_url: str, key: str, secret: str) -> list[dict]:
    """Fetch every product via paginated REST calls."""
    products, page = [], 1
    print("🚀 Fetching products from WooCommerce …")
    while True:
        params = {'per_page': 100, 'page': page}
        try:
            r = requests.get(api_url, auth=HTTPBasicAuth(key, secret),
                             params=params, timeout=30)
            r.raise_for_status()
        except requests.exceptions.RequestException as err:
            sys.exit(f"❌ API error on page {page}: {err}")

        batch = r.json()
        if not batch:
            print("✅ All pages fetched.")
            break
        products.extend(batch)
        print(f"   • page {page:>2} → {len(batch)} products")
        page += 1
    return products


def normalise_complex_field(value):
    """
    Convert lists / dicts to a JSON string so Airtable keeps the structure.
    """
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def export_to_csv(products: list[dict], file_path: str):
    if not products:
        print("No products returned – nothing to export.")
        return

    with open(file_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDS_TO_KEEP)
        writer.writeheader()

        for p in products:
            row = {field: '' for field in FIELDS_TO_KEEP}  # default blanks

            # 1️⃣ core product fields
            for core_key in FIELDS_TO_KEEP:
                if core_key in p:
                    row[core_key] = normalise_complex_field(p[core_key])

            # 2️⃣ selected meta-data fields (subscriptions)
            for meta in p.get('meta_data', []):
                k, v = meta.get('key'), meta.get('value')
                if k in FIELDS_TO_KEEP:
                    row[k] = normalise_complex_field(v)

            writer.writerow(row)

    print(f"\n✨ {len(products)} products exported to → {file_path}")


def main():
    data = fetch_all_products(PRODUCTS_API_URL, CONSUMER_KEY, CONSUMER_SECRET)
    export_to_csv(data, OUTPUT_CSV_FILE)


if __name__ == '__main__':
    main()
