#!/usr/bin/env python3
"""
Campaign Manager - Weekly Marketing Campaigns

Generates and sends marketing campaigns to different customer segments
via Email (SendGrid) and WhatsApp (Gupshup CSV).

SEGMENTS:
  - quiz_droppers: Completed quiz but never purchased
  - dormant: Customers with no orders in 90+ days
  - active: Active subscribers + ordered in last 30 days

USAGE:
    # List all segments with their config
    python scripts/segmentation/campaign_manager.py --list

    # Generate CSVs only (no emails sent)
    python scripts/segmentation/campaign_manager.py --segment quiz_droppers --csv-only
    python scripts/segmentation/campaign_manager.py --segment dormant --csv-only
    python scripts/segmentation/campaign_manager.py --segment active --csv-only
    python scripts/segmentation/campaign_manager.py --segment all --csv-only

    # Send emails only (uses existing segment logic)
    python scripts/segmentation/campaign_manager.py --segment quiz_droppers --email-only
    python scripts/segmentation/campaign_manager.py --segment dormant --email-only
    python scripts/segmentation/campaign_manager.py --segment active --email-only

    # Full campaign (CSV + Email)
    python scripts/segmentation/campaign_manager.py --segment quiz_droppers --execute
    python scripts/segmentation/campaign_manager.py --segment all --execute

    # Dry run (preview without sending)
    python scripts/segmentation/campaign_manager.py --segment active --dry-run

    # Limit emails (for testing)
    python scripts/segmentation/campaign_manager.py --segment active --execute --limit 10

Author: Marketing Automation
Version: 1.0
"""

import os
import sys
import csv
import re
import argparse
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

# Airtable
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")

TABLES = {
    'instapract': 'tbleLSKMeFP1LF5hT',
    'user': 'tblMtIskMF3X3nKWC',
    'mamo': 'tbl7WfjTqWMnsqpbs',
    'orders': 'tblWByCCtBE1dR6ox',
    'subscriptions': 'tblf0AONAdsaBwo8P',
}

# SendGrid
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = 'care@aneeq.co'
FROM_NAME = 'aneeq'
UNSUBSCRIBE_GROUP_ID = 229902

# Output
OUTPUT_DIR = '/Users/juanmanuelzafra/Desktop/projects/aneeq/data/csv/gupshup'

# =============================================================================
# SEGMENT CONFIGURATION
# =============================================================================

SEGMENTS = {
    'quiz_droppers': {
        'name': 'Quiz Droppers',
        'description': 'Completed quiz but never purchased',
        'template_id': 'd-29a008d0f0f14bec9b320185096ba547',
        'cta_url': None,  # Dynamic - uses Product Link from quiz
        'cta_field': 'Product Link',  # Field to use for CTA
    },
    'dormant': {
        'name': 'Dormant Customers',
        'description': 'No orders in 90+ days',
        'template_id': 'd-baa3779d21314c15a8b271c063d2d378',
        'cta_url': 'https://aneeq.co/',
        'airtable_view': 'Dormant>90days',
    },
    'active': {
        'name': 'Active Customers',
        'description': 'Active subscribers + ordered in last 30 days',
        'template_id': 'd-2b48f06507c642ccaf929177d9ce6b3f',
        'cta_url': 'https://aneeq.co/',
    },
}

# =============================================================================
# TEST EMAIL PATTERNS
# =============================================================================

TEST_PATTERNS = [
    r'^test[@.]', r'@test\.com$', r'@example\.com$',
    r'^fake[@.]', r'^demo[@.]', r'@mailinator\.com$',
    r'@aneeq\.co$', r'^test\d*@', r'@yopmail\.com$',
    r'@tempmail\.', r'^amazon$', r'@amazon\.com$',
]


def is_test_email(email: str) -> bool:
    """Check if email matches test/fake patterns."""
    if not email:
        return True
    email_lower = email.strip().lower()
    for pattern in TEST_PATTERNS:
        if re.search(pattern, email_lower):
            return True
    return False


def normalize_email(email: str) -> Optional[str]:
    """Normalize email for matching."""
    if not email:
        return None
    return email.strip().lower()


