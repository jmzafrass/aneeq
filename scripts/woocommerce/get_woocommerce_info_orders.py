import requests
from requests.auth import HTTPBasicAuth
import csv
import os
from dotenv import load_dotenv
load_dotenv()

# WooCommerce API credentials
consumer_key = os.getenv("WC_CONSUMER_KEY")
consumer_secret = os.getenv("WC_CONSUMER_SECRET")

# Base URL for WooCommerce orders
base_url = 'https://aneeq.co/wp-json/wc/v3/orders'

# Output CSV
csv_file_path = "woocommerce_orders.csv"
fieldnames = ['id', 'created_via', 'transaction_id', 'customer_id', 'payment_method', 'total', 'subtotal', 'discount_total', 'status', 'product_ids']

# Initialize results list
all_orders = []
page = 1

while True:
    params = {'per_page': 100, 'page': page}
    response = requests.get(base_url, auth=HTTPBasicAuth(consumer_key, consumer_secret), params=params)
    response.raise_for_status()
    orders = response.json()

    if not orders:
        break

    for order in orders:
        # Extract product IDs from line items
        line_items = order.get('line_items', [])
        product_ids = [str(item.get('product_id', '')) for item in line_items]
        product_ids_str = ','.join(product_ids)

        all_orders.append({
            'id': order['id'],
            'created_via': order.get('created_via', ''),
            'transaction_id': order.get('transaction_id', ''),
            'customer_id': order.get('customer_id', ''),
            'payment_method': order.get('payment_method', ''),
            'total': order.get('total', ''),
            'subtotal': order.get('subtotal', ''),
            'discount_total': order.get('discount_total', ''),
            'status': order.get('status', ''),
            'product_ids': product_ids_str
        })

    page += 1

# Write CSV
with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_orders)

print(f"✅ Exported {len(all_orders)} orders to {csv_file_path}")
