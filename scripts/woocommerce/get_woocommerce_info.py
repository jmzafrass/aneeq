import requests
from requests.auth import HTTPBasicAuth
import json
import os
from dotenv import load_dotenv
load_dotenv()

# WooCommerce API credentials
consumer_key    = os.getenv("WC_CONSUMER_KEY")
consumer_secret = os.getenv("WC_CONSUMER_SECRET")

# WooCommerce Subscriptions API URL
base_url = 'https://aneeq.co/wp-json/wc/v3/subscriptions'

# Fetch up to 5 subscriptions
resp = requests.get(
    base_url,
    auth=HTTPBasicAuth(consumer_key, consumer_secret),
    params={'per_page': 5, 'page': 1}
)
resp.raise_for_status()
subs = resp.json()

# If fewer than 5 exist, this will just take what’s there
last_five = subs[-5:]

results = []
for sub in last_five:
    results.append({
        "id":                       sub["id"],
        "parent_id":                sub["parent_id"],
        "status":                   sub["status"],
        "date_created":             sub["date_created"],
        "date_modified":            sub["date_modified"],
        "date_paid":                sub["date_paid"],
        "date_completed":           sub["date_completed"],
        "customer_id":              sub["customer_id"],
        "number":                   sub["number"],
        "created_via":              sub["created_via"],
        "billing_period":           sub["billing_period"],
        "billing_interval":         sub["billing_interval"],
        "last_payment_date_gmt":    sub.get("last_payment_date_gmt"),
        "next_payment_date_gmt":    sub.get("next_payment_date_gmt"),
        "suspension_count":         sub["suspension_count"],
        "requires_manual_renewal":  sub["requires_manual_renewal"],
        "cancelled_date_gmt":       sub.get("cancelled_date_gmt"),
        "end_date_gmt":             sub.get("end_date_gmt"),
        "line_items": [
            {
                "id":           li["id"],
                "name":         li["name"],
                "product_id":   li["product_id"],
                "variation_id": li["variation_id"],
                "quantity":     li["quantity"],
                "subtotal":     li["subtotal"],
                "total":        li["total"],
                "sku":          li["sku"],
                "price":        li["price"],
            }
            for li in sub["line_items"]
        ]
    })

# Pretty-print the array of the last 5 subscriptions
print(json.dumps(results, indent=2))