def normalize_phone(phone) -> Optional[str]:
    """Normalize phone to digits-only format."""
    if not phone:
        return None
    phone_str = str(phone).strip()
    if '.' in phone_str:
        phone_str = phone_str.split('.')[0]
    digits = re.sub(r'\D', '', phone_str)
    if not digits or len(digits) < 8:
        return None
    # UAE normalization
    if digits.startswith('00971'):
        digits = digits[2:]
    elif digits.startswith('0') and len(digits) == 10:
        digits = '971' + digits[1:]
    elif len(digits) == 9 and digits[0] == '5':
        digits = '971' + digits
    if len(digits) < 9 or len(digits) > 15:
        return None
    return digits


# =============================================================================
# AIRTABLE API
# =============================================================================

def get_headers():
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }


def fetch_all_records(table_id: str, fields: List[str] = None,
                      filter_formula: str = None, view: str = None) -> List[Dict]:
    """Fetch all records from Airtable with pagination."""
    records = []
    offset = None

    while True:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        if fields:
            params["fields[]"] = fields
        if filter_formula:
            params["filterByFormula"] = filter_formula
        if view:
            params["view"] = view

        resp = requests.get(url, headers=get_headers(), params=params)
        if resp.status_code != 200:
            print(f"  Error fetching: {resp.text[:100]}")
            break

        data = resp.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break

    return records


# =============================================================================
# SENDGRID EMAIL
# =============================================================================

def send_email(email: str, first_name: str, cta_url: str, template_id: str,
               dry_run: bool = False) -> Tuple[bool, str]:
    """Send email via SendGrid."""
    payload = {
        "from": {"email": FROM_EMAIL, "name": FROM_NAME},
        "personalizations": [{
            "to": [{"email": email}],
            "dynamic_template_data": {
                "first_name": first_name or "there",
                "cta_url": cta_url
            }
        }],
        "template_id": template_id,
        "asm": {"group_id": UNSUBSCRIBE_GROUP_ID}
    }

    if dry_run:
        return True, "DRY RUN"

    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload
    )

    if resp.ok:
        return True, "SENT"
    return False, resp.text[:100]


# =============================================================================
# EXCLUSION SETS
# =============================================================================

def build_converter_sets() -> Tuple[Set[str], Set[str]]:
    """Build sets of emails/phones that have made purchases."""
    converter_emails = set()
    converter_phones = set()

    # Mamo transactions (captured)
    mamo = fetch_all_records(
        TABLES['mamo'],
        fields=["customer_details_email", "customer_details_phone_number"],
        filter_formula="{status}='captured'"
    )
    for m in mamo:
        f = m.get("fields", {})
        if email := normalize_email(f.get("customer_details_email")):
            converter_emails.add(email)
        if phone := normalize_phone(f.get("customer_details_phone_number")):
            converter_phones.add(phone)

    # WooCommerce orders (completed/processing)
    orders = fetch_all_records(
        TABLES['orders'],
        fields=["Email (Billing)", "Phone (Billing)"],
        filter_formula="OR({status}='completed',{status}='processing')"
    )
    for o in orders:
        f = o.get("fields", {})
        if email := normalize_email(f.get("Email (Billing)")):
            converter_emails.add(email)
        if phone := normalize_phone(f.get("Phone (Billing)")):
            converter_phones.add(phone)

    # Antoine (legacy) customers
    antoine = fetch_all_records(
        TABLES['user'],
        fields=["user_email", "phone_standarised", "billing_phone"],
        filter_formula="{is_customer_antoine}=TRUE()"
    )
    for u in antoine:
        f = u.get("fields", {})
        if email := normalize_email(f.get("user_email")):
            converter_emails.add(email)
        for pf in ["phone_standarised", "billing_phone"]:
            if phone := normalize_phone(f.get(pf)):
                converter_phones.add(phone)

    return converter_emails, converter_phones


def build_unsub_set() -> Set[str]:
    """Build set of unsubscribed emails."""
    unsub = fetch_all_records(
        TABLES['user'],
        fields=["user_email"],
        filter_formula="{unsubscribed_whattsapp}=TRUE()"
    )
    return {normalize_email(u.get("fields", {}).get("user_email"))
            for u in unsub if normalize_email(u.get("fields", {}).get("user_email"))}


