"""
Quiz Dropper Email Campaign - SendGrid

Sends promotional emails to quiz droppers (completed quiz but never purchased)
using SendGrid dynamic templates.

Uses the SAME filtering logic as scripts/segmentation/quiz_droppers.py

Usage:
    # Dry run (preview only, no emails sent)
    python scripts/email/send_quiz_dropper_emails.py --dry-run

    # Send to specific category
    python scripts/email/send_quiz_dropper_emails.py --category "Hair Loss" --dry-run

    # Send for real (with confirmation)
    python scripts/email/send_quiz_dropper_emails.py --execute

    # Limit number of emails (for testing)
    python scripts/email/send_quiz_dropper_emails.py --execute --limit 10
"""

import sys
import os

# Add parent directory to path so we can import from segmentation
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
import argparse
import time
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv

# Import the proven logic from quiz_droppers.py
from segmentation.quiz_droppers import (
    fetch_all_records,
    build_converter_sets,
    build_unsub_sets,
    filter_quiz_droppers,
    deduplicate_droppers,
    normalize_email,
    normalize_phone_for_matching,
    INSTAPRACT_TABLE,
    MAMO_TABLE,
    ORDERS_TABLE,
    USER_TABLE,
)

load_dotenv()

# =============================================================================
# SENDGRID CONFIGURATION
# =============================================================================

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
TEMPLATE_ID = 'd-29a008d0f0f14bec9b320185096ba547'
FROM_EMAIL = 'care@aneeq.co'
FROM_NAME = 'aneeq'
UNSUBSCRIBE_GROUP_ID = 229902


# =============================================================================
# EMAIL FUNCTIONS
# =============================================================================

def send_email(email, first_name, cta_url, dry_run=False):
    """Send email via SendGrid."""
    payload = {
        "from": {"email": FROM_EMAIL, "name": FROM_NAME},
        "personalizations": [{
            "to": [{"email": email}],
            "dynamic_template_data": {
                "first_name": first_name,
                "cta_url": cta_url
            }
        }],
        "template_id": TEMPLATE_ID,
        "asm": {
            "group_id": UNSUBSCRIBE_GROUP_ID
        }
    }

    if dry_run:
        return True, "DRY RUN"

    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload
    )

    if response.ok:
        return True, "SENT"
    else:
        return False, response.text[:100]


