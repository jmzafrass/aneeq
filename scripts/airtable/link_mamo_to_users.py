"""
Link Mamo Transactions to Users

This script finds Mamo Transactions without User links and attempts to link them
using the following priority:
1. If Mamo has Order link → get customer_id → find User by source_user_id
2. Match by senderEmail → find User by user_email
3. Match by senderMobile → find User by phone
4. Create new User with mamo_ prefix if no match

Usage:
    python scripts/airtable/link_mamo_to_users.py --audit           # Audit only
    python scripts/airtable/link_mamo_to_users.py --execute         # Link existing users
    python scripts/airtable/link_mamo_to_users.py --create-users    # Also create new users
"""

import requests
import argparse
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


def fetch_all_records(table_id, fields=None, filter_formula=None):
    """Fetch all records from an Airtable table"""
    all_records = []
    offset = None

    while True:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        if fields:
            for f in fields:
                params.setdefault("fields[]", []).append(f) if isinstance(params.get("fields[]"), list) else None
                params["fields[]"] = fields
        if filter_formula:
            params["filterByFormula"] = filter_formula

        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        all_records.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break

    return all_records


def build_user_lookups(users):
    """Build lookup dictionaries for users"""
    by_source_id = {}
    by_email = {}
    by_phone = {}

    for u in users:
        fields = u.get("fields", {})
        record_id = u["id"]

        # By source_user_id
        sid = fields.get("source_user_id", "")
        if sid:
            by_source_id[str(sid)] = record_id

        # By email
        email = fields.get("user_email", "").strip().lower()
        if email:
            by_email[email] = record_id

        # By phone (normalized)
        phone = fields.get("billing_phone", "").strip()
        if phone:
            # Normalize phone
            phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
            by_phone[phone_clean] = record_id

    return by_source_id, by_email, by_phone


def find_unlinked_mamo():
    """Find Mamo transactions without User link"""
    mamo_records = fetch_all_records(MAMO_TABLE)

    unlinked = []
    amazon = []

    for m in mamo_records:
        fields = m.get("fields", {})
        if not fields.get("User"):
            # Skip Amazon orders
            source = fields.get("Source", "")
            email = fields.get("customer_details_email", "").lower()
            if source == "Amazon" or email == "amazon" or email == "amazon@amazon.com":
                amazon.append(m)
            else:
                unlinked.append(m)

    return unlinked, amazon


def try_link_via_order(mamo, orders_by_id, users_by_source):
    """Try to link Mamo to User via Order's customer_id"""
    order_link = mamo.get("fields", {}).get("order_id", [])
    if not order_link:
        return None

    order_record_id = order_link[0] if isinstance(order_link, list) else order_link

    # Get order's customer_id
    for order_id, order_data in orders_by_id.items():
        if order_data["record_id"] == order_record_id:
            customer_id = order_data.get("customer_id", "")
            if customer_id:
                return users_by_source.get(str(customer_id))

    return None


def audit_unlinked(unlinked, amazon, users_by_source, users_by_email, users_by_phone, orders_by_id):
    """Audit unlinked Mamo transactions"""
    print("\n" + "="*60)
    print("MAMO TRANSACTIONS LINK AUDIT")
    print("="*60)

    print(f"\nTotal unlinked (non-Amazon): {len(unlinked)}")
    print(f"Amazon orders (intentionally unlinked): {len(amazon)}")

    can_link_order = []
    can_link_email = []
    can_link_phone = []
    need_create = []

    for m in unlinked:
        fields = m.get("fields", {})
        mamo_id = m["id"]

        # Try Order link
        user_id = try_link_via_order(m, orders_by_id, users_by_source)
        if user_id:
            can_link_order.append({"mamo_id": mamo_id, "user_id": user_id, "method": "order"})
            continue

        # Try email
        email = fields.get("senderEmail", fields.get("customer_details_email", "")).strip().lower()
        if email and email in users_by_email:
            can_link_email.append({"mamo_id": mamo_id, "user_id": users_by_email[email], "method": "email"})
            continue

        # Try phone
        phone = fields.get("senderMobile", fields.get("customer_details_phone_number", "")).strip()
        if phone:
            phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
            if phone_clean in users_by_phone:
                can_link_phone.append({"mamo_id": mamo_id, "user_id": users_by_phone[phone_clean], "method": "phone"})
                continue

        # Need to create user
        need_create.append({
            "mamo_id": mamo_id,
            "email": email,
            "name": fields.get("senderName", fields.get("customer_details_name", "")),
            "phone": phone,
            "payment_id": fields.get("id", "")
        })

    print(f"\nCan link via Order: {len(can_link_order)}")
    print(f"Can link via Email: {len(can_link_email)}")
    print(f"Can link via Phone: {len(can_link_phone)}")
    print(f"Need to create User: {len(need_create)}")

    return can_link_order + can_link_email + can_link_phone, need_create