def build_user_lookup() -> Dict[str, Dict]:
    """Build user lookup by email for phone/name enrichment."""
    users = fetch_all_records(
        TABLES['user'],
        fields=["user_email", "phone_standarised", "billing_phone",
                "billing_first_name", "unsubscribed_whattsapp"]
    )
    lookup = {}
    for u in users:
        f = u.get("fields", {})
        email = normalize_email(f.get("user_email"))
        if email:
            lookup[email] = {
                'phone': normalize_phone(f.get("phone_standarised")) or
                         normalize_phone(f.get("billing_phone")),
                'first_name': f.get("billing_first_name", ""),
                'unsubscribed': bool(f.get("unsubscribed_whattsapp"))
            }
    return lookup


# =============================================================================
# SEGMENT: QUIZ DROPPERS
# =============================================================================

def get_quiz_droppers() -> List[Dict]:
    """
    Get quiz droppers - completed quiz but never purchased.
    Returns list with: email, phone, first_name, cta_url, quiz_type
    """
    print("  Fetching quiz records...")
    quiz_fields = ["Email", "Phone Number", "Date", "Product Link", "Quiz Type",
                   "first_name", "User", "never_ordered", "unsubscribed_whattsapp (from User)"]
    quiz_records = fetch_all_records(TABLES['instapract'], fields=quiz_fields)
    print(f"    Total quiz records: {len(quiz_records):,}")

    print("  Building converter sets...")
    converter_emails, converter_phones = build_converter_sets()
    print(f"    Converter emails: {len(converter_emails):,}")

    print("  Building unsubscribe set...")
    unsub_emails = build_unsub_set()
    print(f"    Unsubscribed: {len(unsub_emails):,}")

    # Filter
    droppers = []
    seen_emails = set()
    excluded = defaultdict(int)

    # Sort by date descending
    quiz_records.sort(key=lambda x: x.get("fields", {}).get("Date", ""), reverse=True)

    for q in quiz_records:
        f = q.get("fields", {})
        email = normalize_email(f.get("Email"))
        phone = normalize_phone(f.get("Phone Number"))
        product_link = f.get("Product Link")
        quiz_type = f.get("Quiz Type", "")
        fname = f.get("first_name", "")
        user_link = f.get("User")
        never_ordered_raw = f.get("never_ordered")
        unsub_lookup = f.get("unsubscribed_whattsapp (from User)")

        # Must have email
        if not email:
            excluded['no_email'] += 1
            continue

        # Skip test emails
        if is_test_email(email):
            excluded['test_email'] += 1
            continue

        # Skip if converter via lookup
        if user_link:
            never_ordered_is_true = (isinstance(never_ordered_raw, list) and
                                     never_ordered_raw and never_ordered_raw[0] is True)
            if not never_ordered_is_true:
                excluded['converter_lookup'] += 1
                continue

        # Skip if converter via direct match
        if email in converter_emails:
            excluded['converter_direct'] += 1
            continue
        if phone and phone in converter_phones:
            excluded['converter_direct'] += 1
            continue

        # Skip if unsubscribed
        if isinstance(unsub_lookup, list) and unsub_lookup and unsub_lookup[0] is True:
            excluded['unsubscribed'] += 1
            continue
        if email in unsub_emails:
            excluded['unsubscribed'] += 1
            continue

        # Skip if no CTA URL
        if not product_link:
            excluded['no_cta'] += 1
            continue

        # Skip duplicates
        if email in seen_emails:
            excluded['duplicate'] += 1
            continue
        seen_emails.add(email)

        droppers.append({
            'email': email,
            'phone': phone,
            'first_name': fname.split()[0] if fname else "",
            'cta_url': product_link,
            'quiz_type': quiz_type,
        })

    print(f"  Filtering results:")
    for reason, count in excluded.items():
        if count > 0:
            print(f"    Excluded ({reason}): {count:,}")
    print(f"    Final droppers: {len(droppers):,}")

    return droppers


# =============================================================================
# SEGMENT: DORMANT CUSTOMERS
# =============================================================================

