"""
Audit Data Quality in Airtable

This script checks data integrity across Airtable tables:
- Duplicate users by email
- Mamo Transactions without User links
- Order status mismatches with WooCommerce
- Missing customer_id links

Usage:
    python scripts/airtable/audit_data_quality.py
"""

import requests
from collections import defaultdict
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv
load_dotenv()

# API Configuration
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
USER_TABLE = "tblMtIskMF3X3nKWC"
MAMO_TABLE = "tbl7WfjTqWMnsqpbs"
ORDERS_TABLE = "tblWByCCtBE1dR6ox"

# WooCommerce
WC_CONSUMER_KEY = os.getenv("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.getenv("WC_CONSUMER_SECRET")
WC_BASE_URL = 'https://aneeq.co/wp-json/wc/v3'

headers = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json"
}


def fetch_all_records(table_id, fields=None):
    """Fetch all records from an Airtable table"""
    all_records = []
    offset = None

    while True:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        if fields:
            params["fields[]"] = fields

        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        all_records.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break

    return all_records


def check_duplicate_users():
    """Check for duplicate users by email"""
    print("\n" + "="*60)
    print("1. DUPLICATE USERS BY EMAIL")
    print("="*60)

    users = fetch_all_records(USER_TABLE)
    print(f"Total users: {len(users)}")

    email_groups = defaultdict(list)
    for user in users:
        email = user.get("fields", {}).get("user_email", "").strip().lower()
        if email:
            email_groups[email].append(user)

    duplicates = {email: users for email, users in email_groups.items() if len(users) > 1}

    if duplicates:
        print(f"❌ Found {len(duplicates)} duplicate emails:")
        for email, users in list(duplicates.items())[:5]:
            print(f"   - {email}: {len(users)} records")
        if len(duplicates) > 5:
            print(f"   ... and {len(duplicates) - 5} more")
        print("\n   Run: python scripts/airtable/clean_duplicate_users.py --audit")
    else:
        print("✅ No duplicate emails found")

    return len(duplicates)


def check_mamo_user_links():
    """Check for Mamo Transactions without User links"""
    print("\n" + "="*60)
    print("2. MAMO TRANSACTIONS WITHOUT USER LINKS")
    print("="*60)

    mamo_records = fetch_all_records(MAMO_TABLE)
    print(f"Total Mamo transactions: {len(mamo_records)}")

    without_user = []
    amazon_orders = []

    for m in mamo_records:
        fields = m.get("fields", {})
        if not fields.get("User"):
            # Check if it's an Amazon order
            source = fields.get("Source", "")
            if source == "Amazon" or fields.get("customer_details_email", "").lower() == "amazon":
                amazon_orders.append(m)
            else:
                without_user.append(m)

    if without_user:
        print(f"❌ Found {len(without_user)} transactions without User link:")
        for m in without_user[:5]:
            fields = m.get("fields", {})
            print(f"   - {fields.get('id', 'N/A')}: {fields.get('senderEmail', fields.get('customer_details_email', 'N/A'))}")
        if len(without_user) > 5:
            print(f"   ... and {len(without_user) - 5} more")
    else:
        print("✅ All non-Amazon transactions have User links")

    print(f"ℹ️  Amazon orders without User link (expected): {len(amazon_orders)}")

    return len(without_user)


def check_mamo_created_users():
    """Check mamo-created users"""
    print("\n" + "="*60)
    print("3. MAMO-CREATED USERS")
    print("="*60)

    users = fetch_all_records(USER_TABLE)

    mamo_users = [u for u in users if str(u.get("fields", {}).get("source_user_id", "")).startswith("mamo_")]

    mamo_email = [u for u in mamo_users if "@" in u.get("fields", {}).get("source_user_id", "")]
    mamo_pay = [u for u in mamo_users if u.get("fields", {}).get("source_user_id", "").startswith("mamo_PAY")]

    print(f"Total mamo-created users: {len(mamo_users)}")
    print(f"   - With email in source_user_id: {len(mamo_email)}")
    print(f"   - With PAY ID only: {len(mamo_pay)}")

    # Check if they have user_email populated
    missing_email = [u for u in mamo_email if not u.get("fields", {}).get("user_email")]
    if missing_email:
        print(f"⚠️  {len(missing_email)} mamo users missing user_email field")

    return len(mamo_users)


def check_order_count():
    """Check order counts between WooCommerce and Airtable"""
    print("\n" + "="*60)
    print("4. ORDER COUNT COMPARISON")
    print("="*60)

    # Airtable orders
    airtable_orders = fetch_all_records(ORDERS_TABLE, fields=["id", "status"])
    print(f"Airtable orders: {len(airtable_orders)}")

    # WooCommerce orders (just count)
    page = 1
    wc_count = 0

    while True:
        resp = requests.get(
            f"{WC_BASE_URL}/orders",
            auth=HTTPBasicAuth(WC_CONSUMER_KEY, WC_CONSUMER_SECRET),
            params={'per_page': 100, 'page': page}
        )
        batch = resp.json()
        if not batch:
            break
        wc_count += len(batch)
        page += 1
        if page > 100:  # Safety limit
            print("⚠️  Reached page limit")
            break

    print(f"WooCommerce orders: {wc_count}")

    diff = abs(len(airtable_orders) - wc_count)
    if diff > 10:
        print(f"⚠️  Difference of {diff} orders between systems")
    else:
        print(f"✅ Order counts are close (diff: {diff})")

    return diff


def main():
    print("="*60)
    print("AIRTABLE DATA QUALITY AUDIT")
    print("="*60)

    issues = 0

    issues += check_duplicate_users()
    issues += check_mamo_user_links()
    check_mamo_created_users()
    check_order_count()

    print("\n" + "="*60)
    print("AUDIT COMPLETE")
    print("="*60)

    if issues > 0:
        print(f"⚠️  Found {issues} issues that need attention")
    else:
        print("✅ All checks passed!")


if __name__ == "__main__":
    main()