def execute_links(to_link):
    """Execute the linking"""
    if not to_link:
        print("✅ Nothing to link!")
        return

    print(f"\nLinking {len(to_link)} Mamo transactions...")

    linked = 0
    for item in to_link:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{MAMO_TABLE}/{item['mamo_id']}"
        data = {"fields": {"User": [item["user_id"]]}}

        resp = requests.patch(url, headers=headers, json=data)
        if resp.status_code == 200:
            linked += 1
        else:
            print(f"   ❌ Failed: {resp.text[:50]}")

        time.sleep(0.2)

    print(f"✅ Linked {linked} transactions")


def create_users_and_link(need_create):
    """Create new users and link Mamo transactions"""
    if not need_create:
        print("✅ No users to create!")
        return

    print(f"\nCreating {len(need_create)} new users...")

    created = 0
    for item in need_create:
        # Determine source_user_id
        if item["email"]:
            source_id = f"mamo_{item['email']}"
        else:
            source_id = f"mamo_{item['payment_id']}"

        # Create user
        url = f"https://api.airtable.com/v0/{BASE_ID}/{USER_TABLE}"
        user_data = {
            "fields": {
                "source_user_id": source_id,
                "user_email": item["email"] if item["email"] else None,
                "billing_phone": item["phone"] if item["phone"] else None
            }
        }
        # Remove None values
        user_data["fields"] = {k: v for k, v in user_data["fields"].items() if v}

        resp = requests.post(url, headers=headers, json=user_data)
        if resp.status_code == 200:
            new_user_id = resp.json()["id"]

            # Link Mamo to user
            mamo_url = f"https://api.airtable.com/v0/{BASE_ID}/{MAMO_TABLE}/{item['mamo_id']}"
            link_resp = requests.patch(mamo_url, headers=headers, json={"fields": {"User": [new_user_id]}})

            if link_resp.status_code == 200:
                created += 1
                print(f"   ✅ Created user {source_id} and linked")
            else:
                print(f"   ⚠️  Created user but failed to link Mamo")
        else:
            print(f"   ❌ Failed to create user: {resp.text[:50]}")

        time.sleep(0.2)

    print(f"✅ Created and linked {created} users")


def main():
    parser = argparse.ArgumentParser(description="Link Mamo Transactions to Users")
    parser.add_argument("--audit", action="store_true", help="Audit only")
    parser.add_argument("--execute", action="store_true", help="Link to existing users")
    parser.add_argument("--create-users", action="store_true", help="Also create new users")
    args = parser.parse_args()

    if not args.audit and not args.execute and not args.create_users:
        print("Please specify --audit, --execute, or --create-users")
        return

    print("Fetching data...")

    # Fetch all data
    users = fetch_all_records(USER_TABLE)
    print(f"Users: {len(users)}")

    orders = fetch_all_records(ORDERS_TABLE, fields=["id", "customer_id"])
    orders_by_id = {
        r.get("fields", {}).get("id", ""): {
            "record_id": r["id"],
            "customer_id": r.get("fields", {}).get("customer_id", "")
        }
        for r in orders if r.get("fields", {}).get("id")
    }
    print(f"Orders: {len(orders_by_id)}")

    # Build lookups
    users_by_source, users_by_email, users_by_phone = build_user_lookups(users)

    # Find unlinked
    unlinked, amazon = find_unlinked_mamo()

    # Audit
    to_link, need_create = audit_unlinked(
        unlinked, amazon, users_by_source, users_by_email, users_by_phone, orders_by_id
    )

    if args.execute or args.create_users:
        execute_links(to_link)

    if args.create_users:
        create_users_and_link(need_create)


if __name__ == "__main__":
    main()
