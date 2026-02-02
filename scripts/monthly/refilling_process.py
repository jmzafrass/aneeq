"""
Monthly Subscription Refilling Process

This script handles the monthly process of generating subscription refill records:
1. Fetch active subscribers from MamoPay for target month
2. Fetch active subscribers from WooCommerce for target month
3. Deduplicate (MamoPay takes priority)
4. Match with Airtable Users
5. Create Subscriptions records
6. Create Magenta records for pharmacy

Usage:
    python scripts/monthly/refilling_process.py --month 2026-02 --audit
    python scripts/monthly/refilling_process.py --month 2026-02 --execute

Documentation: docs/refilling_process.md
"""

import requests
import argparse
from requests.auth import HTTPBasicAuth
from datetime import datetime, timezone, timedelta
import time
import os
from dotenv import load_dotenv
load_dotenv()

# API Configuration
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
USER_TABLE = "tblMtIskMF3X3nKWC"
SUBSCRIPTIONS_TABLE = "tblf0AONAdsaBwo8P"
MAGENTA_TABLE = "tbl5MDz6ZRUosdsEQ"

# MamoPay
MAMO_API_KEY = os.getenv("MAMO_API_KEY")
MAMO_BASE_URL = 'https://business.mamopay.com/manage_api/v1'

# WooCommerce
WC_CONSUMER_KEY = os.getenv("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.getenv("WC_CONSUMER_SECRET")
WC_BASE_URL = 'https://aneeq.co/wp-json/wc/v3'

DUBAI_OFFSET = timedelta(hours=4)

airtable_headers = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json"
}

mamo_headers = {
    "accept": "application/json",
    "Authorization": f"Bearer {MAMO_API_KEY}"
}


def parse_month(month_str):
    """Parse month string like '2026-02' into year and month"""
    parts = month_str.split("-")
    return int(parts[0]), int(parts[1])


def fetch_mamo_subscribers(target_year, target_month):
    """Fetch active MamoPay subscribers for target month"""
    print("Fetching MamoPay subscription IDs...")

    # Get all subscription IDs from payment links
    page = 1
    subscription_ids = set()

    while True:
        resp = requests.get(
            f"{MAMO_BASE_URL}/links",
            headers=mamo_headers,
            params={'page': page, 'per_page': 100}
        )
        data = resp.json()
        batch = data.get('data', [])
        if not batch:
            break

        for item in batch:
            subscription = item.get('subscription')
            if subscription and isinstance(subscription, dict):
                sub_id = subscription.get('identifier')
                if sub_id:
                    subscription_ids.add(sub_id)

        meta = data.get('pagination_meta', {})
        if page >= meta.get('total_pages', 1):
            break
        page += 1

    print(f"Found {len(subscription_ids)} subscription types")

    # Fetch subscribers for each subscription
    all_subscribers = []
    for sid in subscription_ids:
        resp = requests.get(
            f"{MAMO_BASE_URL}/subscriptions/{sid}/subscribers",
            headers=mamo_headers,
            params={'per_page': 100}
        )
        if resp.status_code == 200:
            batch = resp.json()
            if isinstance(batch, list):
                for sub in batch:
                    sub['subscription_id'] = sid
                    all_subscribers.append(sub)
        time.sleep(0.1)

    print(f"Total MamoPay subscribers: {len(all_subscribers)}")

    # Filter for active and target month
    target_prefix = f"{target_year}-{target_month:02d}"
    active = [s for s in all_subscribers if s.get('status', '').lower() == 'active']
    filtered = [s for s in active if s.get('next_payment_date', '').startswith(target_prefix)]

    print(f"Active subscribers: {len(active)}")
    print(f"Subscribers in {target_prefix}: {len(filtered)}")

    return filtered