def get_dormant_customers() -> List[Dict]:
    """
    Get dormant customers - no orders in 90+ days.
    Uses Airtable view 'Dormant>90days'.
    Returns list with: email, phone, first_name
    """
    print("  Fetching dormant customers from view...")
    users = fetch_all_records(
        TABLES['user'],
        fields=["user_email", "billing_first_name", "phone_standarised",
                "billing_phone", "unsubscribed_whattsapp"],
        view="Dormant>90days"
    )
    print(f"    Total from view: {len(users):,}")

    # Filter
    dormant = []
    excluded = defaultdict(int)

    for u in users:
        f = u.get("fields", {})
        email = normalize_email(f.get("user_email"))
        phone = normalize_phone(f.get("phone_standarised")) or normalize_phone(f.get("billing_phone"))
        fname = f.get("billing_first_name", "")
        unsub = f.get("unsubscribed_whattsapp")

        if not email:
            excluded['no_email'] += 1
            continue

        if is_test_email(email):
            excluded['test_email'] += 1
            continue

        if unsub:
            excluded['unsubscribed'] += 1
            continue

        dormant.append({
            'email': email,
            'phone': phone,
            'first_name': fname.split()[0] if fname else "",
        })

    print(f"  Filtering results:")
    for reason, count in excluded.items():
        if count > 0:
            print(f"    Excluded ({reason}): {count:,}")
    print(f"    Final dormant: {len(dormant):,}")

    return dormant


# =============================================================================
# SEGMENT: ACTIVE CUSTOMERS
# =============================================================================

def get_active_customers() -> List[Dict]:
    """
    Get active customers - active subscribers + ordered in last 30 days.
    Returns list with: email, phone, first_name, source
    """
    today = datetime.now()
    thirty_days_ago = today - timedelta(days=30)

    print(f"  Date range: {thirty_days_ago.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")

    # Build user lookup for enrichment
    print("  Building user lookup...")
    user_lookup = build_user_lookup()
    unsub_emails = {e for e, d in user_lookup.items() if d.get('unsubscribed')}
    print(f"    Users: {len(user_lookup):,}, Unsubscribed: {len(unsub_emails):,}")

    combined = {}

    # Source 1: Active subscribers
    print("  Fetching active subscribers...")
    subs = fetch_all_records(
        TABLES['subscriptions'],
        fields=["status", "customer_email", "billing_first_name (from User)",
                "billing_phone (from User)"],
        filter_formula="{status}='active'"
    )
    print(f"    Active subscriptions: {len(subs):,}")

    for s in subs:
        f = s.get("fields", {})
        email = normalize_email(f.get("customer_email"))
        if not email or is_test_email(email):
            continue

        fname_list = f.get("billing_first_name (from User)", [])
        phone_list = f.get("billing_phone (from User)", [])

        fname = fname_list[0] if fname_list else ""
        phone = normalize_phone(phone_list[0]) if phone_list else None

        # Enrich from user lookup
        if not phone and email in user_lookup:
            phone = user_lookup[email]['phone']
        if not fname and email in user_lookup:
            fname = user_lookup[email]['first_name']

        combined[email] = {
            'email': email,
            'phone': phone,
            'first_name': fname.split()[0] if fname else "",
            'source': 'subscription'
        }

    print(f"    Unique subscribers: {len(combined):,}")

    # Source 2: Recent orders (last 30 days)
    print("  Fetching recent orders (30 days)...")
    orders = fetch_all_records(
        TABLES['orders'],
        fields=["status", "date_created", "Email (Billing)",
                "Phone (Billing)", "First Name (Billing)"],
        filter_formula="OR({status}='completed',{status}='processing')"
    )

    recent_count = 0
    for o in orders:
        f = o.get("fields", {})
        date_str = f.get("date_created", "")

        if date_str:
            try:
                order_date = datetime.fromisoformat(
                    date_str.replace('Z', '+00:00').replace('.000+00:00', '')
                )
                if order_date.replace(tzinfo=None) < thirty_days_ago:
                    continue
                recent_count += 1
            except:
                continue
        else:
            continue

        email = normalize_email(f.get("Email (Billing)"))
        if not email or is_test_email(email):
            continue

        fname = f.get("First Name (Billing)", "")
        phone = normalize_phone(f.get("Phone (Billing)"))

        # Enrich from user lookup
        if not phone and email in user_lookup:
            phone = user_lookup[email]['phone']
        if not fname and email in user_lookup:
            fname = user_lookup[email]['first_name']

        if email in combined:
            # Update existing with better data
            if not combined[email]['phone'] and phone:
                combined[email]['phone'] = phone
            if not combined[email]['first_name'] and fname:
                combined[email]['first_name'] = fname.split()[0] if fname else ""
            combined[email]['source'] = 'both'
        else:
            combined[email] = {
                'email': email,
                'phone': phone,
                'first_name': fname.split()[0] if fname else "",
                'source': 'recent_order'
            }

    print(f"    Orders in last 30 days: {recent_count:,}")
    print(f"    Combined unique: {len(combined):,}")

    # Exclude unsubscribed
    final = [c for e, c in combined.items() if e not in unsub_emails]
    excluded_unsub = len(combined) - len(final)

    print(f"  Filtering results:")
    print(f"    Excluded (unsubscribed): {excluded_unsub:,}")
    print(f"    Final active: {len(final):,}")

    # Stats
    source_counts = defaultdict(int)
    for c in final:
        source_counts[c['source']] += 1

    print(f"  By source:")
    print(f"    Subscription only: {source_counts['subscription']:,}")
    print(f"    Recent order only: {source_counts['recent_order']:,}")
    print(f"    Both: {source_counts['both']:,}")

    return final


