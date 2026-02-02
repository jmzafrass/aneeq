"""
Sync Order Status from WooCommerce to Airtable

This script compares order statuses between WooCommerce and Airtable,
and updates Airtable to match WooCommerce (source of truth).

Usage:
    python scripts/airtable/sync_order_status.py --audit    # Audit only
    python scripts/airtable/sync_order_status.py --execute  # Execute sync
"""

import requests
import argparse
from requests.auth import HTTPBasicAuth
import time
import os
from dotenv import load_dotenv
load_dotenv()

# API Configuration
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
ORDERS_TABLE = "tblWByCCtBE1dR6ox"

# WooCommerce
WC_CONSUMER_KEY = os.getenv("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.getenv("WC_CONSUMER_SECRET")
WC_BASE_URL = 'https://aneeq.co/wp-json/wc/v3'

headers = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json"
}


def fetch_woocommerce_orders():
    """Fetch all orders from WooCommerce"""
    all_orders = []
    page = 1

    while True:
        resp = requests.get(
            f"{WC_BASE_URL}/orders",
            auth=HTTPBasicAuth(WC_CONSUMER_KEY, WC_CONSUMER_SECRET),
            params={'per_page': 100, 'page': page}
        )
        batch = resp.json()
        if not batch:
            break
        all_orders.extend(batch)
        page += 1
        if page > 100:
            break

    return {str(o['id']): o['status'] for o in all_orders}


def fetch_airtable_orders():
    """Fetch all orders from Airtable"""
    all_orders = []
    offset = None

    while True:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{ORDERS_TABLE}"
        params = {"pageSize": 100, "fields[]": ["id", "status"]}
        if offset:
            params["offset"] = offset

        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        all_orders.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break

    return {
        r.get("fields", {}).get("id", ""): {
            "record_id": r["id"],
            "status": r.get("fields", {}).get("status", "")
        }
        for r in all_orders if r.get("fields", {}).get("id")
    }


def find_mismatches(wc_orders, at_orders):
    """Find orders with different status"""
    mismatches = []

    for order_id, at_data in at_orders.items():
        wc_status = wc_orders.get(order_id)
        if wc_status and wc_status != at_data["status"]:
            mismatches.append({
                "order_id": order_id,
                "record_id": at_data["record_id"],
                "airtable_status": at_data["status"],
                "woocommerce_status": wc_status
            })

    return mismatches


def audit_mismatches(mismatches):
    """Print audit report"""
    print("\n" + "="*60)
    print("STATUS MISMATCH AUDIT")
    print("="*60)

    if not mismatches:
        print("✅ All order statuses match!")
        return

    print(f"Found {len(mismatches)} status mismatches:\n")

    # Group by status transition
    transitions = {}
    for m in mismatches:
        key = f"{m['airtable_status']} → {m['woocommerce_status']}"
        if key not in transitions:
            transitions[key] = []
        transitions[key].append(m['order_id'])

    for transition, orders in transitions.items():
        print(f"   {transition}: {len(orders)} orders")

    print(f"\nSample mismatches:")
    for m in mismatches[:10]:
        print(f"   Order {m['order_id']}: {m['airtable_status']} → {m['woocommerce_status']}")


def execute_sync(mismatches):
    """Update Airtable to match WooCommerce"""
    if not mismatches:
        print("✅ Nothing to sync!")
        return

    print(f"\nUpdating {len(mismatches)} orders...")

    updated = 0
    failed = 0

    for m in mismatches:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{ORDERS_TABLE}/{m['record_id']}"
        data = {"fields": {"status": m["woocommerce_status"]}}

        resp = requests.patch(url, headers=headers, json=data)
        if resp.status_code == 200:
            updated += 1
            if updated % 50 == 0:
                print(f"   Updated {updated}/{len(mismatches)}...")
        else:
            failed += 1
            print(f"   ❌ Failed order {m['order_id']}: {resp.text[:50]}")

        time.sleep(0.2)

    print(f"\n✅ Updated {updated} orders")
    if failed:
        print(f"❌ Failed {failed} orders")


def main():
    parser = argparse.ArgumentParser(description="Sync order status from WooCommerce to Airtable")
    parser.add_argument("--audit", action="store_true", help="Audit only")
    parser.add_argument("--execute", action="store_true", help="Execute sync")
    args = parser.parse_args()

    if not args.audit and not args.execute:
        print("Please specify --audit or --execute")
        return

    print("Fetching WooCommerce orders...")
    wc_orders = fetch_woocommerce_orders()
    print(f"WooCommerce orders: {len(wc_orders)}")

    print("Fetching Airtable orders...")
    at_orders = fetch_airtable_orders()
    print(f"Airtable orders: {len(at_orders)}")

    print("Finding mismatches...")
    mismatches = find_mismatches(wc_orders, at_orders)
    print(f"Mismatches found: {len(mismatches)}")

    if args.audit:
        audit_mismatches(mismatches)
    elif args.execute:
        audit_mismatches(mismatches)
        execute_sync(mismatches)


if __name__ == "__main__":
    main()