def fetch_woocommerce_subscribers(target_year, target_month):
    """Fetch active WooCommerce subscriptions for target month"""
    print("Fetching WooCommerce subscriptions...")

    page = 1
    all_subs = []

    while True:
        resp = requests.get(
            f"{WC_BASE_URL}/subscriptions",
            auth=HTTPBasicAuth(WC_CONSUMER_KEY, WC_CONSUMER_SECRET),
            params={'per_page': 100, 'page': page, 'status': 'active'}
        )
        batch = resp.json()
        if not batch:
            break
        all_subs.extend(batch)
        page += 1

    print(f"Total WooCommerce active subscriptions: {len(all_subs)}")

    # Filter for target month (convert UTC to Dubai time)
    filtered = []
    for sub in all_subs:
        next_payment = sub.get('next_payment_date_gmt', '')
        if next_payment:
            try:
                # Parse ISO datetime
                dt = datetime.fromisoformat(next_payment.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt_dubai = dt + DUBAI_OFFSET

                if dt_dubai.year == target_year and dt_dubai.month == target_month:
                    sub['_next_payment_dubai'] = dt_dubai.strftime('%Y-%m-%d')
                    filtered.append(sub)
            except:
                pass

    print(f"Subscriptions in {target_year}-{target_month:02d}: {len(filtered)}")

    return filtered


def fetch_airtable_users():
    """Fetch all users from Airtable"""
    print("Fetching Airtable users...")

    all_users = []
    offset = None

    while True:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{USER_TABLE}"
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset

        resp = requests.get(url, headers=airtable_headers, params=params)
        data = resp.json()
        all_users.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break

    print(f"Total Airtable users: {len(all_users)}")

    # Build email lookup
    user_data = {}
    for u in all_users:
        fields = u.get("fields", {})
        email = fields.get("user_email", "").strip().lower()
        if email:
            user_data[email] = {
                "record_id": u["id"],
                "first_name": fields.get("billing_first_name", ""),
                "last_name": fields.get("billing_last_name", ""),
                "phone": fields.get("billing_phone", "")
            }

    return user_data


def combine_subscribers(mamo_subs, woo_subs, user_data):
    """Combine and deduplicate subscribers (MamoPay priority)"""
    combined = {}

    # MamoPay first
    for sub in mamo_subs:
        customer = sub.get('customer', {})
        email = customer.get('email', '').lower().strip()
        if email and email not in combined:
            user = user_data.get(email, {})
            combined[email] = {
                'id': sub.get('id', ''),
                'customer_email': email,
                'customer_name': customer.get('name', ''),
                'next_payment_date': sub.get('next_payment_date', ''),
                'status': 'Active',
                'trigger_by': 'MAMO',
                'user_record_id': user.get('record_id'),
                'phone': user.get('phone', ''),
                'first_name': user.get('first_name', ''),
                'last_name': user.get('last_name', '')
            }

    mamo_count = len(combined)

    # WooCommerce (only if not in MamoPay)
    for sub in woo_subs:
        billing = sub.get('billing', {})
        email = billing.get('email', '').lower().strip()
        if email and email not in combined:
            user = user_data.get(email, {})
            combined[email] = {
                'id': str(sub.get('id', '')),
                'customer_email': email,
                'customer_name': f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip(),
                'next_payment_date': sub.get('_next_payment_dubai', ''),
                'status': 'active',
                'trigger_by': 'WOO',
                'user_record_id': user.get('record_id'),
                'phone': billing.get('phone', '') or user.get('phone', ''),
                'first_name': billing.get('first_name', '') or user.get('first_name', ''),
                'last_name': billing.get('last_name', '') or user.get('last_name', '')
            }

    woo_count = len(combined) - mamo_count

    print(f"\nCombined: {len(combined)} unique subscribers")
    print(f"  - From MamoPay: {mamo_count}")
    print(f"  - From WooCommerce: {woo_count}")

    # Count with/without user
    with_user = len([s for s in combined.values() if s.get('user_record_id')])
    without_user = len(combined) - with_user
    print(f"  - With Airtable User: {with_user}")
    print(f"  - Without Airtable User: {without_user}")

    return combined


def audit_combined(combined):
    """Print audit of combined subscribers"""
    print("\n" + "="*60)
    print("SUBSCRIPTION AUDIT")
    print("="*60)

    # Group by trigger
    mamo = [s for s in combined.values() if s['trigger_by'] == 'MAMO']
    woo = [s for s in combined.values() if s['trigger_by'] == 'WOO']

    print(f"\nMamoPay subscribers: {len(mamo)}")
    print(f"WooCommerce subscribers: {len(woo)}")

    # Missing user
    missing_user = [s for s in combined.values() if not s.get('user_record_id')]
    if missing_user:
        print(f"\n⚠️  Subscribers without Airtable User ({len(missing_user)}):")
        for s in missing_user[:5]:
            print(f"   - {s['customer_email']}")
        if len(missing_user) > 5:
            print(f"   ... and {len(missing_user) - 5} more")


def create_subscriptions_records(combined):
    """Create Subscriptions records in Airtable"""
    print("\nCreating Subscriptions records...")

    records_to_create = []
    for email, sub in combined.items():
        fields = {
            'id': sub['id'],
            'customer_email': sub['customer_email'],
            'customer_name': sub['customer_name'],
            'next_payment_date': sub['next_payment_date'],
            'status': sub['status'],
            'Trigger by': sub['trigger_by']
        }
        if sub['user_record_id']:
            fields['User'] = [sub['user_record_id']]

        records_to_create.append({'fields': fields})

    # Batch create
    url = f"https://api.airtable.com/v0/{BASE_ID}/{SUBSCRIPTIONS_TABLE}"
    created = 0

    for i in range(0, len(records_to_create), 10):
        batch = records_to_create[i:i+10]
        resp = requests.post(url, headers=airtable_headers, json={'records': batch})
        if resp.status_code == 200:
            created += len(batch)
        else:
            print(f"   ❌ Batch failed: {resp.text[:50]}")
        time.sleep(0.2)

    print(f"✅ Created {created} Subscriptions records")
    return created


def create_magenta_records(combined):
    """Create Magenta records for pharmacy"""
    print("\nCreating Magenta records...")

    # Only create for subscribers with User link
    with_user = [s for s in combined.values() if s.get('user_record_id')]

    records_to_create = []
    for sub in with_user:
        fields = {
            'User': [sub['user_record_id']],
            'Status': '✅ RX Received',
            'Trigger by': sub['trigger_by'],
            'Type of delivery': 'Refill',
            'Refill ': 'Yes',  # Note: field has trailing space
            'Date': sub.get('next_payment_date', ''),
            'email_input': sub.get('customer_email', '')
        }
        records_to_create.append({'fields': fields})

    # Batch create
    url = f"https://api.airtable.com/v0/{BASE_ID}/{MAGENTA_TABLE}"
    created = 0

    for i in range(0, len(records_to_create), 10):
        batch = records_to_create[i:i+10]
        resp = requests.post(url, headers=airtable_headers, json={'records': batch})
        if resp.status_code == 200:
            created += len(batch)
        else:
            print(f"   ❌ Batch failed: {resp.text[:50]}")
        time.sleep(0.2)

    print(f"✅ Created {created} Magenta records")
    print(f"⚠️  Skipped {len(combined) - len(with_user)} without User link")
    return created


def main():
    parser = argparse.ArgumentParser(description="Monthly Subscription Refilling Process")
    parser.add_argument("--month", required=True, help="Target month (YYYY-MM)")
    parser.add_argument("--audit", action="store_true", help="Audit only")
    parser.add_argument("--execute", action="store_true", help="Execute creation")
    args = parser.parse_args()

    if not args.audit and not args.execute:
        print("Please specify --audit or --execute")
        return

    target_year, target_month = parse_month(args.month)
    print(f"\n{'='*60}")
    print(f"MONTHLY REFILLING PROCESS - {args.month}")
    print(f"{'='*60}")

    # Fetch data
    mamo_subs = fetch_mamo_subscribers(target_year, target_month)
    woo_subs = fetch_woocommerce_subscribers(target_year, target_month)
    user_data = fetch_airtable_users()

    # Combine
    combined = combine_subscribers(mamo_subs, woo_subs, user_data)

    # Audit
    audit_combined(combined)

    if args.execute:
        print("\n" + "="*60)
        print("EXECUTING...")
        print("="*60)
        create_subscriptions_records(combined)
        create_magenta_records(combined)

    print("\n" + "="*60)
    print("COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