# =============================================================================
# EXPORT & SEND
# =============================================================================

def normalize_cta_url(url: str) -> str:
    """Strip base URL to return path only for Gupshup templates."""
    if not url:
        return ''
    # Remove common base URLs
    for base in ['https://aneeq.co/', 'http://aneeq.co/', 'https://www.aneeq.co/', 'http://www.aneeq.co/']:
        if url.startswith(base):
            return url[len(base):]
    return url


def export_csv(records: List[Dict], segment: str, timestamp: str,
               cta_url: str = None) -> Tuple[str, str]:
    """Export records to CSV files for WhatsApp and Email."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # WhatsApp CSV (Gupshup format) - uses PATH ONLY for cta_url
    whatsapp_file = f"{OUTPUT_DIR}/{segment}_whatsapp_{timestamp}.csv"
    whatsapp_count = 0

    with open(whatsapp_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Phone', 'fname', 'cta_url'])
        for r in records:
            if r.get('phone'):
                raw_cta = r.get('cta_url', cta_url or '')
                writer.writerow([
                    r['phone'],
                    r.get('first_name', ''),
                    normalize_cta_url(raw_cta)
                ])
                whatsapp_count += 1

    # Email CSV - uses PATH ONLY for cta_url
    email_file = f"{OUTPUT_DIR}/{segment}_email_{timestamp}.csv"

    with open(email_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Email', 'first_name', 'phone', 'cta_url'])
        for r in records:
            raw_cta = r.get('cta_url', cta_url or '')
            writer.writerow([
                r['email'],
                r.get('first_name', ''),
                r.get('phone', ''),
                normalize_cta_url(raw_cta)
            ])

    print(f"\n  CSV files created:")
    print(f"    WhatsApp: {whatsapp_file} ({whatsapp_count:,} records)")
    print(f"    Email: {email_file} ({len(records):,} records)")

    return whatsapp_file, email_file


def send_campaign(records: List[Dict], segment_config: Dict,
                  dry_run: bool = False, limit: int = None) -> Tuple[int, int]:
    """Send email campaign to records."""
    template_id = segment_config['template_id']
    default_cta = segment_config.get('cta_url', 'https://aneeq.co/')

    if limit:
        records = records[:limit]

    print(f"\n  Sending {len(records):,} emails...")
    print(f"    Template: {template_id}")
    print(f"    Mode: {'DRY RUN' if dry_run else 'LIVE'}")

    success = 0
    failed = 0

    for i, r in enumerate(records):
        cta_url = r.get('cta_url', default_cta)
        ok, msg = send_email(
            r['email'],
            r.get('first_name', 'there'),
            cta_url,
            template_id,
            dry_run
        )

        if ok:
            success += 1
            status = "✓"
        else:
            failed += 1
            status = f"✗ {msg}"

        print(f"    [{i+1}/{len(records)}] {r['email'][:40]:<40} {status}")

    return success, failed


# =============================================================================
# MAIN
# =============================================================================

def list_segments():
    """Print available segments."""
    print("\n" + "="*60)
    print("AVAILABLE SEGMENTS")
    print("="*60)

    for key, config in SEGMENTS.items():
        print(f"\n{key}:")
        print(f"  Name: {config['name']}")
        print(f"  Description: {config['description']}")
        print(f"  Template ID: {config['template_id']}")
        print(f"  CTA URL: {config.get('cta_url', 'Dynamic (from data)')}")


def run_segment(segment: str, csv_only: bool = False, email_only: bool = False,
                dry_run: bool = False, limit: int = None):
    """Run campaign for a segment."""
    if segment not in SEGMENTS:
        print(f"Unknown segment: {segment}")
        print(f"Available: {', '.join(SEGMENTS.keys())}")
        return

    config = SEGMENTS[segment]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\n" + "="*60)
    print(f"SEGMENT: {config['name'].upper()}")
    print("="*60)
    print(f"Description: {config['description']}")
    print(f"Template ID: {config['template_id']}")
    print(f"CTA URL: {config.get('cta_url', 'Dynamic')}")
    print()

    # Get records
    if segment == 'quiz_droppers':
        records = get_quiz_droppers()
    elif segment == 'dormant':
        records = get_dormant_customers()
    elif segment == 'active':
        records = get_active_customers()
    else:
        print(f"No handler for segment: {segment}")
        return

    if not records:
        print("  No records found!")
        return

    # Stats
    with_email = sum(1 for r in records if r.get('email'))
    with_phone = sum(1 for r in records if r.get('phone'))
    with_both = sum(1 for r in records if r.get('email') and r.get('phone'))

    print(f"\n  Coverage:")
    print(f"    With email: {with_email:,}")
    print(f"    With phone: {with_phone:,}")
    print(f"    With both: {with_both:,}")

    # Export CSV
    if not email_only:
        export_csv(records, segment, timestamp, config.get('cta_url'))

    # Send emails
    if not csv_only:
        success, failed = send_campaign(records, config, dry_run, limit)

        print(f"\n  " + "="*40)
        print(f"  EMAIL SUMMARY")
        print(f"  " + "="*40)
        print(f"  Total: {len(records) if not limit else min(limit, len(records)):,}")
        print(f"  Success: {success:,}")
        print(f"  Failed: {failed:,}")


def main():
    parser = argparse.ArgumentParser(
        description='Campaign Manager - Weekly Marketing Campaigns',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python campaign_manager.py --list
  python campaign_manager.py --segment quiz_droppers --csv-only
  python campaign_manager.py --segment dormant --email-only
  python campaign_manager.py --segment active --execute
  python campaign_manager.py --segment all --execute
  python campaign_manager.py --segment active --dry-run --limit 10
        """
    )

    parser.add_argument('--list', action='store_true',
                        help='List available segments')
    parser.add_argument('--segment', type=str,
                        choices=['quiz_droppers', 'dormant', 'active', 'all'],
                        help='Segment to process')
    parser.add_argument('--csv-only', action='store_true',
                        help='Only generate CSV files (no emails)')
    parser.add_argument('--email-only', action='store_true',
                        help='Only send emails (no CSV generation)')
    parser.add_argument('--execute', action='store_true',
                        help='Execute campaign (send real emails)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview without sending emails')
    parser.add_argument('--limit', type=int,
                        help='Limit number of emails to send')

    args = parser.parse_args()

    if args.list:
        list_segments()
        return

    if not args.segment:
        parser.print_help()
        return

    if not args.csv_only and not args.email_only and not args.execute and not args.dry_run:
        print("Please specify an action:")
        print("  --csv-only    Generate CSV files only")
        print("  --email-only  Send emails only")
        print("  --execute     Full campaign (CSV + emails)")
        print("  --dry-run     Preview without sending")
        return

    # Determine modes
    csv_only = args.csv_only
    email_only = args.email_only
    dry_run = args.dry_run and not args.execute

    print("\n" + "="*60)
    print("CAMPAIGN MANAGER")
    print("="*60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'DRY RUN' if dry_run else 'CSV Only' if csv_only else 'Email Only' if email_only else 'FULL CAMPAIGN'}")
    if args.limit:
        print(f"Limit: {args.limit}")

    # Run segments
    segments_to_run = list(SEGMENTS.keys()) if args.segment == 'all' else [args.segment]

    results = {}
    for seg in segments_to_run:
        run_segment(seg, csv_only, email_only, dry_run, args.limit)
        results[seg] = True

    # Final summary
    print("\n" + "="*60)
    print("CAMPAIGN COMPLETE")
    print("="*60)
    print(f"Segments processed: {', '.join(results.keys())}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