def get_email_droppers(category_filter=None):
    """
    Get quiz droppers for email campaign.
    Uses the SAME logic as quiz_droppers.py but filters for valid email + Product Link.

    Returns list of dicts with: email, first_name, cta_url, quiz_type
    """
    print("Fetching data from Airtable...")

    # Fetch quiz records (same fields as quiz_droppers.py)
    print("  - Fetching quiz completions...")
    quiz_fields = ["Email", "Phone Number", "Date", "Product Link", "Quiz Type", "first_name",
                   "User", "never_ordered", "unsubscribed_whattsapp (from User)"]
    quiz_records = fetch_all_records(INSTAPRACT_TABLE, fields=quiz_fields)
    print(f"    Found {len(quiz_records):,} quiz records")

    # Fetch Mamo transactions (captured only)
    print("  - Fetching Mamo transactions...")
    mamo_fields = ["customer_details_email", "customer_details_phone_number", "status"]
    mamo_filter = "{status}='captured'"
    mamo_records = fetch_all_records(MAMO_TABLE, fields=mamo_fields, filter_formula=mamo_filter)
    print(f"    Found {len(mamo_records):,} captured transactions")

    # Fetch WooCommerce orders (completed/processing)
    print("  - Fetching WooCommerce orders...")
    woo_fields = ["Email (Billing)", "Phone (Billing)", "status"]
    woo_filter = "OR({status}='completed',{status}='processing')"
    woo_orders = fetch_all_records(ORDERS_TABLE, fields=woo_fields, filter_formula=woo_filter)
    print(f"    Found {len(woo_orders):,} completed/processing orders")

    # Fetch unsubscribed users
    print("  - Fetching unsubscribed users...")
    user_fields = ["user_email", "phone_standarised", "billing_phone", "unsubscribed_whattsapp"]
    user_filter = "{unsubscribed_whattsapp}=TRUE()"
    unsub_users = fetch_all_records(USER_TABLE, fields=user_fields, filter_formula=user_filter)
    print(f"    Found {len(unsub_users):,} unsubscribed users")

    # Fetch antoine (legacy) customers
    print("  - Fetching antoine (legacy) customers...")
    antoine_fields = ["user_email", "phone_standarised", "billing_phone"]
    antoine_filter = "{is_customer_antoine}=TRUE()"
    antoine_users = fetch_all_records(USER_TABLE, fields=antoine_fields, filter_formula=antoine_filter)
    print(f"    Found {len(antoine_users):,} antoine customers")

    # Build exclusion sets (same as quiz_droppers.py)
    print("\nBuilding exclusion sets...")
    converter_emails, converter_phones = build_converter_sets(mamo_records, woo_orders)

    # Add antoine customers to converter sets
    for u in antoine_users:
        f = u.get("fields", {})
        email = normalize_email(f.get("user_email"))
        if email:
            converter_emails.add(email)
        for phone in [f.get("phone_standarised"), f.get("billing_phone")]:
            norm_phone = normalize_phone_for_matching(phone)
            if norm_phone:
                converter_phones.add(norm_phone)

    print(f"  - Converter emails: {len(converter_emails):,}")
    print(f"  - Converter phones: {len(converter_phones):,}")

    unsub_emails, unsub_phones = build_unsub_sets(unsub_users)
    print(f"  - Unsub emails: {len(unsub_emails):,}")
    print(f"  - Unsub phones: {len(unsub_phones):,}")

    # Filter using the SAME logic as quiz_droppers.py
    print("\nFiltering quiz records...")
    droppers, filter_metrics = filter_quiz_droppers(
        quiz_records,
        converter_emails,
        converter_phones,
        unsub_emails,
        unsub_phones,
        since_date=None
    )

    # Deduplicate using the SAME logic
    print("Deduplicating...")
    unique_droppers, dedup_metrics = deduplicate_droppers(droppers)

    # Now filter for EMAIL campaign requirements:
    # 1. Must have valid email
    # 2. Must have Product Link (cta_url)
    email_droppers = []
    excluded_no_email = 0
    excluded_no_cta = 0
    excluded_wrong_category = 0

    for d in unique_droppers:
        email = d.get('email')
        product_link = None

        # Get Product Link from original record
        for q in quiz_records:
            if q['id'] == d.get('record_id'):
                product_link = q.get('fields', {}).get('Product Link')
                break

        # Must have email
        if not email:
            excluded_no_email += 1
            continue

        # Must have Product Link
        if not product_link:
            excluded_no_cta += 1
            continue

        # Apply category filter if specified
        quiz_type = d.get('quiz_type') or ''
        if category_filter:
            if category_filter.lower() not in quiz_type.lower():
                excluded_wrong_category += 1
                continue

        email_droppers.append({
            'email': email,
            'first_name': (d.get('fname') or '').split()[0] if d.get('fname') else 'there',
            'cta_url': product_link,
            'quiz_type': quiz_type,
        })

    print(f"\n=== EMAIL FILTERING RESULTS ===")
    print(f"  From quiz_droppers logic: {len(unique_droppers)}")
    print(f"  - Excluded (no email): {excluded_no_email}")
    print(f"  - Excluded (no cta_url): {excluded_no_cta}")
    if category_filter:
        print(f"  - Excluded (wrong category): {excluded_wrong_category}")
    print(f"  = Final email droppers: {len(email_droppers)}")

    return email_droppers


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Send quiz dropper email campaign')
    parser.add_argument('--dry-run', action='store_true', help='Preview only, no emails sent')
    parser.add_argument('--execute', action='store_true', help='Actually send emails')
    parser.add_argument('--category', type=str, help='Filter by quiz category (e.g., "Hair Loss")')
    parser.add_argument('--limit', type=int, help='Limit number of emails to send')
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Please specify --dry-run or --execute")
        print("  --dry-run   Preview recipients without sending")
        print("  --execute   Actually send emails")
        return

    print("=" * 60)
    print("QUIZ DROPPER EMAIL CAMPAIGN")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    print(f"Template ID: {TEMPLATE_ID}")
    print(f"From: {FROM_NAME} <{FROM_EMAIL}>")
    if args.category:
        print(f"Category filter: {args.category}")
    if args.limit:
        print(f"Limit: {args.limit}")
    print()

    # Get quiz droppers using the SAME logic as quiz_droppers.py
    droppers = get_email_droppers(category_filter=args.category)

    if not droppers:
        print("No droppers to email.")
        return

    # Apply limit
    if args.limit:
        droppers = droppers[:args.limit]

    # Show category breakdown
    print(f"\n=== BY CATEGORY ===")
    category_counts = Counter(d['quiz_type'] for d in droppers)
    for cat, count in category_counts.most_common():
        print(f"  {cat}: {count}")

    # Preview sample
    print(f"\n=== SAMPLE RECIPIENTS (first 5) ===")
    for d in droppers[:5]:
        print(f"  {d['email'][:40]:40} | {d['first_name']:15} | {d['cta_url'][:50]}")

    # Confirmation for execute mode
    if args.execute:
        print(f"\n⚠️  About to send {len(droppers)} emails!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return

    # Send emails
    print(f"\n=== SENDING EMAILS ===")
    success = 0
    failed = 0

    for i, d in enumerate(droppers):
        ok, msg = send_email(
            email=d['email'],
            first_name=d['first_name'],
            cta_url=d['cta_url'],
            dry_run=args.dry_run
        )

        if ok:
            success += 1
            status = "✓"
        else:
            failed += 1
            status = f"✗ {msg}"

        print(f"  [{i+1}/{len(droppers)}] {d['email'][:40]:40} {status}")

        # Rate limiting (100 emails per second max for SendGrid)
        if not args.dry_run and (i + 1) % 50 == 0:
            time.sleep(1)

    print(f"\n=== SUMMARY ===")
    print(f"  Total: {len(droppers)}")
    print(f"  Success: {success}")
    print(f"  Failed: {failed}")


if __name__ == "__main__":
    main()
