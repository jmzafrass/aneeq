"""
Clean Duplicate Users in Airtable

This script finds and merges duplicate User records based on user_email.
Priority: Keep user with numeric source_user_id (WooCommerce customer ID)

Before deleting duplicates, it migrates all linked records (Orders, Mamo Transactions)
to the user being kept.

Usage:
    python scripts/airtable/clean_duplicate_users.py --audit    # Audit only, no changes
    python scripts/airtable/clean_duplicate_users.py --execute  # Execute cleanup
"""

import requests
import argparse
from collections import defaultdict
import time
import os
from dotenv import load_dotenv
load_dotenv()

# API Configuration
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
USER_TABLE = "tblMtIskMF3X3nKWC"
MAMO_TABLE = "tbl7WfjTqWMnsqpbs"
ORDERS_TABLE = "tblWByCCtBE1dR6ox"

headers = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json"
}


def fetch_all_users():
    """Fetch all users from Airtable"""
    all_users = []
    offset = None

    while True:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{USER_TABLE}"
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset

        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        all_users.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break

    return all_users


def find_duplicates(users):
    """Group users by email and find duplicates"""
    email_groups = defaultdict(list)

    for user in users:
        email = user.get("fields", {}).get("user_email", "").strip().lower()
        if email:
            email_groups[email].append(user)

    return {email: users for email, users in email_groups.items() if len(users) > 1}


def select_user_to_keep(users):
    """Select which user to keep based on priority rules"""
    # Priority: numeric source_user_id (WooCommerce customer ID)
    target_user = None

    for u in users:
        sid = str(u.get("fields", {}).get("source_user_id", ""))
        if sid.isdigit():
            if target_user is None:
                target_user = u
            else:
                # Multiple numeric - keep the one with more linked records
                curr_links = len(target_user.get("fields", {}).get("Mamo Transactions", []) or []) + \
                             len(target_user.get("fields", {}).get("Orders", []) or [])
                new_links = len(u.get("fields", {}).get("Mamo Transactions", []) or []) + \
                            len(u.get("fields", {}).get("Orders", []) or [])
                if new_links > curr_links:
                    target_user = u

    # Fallback to first user if no numeric source_user_id
    if not target_user:
        target_user = users[0]

    return target_user


def audit_duplicates(duplicates):
    """Print audit report of duplicates"""
    print("\n" + "="*80)
    print("DUPLICATE USER AUDIT REPORT")
    print("="*80)

    total_to_delete = 0
    total_mamo_migrate = 0
    total_orders_migrate = 0

    for email, users in duplicates.items():
        target = select_user_to_keep(users)

        print(f"\n📧 {email}")
        print(f"   KEEP: {target['id']} (source: {target.get('fields', {}).get('source_user_id', 'N/A')})")

        for u in users:
            if u["id"] == target["id"]:
                continue

            mamo = u.get("fields", {}).get("Mamo Transactions", []) or []
            orders = u.get("fields", {}).get("Orders", []) or []

            print(f"   DELETE: {u['id']} (source: {u.get('fields', {}).get('source_user_id', 'N/A')}) - {len(mamo)} Mamo, {len(orders)} Orders to migrate")

            total_to_delete += 1
            total_mamo_migrate += len(mamo)
            total_orders_migrate += len(orders)

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Duplicate email groups: {len(duplicates)}")
    print(f"Users to delete: {total_to_delete}")
    print(f"Mamo Transactions to migrate: {total_mamo_migrate}")
    print(f"Orders to migrate: {total_orders_migrate}")

    return total_to_delete


def execute_cleanup(duplicates):
    """Execute the cleanup - migrate records and delete duplicates"""
    mamo_migrated = 0
    orders_migrated = 0
    deleted = 0

    for email, users in duplicates.items():
        target = select_user_to_keep(users)
        target_id = target["id"]

        print(f"\n📧 {email}")
        print(f"   KEEP: {target_id}")

        for u in users:
            if u["id"] == target_id:
                continue

            # Migrate Mamo Transactions
            mamo_txns = u.get("fields", {}).get("Mamo Transactions", []) or []
            for txn_id in mamo_txns:
                update_url = f"https://api.airtable.com/v0/{BASE_ID}/{MAMO_TABLE}/{txn_id}"
                update_data = {"fields": {"User": [target_id]}}
                resp = requests.patch(update_url, headers=headers, json=update_data)
                if resp.status_code == 200:
                    print(f"   ✅ Migrated Mamo txn {txn_id}")
                    mamo_migrated += 1
                else:
                    print(f"   ❌ Failed Mamo {txn_id}: {resp.text[:50]}")
                time.sleep(0.2)

            # Migrate Orders
            orders = u.get("fields", {}).get("Orders", []) or []
            for order_id in orders:
                update_url = f"https://api.airtable.com/v0/{BASE_ID}/{ORDERS_TABLE}/{order_id}"
                update_data = {"fields": {"User": [target_id]}}
                resp = requests.patch(update_url, headers=headers, json=update_data)
                if resp.status_code == 200:
                    print(f"   ✅ Migrated Order {order_id}")
                    orders_migrated += 1
                else:
                    print(f"   ❌ Failed Order {order_id}: {resp.text[:50]}")
                time.sleep(0.2)

            # Delete duplicate
            delete_url = f"https://api.airtable.com/v0/{BASE_ID}/{USER_TABLE}/{u['id']}"
            resp = requests.delete(delete_url, headers=headers)
            if resp.status_code == 200:
                print(f"   🗑️  Deleted: {u['id']}")
                deleted += 1
            else:
                print(f"   ❌ Delete failed {u['id']}: {resp.text[:50]}")
            time.sleep(0.2)

    print("\n" + "="*60)
    print("CLEANUP COMPLETE")
    print("="*60)
    print(f"✅ Migrated {mamo_migrated} Mamo transactions")
    print(f"✅ Migrated {orders_migrated} Orders")
    print(f"🗑️  Deleted {deleted} duplicate users")


def main():
    parser = argparse.ArgumentParser(description="Clean duplicate users in Airtable")
    parser.add_argument("--audit", action="store_true", help="Audit only, no changes")
    parser.add_argument("--execute", action="store_true", help="Execute cleanup")
    args = parser.parse_args()

    if not args.audit and not args.execute:
        print("Please specify --audit or --execute")
        return

    print("Fetching all users...")
    users = fetch_all_users()
    print(f"Total users: {len(users)}")

    print("Finding duplicates...")
    duplicates = find_duplicates(users)
    print(f"Duplicate email groups: {len(duplicates)}")

    if not duplicates:
        print("✅ No duplicates found!")
        return

    if args.audit:
        audit_duplicates(duplicates)
    elif args.execute:
        print("\n⚠️  EXECUTING CLEANUP - This will modify data!")
        execute_cleanup(duplicates)


if __name__ == "__main__":
    main()
