import os
import csv
import requests
from requests.auth import HTTPBasicAuth
from datetime import timedelta, timezone
from dateutil.parser import isoparse  # pip install python-dateutil
from dotenv import load_dotenv
load_dotenv()

# ─── CONFIG ────────────────────────────────────────────────────────────────────

# It's safest to keep your keys out of source:
WC_BASE_URL      = os.getenv('WC_BASE_URL',      'https://aneeq.co/wp-json/wc/v3/subscriptions')
WC_CONSUMER_KEY    = os.getenv("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.getenv("WC_CONSUMER_SECRET")

PER_PAGE = 100   # max allowed by WooCommerce REST API is usually 100

# Dubai timezone offset (UTC+4)
DUBAI_OFFSET = timedelta(hours=4)

# ─── HELPERS ───────────────────────────────────────────────────────────────────

def extract_meta_value(meta_data, key):
    """Extract value from meta_data array by key"""
    for item in meta_data:
        if item.get('key') == key:
            return item.get('value', '')
    return ''

def extract_line_items(line_items):
    """Extract line items as a formatted string"""
    items = []
    for item in line_items:
        items.append(f"{item.get('name', '')} (ID:{item.get('product_id', '')}, Var:{item.get('variation_id', '')}, Qty:{item.get('quantity', '')}, Price:{item.get('price', '')})")
    return ' | '.join(items)

def fetch_all_active_subscriptions():
    """Fetch all active subscriptions regardless of next payment date."""
    print("Fetching all active WooCommerce subscriptions...")
    print()

    page = 1
    matches = []

    while True:
        params = {
            'per_page': PER_PAGE,
            'page': page,
            'status': 'active'  # Filter for active subscriptions on server side
        }
        resp = requests.get(
            WC_BASE_URL,
            auth=HTTPBasicAuth(WC_CONSUMER_KEY, WC_CONSUMER_SECRET),
            params=params,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break

        for sub in batch:
            # Convert next payment date to Dubai time if available
            next_payment_str = sub.get('next_payment_date_gmt')
            if next_payment_str:
                next_payment = isoparse(next_payment_str)
                # Ensure next_payment is timezone-aware (convert to UTC if naive)
                if next_payment.tzinfo is None:
                    next_payment = next_payment.replace(tzinfo=timezone.utc)

                # Convert to Dubai time for display
                next_payment_dubai = next_payment + DUBAI_OFFSET
                sub['_next_payment_dubai_time'] = next_payment_dubai.isoformat()
            else:
                sub['_next_payment_dubai_time'] = ''

            # Keep all active subscriptions
            matches.append(sub)

        page += 1

    return matches

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    subs = fetch_all_active_subscriptions()
    
    # Define CSV headers
    headers = [
        # Record IDs
        'subscription_id',
        'parent_id',
        'number',

        # Account
        'customer_id',

        # Lifecycle status
        'status',

        # Timestamps (UTC)
        'date_created_gmt',
        'date_paid_gmt',
        'last_payment_date_gmt',
        'next_payment_date_gmt',
        'next_payment_date_dubai',  # Added Dubai time
        'end_date_gmt',

        # Payment rails
        'payment_method',
        'payment_method_title',

        # Order → Mamopay handshake
        'order_key',

        # Mamopay tokens & links
        'mamopay_ws_payment_token',
        'mamo_pay_payment_link_id',
        'mamo_pay_payment_link_type',
        'mamo_pay_payment_url',
        'mamo_pay_order_total_hash',

        # Financials
        'currency',
        'total',
        'shipping_total',
        'discount_total',

        # Item details
        'line_items',

        # Additional useful fields
        'billing_email',
        'billing_name',
        'billing_phone'
    ]
    
    # Write CSV
    csv_filename = 'subscriptions_mamopay_reconciliation.csv'
    with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        
        for sub in subs:
            row = {
                # Record IDs
                'subscription_id': sub.get('id', ''),
                'parent_id': sub.get('parent_id', ''),
                'number': sub.get('number', ''),
                
                # Account
                'customer_id': sub.get('customer_id', ''),
                
                # Lifecycle status
                'status': sub.get('status', ''),
                
                # Timestamps
                'date_created_gmt': sub.get('date_created_gmt', ''),
                'date_paid_gmt': sub.get('date_paid_gmt', ''),
                'last_payment_date_gmt': sub.get('last_payment_date_gmt', ''),
                'next_payment_date_gmt': sub.get('next_payment_date_gmt', ''),
                'next_payment_date_dubai': sub.get('_next_payment_dubai_time', ''),
                'end_date_gmt': sub.get('end_date_gmt', ''),
                
                # Payment rails
                'payment_method': sub.get('payment_method', ''),
                'payment_method_title': sub.get('payment_method_title', ''),
                
                # Order key
                'order_key': sub.get('order_key', ''),
                
                # Extract Mamopay fields from meta_data
                'mamopay_ws_payment_token': extract_meta_value(sub.get('meta_data', []), '_mamopay_ws_payment_token'),
                'mamo_pay_payment_link_id': extract_meta_value(sub.get('meta_data', []), '_mamo_pay_payment_link_id'),
                'mamo_pay_payment_link_type': extract_meta_value(sub.get('meta_data', []), '_mamo_pay_payment_link_type'),
                'mamo_pay_payment_url': extract_meta_value(sub.get('meta_data', []), '_mamo_pay_payment_url'),
                'mamo_pay_order_total_hash': extract_meta_value(sub.get('meta_data', []), '_mamo_pay_order_total_hash'),
                
                # Financials
                'currency': sub.get('currency', ''),
                'total': sub.get('total', ''),
                'shipping_total': sub.get('shipping_total', ''),
                'discount_total': sub.get('discount_total', ''),
                
                # Line items
                'line_items': extract_line_items(sub.get('line_items', [])),
                
                # Additional fields from billing
                'billing_email': sub.get('billing', {}).get('email', ''),
                'billing_name': f"{sub.get('billing', {}).get('first_name', '')} {sub.get('billing', {}).get('last_name', '')}".strip(),
                'billing_phone': sub.get('billing', {}).get('phone', '')
            }
            writer.writerow(row)
    
    print(f"Found {len(subs)} active subscriptions")
    print(f"Results saved to: {csv_filename}")
