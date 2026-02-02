#!/usr/bin/env python3
"""
Quiz Droppers Segmentation

Generate Gupshup-ready CSV files for quiz droppers - users who completed a quiz
on the Instapract platform but never made a purchase.

Usage:
    python scripts/segmentation/quiz_droppers.py --audit           # Show funnel metrics
    python scripts/segmentation/quiz_droppers.py --execute         # Generate CSV files
    python scripts/segmentation/quiz_droppers.py --execute --since 2025-06-01  # With date filter
"""

import requests
import argparse
import re
import os
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()

# =============================================================================
# API Configuration
# =============================================================================

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")

# Table IDs
INSTAPRACT_TABLE = "tbleLSKMeFP1LF5hT"  # Quiz completions
MAMO_TABLE = "tbl7WfjTqWMnsqpbs"        # Payment records
ORDERS_TABLE = "tblWByCCtBE1dR6ox"      # WooCommerce orders
USER_TABLE = "tblMtIskMF3X3nKWC"        # Users (for unsubscribes)

# Field IDs for reference
# instapract table:
#   Email: fldUGXOufJC3DcQQ4
#   Phone Number: fldaZXw7eXhsXh6U2
#   never_ordered: fldcMtcI9xvZ5vt76 (lookup)
#   unsubscribed_whattsapp (from User): fld1fKWPanTaLyK55 (lookup)

# Output directory
OUTPUT_DIR = "/Users/juanmanuelzafra/Desktop/projects/aneeq/data/csv/gupshup"

headers = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json"
}

# =============================================================================
# Test Email Patterns
# =============================================================================

TEST_PATTERNS = [
    r'^test[@.]',
    r'@test\.com$',
    r'@example\.com$',
    r'^fake[@.]',
    r'^demo[@.]',
    r'@mailinator\.com$',
    r'@aneeq\.co$',  # Internal emails
    r'^test\d*@',    # test1@, test2@, etc.
    r'@yopmail\.com$',
    r'@tempmail\.',
]


def is_test_email(email):
    """Check if email matches test patterns"""
    if not email:
        return False
    email_lower = email.strip().lower()
    for pattern in TEST_PATTERNS:
        if re.search(pattern, email_lower):
            return True
    return False


# =============================================================================
# Phone Normalization
# =============================================================================

def normalize_phone_for_matching(phone):
    """
    Normalize any phone format to digits-only for matching.
    Returns the normalized form that can be compared across tables.
    """
    if not phone:
        return None

    # Convert to string (handles float like 971501234567.0)
    phone_str = str(phone).strip()
    if '.' in phone_str:
        phone_str = phone_str.split('.')[0]  # Remove decimal

    # Remove ALL non-digits
    digits = re.sub(r'\D', '', phone_str)

    if not digits or len(digits) < 8:
        return None

    # UAE normalization (to ensure consistent matching)
    if digits.startswith('00971'):
        digits = digits[2:]           # 00971... -> 971...
    elif digits.startswith('0') and len(digits) == 10:
        digits = '971' + digits[1:]   # 05x... -> 9715x...
    elif len(digits) == 9 and digits[0] == '5':
        digits = '971' + digits       # 5x... -> 9715x...

    return digits


def normalize_email(email):
    """Normalize email for matching"""
    if not email:
        return None
    return email.strip().lower()


def format_phone_for_gupshup(phone):
    """
    Format phone for Gupshup CSV output.
    Returns clean digits-only format (e.g., 971501234567)
    """
    normalized = normalize_phone_for_matching(phone)
    if not normalized:
        return None
    # Ensure it's a valid length (9-15 digits)
    if len(normalized) < 9 or len(normalized) > 15:
        return None
    return normalized


# =============================================================================
# Airtable API Functions
# =============================================================================

def fetch_all_records(table_id, fields=None, filter_formula=None):
    """Fetch all records from an Airtable table with pagination"""
    all_records = []
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

        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            print(f"Error fetching from {table_id}: {resp.text[:100]}")
            break

        data = resp.json()
        all_records.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break

    return all_records


# =============================================================================
# Data Building Functions
# =============================================================================

def build_converter_sets(mamo_records, woo_orders):
    """
    Build sets of emails and phones that have made purchases.
    Used to exclude converters from the dropper list.
    """
    converter_emails = set()
    converter_phones = set()

    # From Mamo Transactions (captured payments)
    for m in mamo_records:
        f = m.get("fields", {})

        # Check email field
        email = f.get("customer_details_email")
        norm_email = normalize_email(email)
        if norm_email:
            converter_emails.add(norm_email)

        # Check phone field
        phone = f.get("customer_details_phone_number")
        norm_phone = normalize_phone_for_matching(phone)
        if norm_phone:
            converter_phones.add(norm_phone)

    # From WooCommerce orders (completed/processing)
    for o in woo_orders:
        f = o.get("fields", {})

        # Email
        email = f.get("Email (Billing)")
        norm_email = normalize_email(email)
        if norm_email:
            converter_emails.add(norm_email)

        # Phone
        phone = f.get("Phone (Billing)")
        norm_phone = normalize_phone_for_matching(phone)
        if norm_phone:
            converter_phones.add(norm_phone)

    return converter_emails, converter_phones


def build_unsub_sets(user_records):
    """
    Build sets of emails and phones that have unsubscribed from WhatsApp.
    """
    unsub_emails = set()
    unsub_phones = set()

    for u in user_records:
        f = u.get("fields", {})

        # Check if unsubscribed
        if f.get("unsubscribed_whattsapp"):
            # Email
            email = f.get("user_email")
            norm_email = normalize_email(email)
            if norm_email:
                unsub_emails.add(norm_email)

            # Phone - check both fields
            for phone in [f.get("phone_standarised"), f.get("billing_phone")]:
                norm_phone = normalize_phone_for_matching(phone)
                if norm_phone:
                    unsub_phones.add(norm_phone)

    return unsub_emails, unsub_phones


# =============================================================================
# Quiz URL Extraction
# =============================================================================

def extract_product_slug(product_link):
    """
    Extract the product slug from Product Link field.
    Input: "https://aneeq.co/product/moderate-ed/" or "moderate-ed/"
    Output: "moderate-ed/"
    """
    if not product_link:
        return None

    # If it's a full URL, extract the product slug
    # Format: https://aneeq.co/product/moderate-ed/
    if 'http' in product_link:
        match = re.search(r'/product/([^/?]+)/?', product_link)
        if match:
            slug = match.group(1)
            return f"{slug}/"

    # If it's already just a slug, clean it up
    slug = product_link.strip().strip('/')
    return f"{slug}/" if slug else None


def categorize_quiz(quiz_type, quiz_url=None):
    """
    Categorize quiz into segment based on Quiz Type field.
    Falls back to quiz_url if Quiz Type is not available.
    Returns: 'hair_loss', 'sexual_health', 'beard_growth', or 'other'
    """
    # Prefer Quiz Type field
    if quiz_type:
        type_lower = quiz_type.lower().strip()
        if 'hair' in type_lower:
            return 'hair_loss'
        if 'sexual' in type_lower:
            return 'sexual_health'
        if 'beard' in type_lower:
            return 'beard_growth'

    # Fallback to quiz_url
    if quiz_url:
        url_lower = quiz_url.lower()

        # Hair loss patterns
        hair_patterns = ['hair-loss', 'hairloss', 'hair_loss', 'severe-hair', 'critical-hair', 'moderate-hair']
        for p in hair_patterns:
            if p in url_lower:
                return 'hair_loss'

        # Sexual health patterns
        sexual_patterns = ['sexual', 'ed', 'erectile', 'pe', 'premature', 'sex-', 'sex_']
        for p in sexual_patterns:
            if p in url_lower:
                return 'sexual_health'

        # Beard growth patterns
        beard_patterns = ['beard', 'facial-hair']
        for p in beard_patterns:
            if p in url_lower:
                return 'beard_growth'

    return 'other'


# =============================================================================
# Filtering Logic
# =============================================================================

def filter_quiz_droppers(quiz_records, converter_emails, converter_phones,
                         unsub_emails, unsub_phones, since_date=None):
    """
    Filter quiz records to find droppers.
    Returns tuple: (droppers, metrics)
    """
    metrics = {
        'total_quizzes': len(quiz_records),
        'excluded_test': 0,
        'excluded_no_phone': 0,
        'excluded_converted_lookup': 0,
        'excluded_converted_direct': 0,
        'excluded_unsubscribed': 0,
        'excluded_date_filter': 0,
        'potential_droppers': 0,
    }

    droppers = []

    for q in quiz_records:
        f = q.get("fields", {})

        # Get quiz data
        email = normalize_email(f.get("Email"))
        phone_raw = f.get("Phone Number")
        phone = normalize_phone_for_matching(phone_raw)
        quiz_date = f.get("Date")
        product_link = f.get("Product Link")
        quiz_url_field = f.get("quiz_url")  # singleSelect - clean slug like "moderate-ed/"
        quiz_type = f.get("Quiz Type")
        fname = f.get("first_name", "")
        user_link = f.get("User")  # Check if User is linked
        never_ordered_raw = f.get("never_ordered")  # Lookup field from User table
        unsub_lookup_raw = f.get("unsubscribed_whattsapp (from User)")  # Lookup field

        # Parse never_ordered lookup field:
        # - If User linked + never_ordered=[True] → User has NEVER ordered (keep as dropper)
        # - If User linked + never_ordered=None/[None]/blank → User HAS ordered (exclude as converter)
        # - If NO User link → Check by email/phone matching
        has_user_link = bool(user_link)
        never_ordered_is_true = False
        if isinstance(never_ordered_raw, list) and never_ordered_raw and never_ordered_raw[0] is True:
            never_ordered_is_true = True

        # unsub_lookup: [True] means unsubscribed, [None] or None means not unsubscribed
        unsub_lookup = False
        if isinstance(unsub_lookup_raw, list) and unsub_lookup_raw and unsub_lookup_raw[0] is True:
            unsub_lookup = True

        # Date filter
        if since_date and quiz_date:
            try:
                record_date = datetime.strptime(quiz_date[:10], "%Y-%m-%d")
                if record_date < since_date:
                    metrics['excluded_date_filter'] += 1
                    continue
            except (ValueError, TypeError):
                pass

        # Exclude test emails
        if is_test_email(email):
            metrics['excluded_test'] += 1
            continue

        # Exclude records without valid phone
        if not phone:
            metrics['excluded_no_phone'] += 1
            continue

        # Step 1: Check never_ordered lookup (if User is linked)
        # If User linked AND never_ordered is NOT [True] → User HAS ordered → EXCLUDE
        # This catches converters including is_customer_antoine legacy customers
        if has_user_link and not never_ordered_is_true:
            metrics['excluded_converted_lookup'] += 1
            continue

        # Step 2: Direct verification (catch-all for records without User link)
        # Check if email or phone is in converter sets from Mamo/WooCommerce
        if email and email in converter_emails:
            metrics['excluded_converted_direct'] += 1
            continue
        if phone and phone in converter_phones:
            metrics['excluded_converted_direct'] += 1
            continue

        # Check unsubscribed via lookup
        if unsub_lookup:
            metrics['excluded_unsubscribed'] += 1
            continue

        # Check unsubscribed via direct match
        if email and email in unsub_emails:
            metrics['excluded_unsubscribed'] += 1
            continue
        if phone and phone in unsub_phones:
            metrics['excluded_unsubscribed'] += 1
            continue

        # Resolve quiz_url: prefer quiz_url field (clean slug), fallback to Product Link
        resolved_url = None
        if quiz_url_field and quiz_url_field.strip():
            slug = quiz_url_field.strip()
            resolved_url = slug if slug.endswith('/') else f"{slug}/"
        else:
            resolved_url = extract_product_slug(product_link)

        # Passed all filters - this is a dropper
        droppers.append({
            'record_id': q['id'],
            'email': email,
            'phone': phone,
            'phone_raw': phone_raw,
            'fname': fname,
            'quiz_url': resolved_url,
            'quiz_type': quiz_type,
            'quiz_date': quiz_date,
            'category': categorize_quiz(quiz_type, quiz_url_field or product_link),
        })

    metrics['potential_droppers'] = len(droppers)
    return droppers, metrics


def deduplicate_droppers(droppers):
    """
    Deduplicate droppers by email and phone.
    Keep most recent quiz for each unique identifier.
    """
    metrics = {
        'before': len(droppers),
        'removed_email_dupe': 0,
        'removed_phone_dupe': 0,
        'after': 0,
    }

    # Sort by date descending (most recent first)
    sorted_droppers = sorted(
        droppers,
        key=lambda x: x.get('quiz_date') or '',
        reverse=True
    )

    seen_emails = set()
    seen_phones = set()
    unique_droppers = []

    for d in sorted_droppers:
        email = d.get('email')
        phone = d.get('phone')

        # Check email duplicate
        if email and email in seen_emails:
            metrics['removed_email_dupe'] += 1
            continue

        # Check phone duplicate
        if phone and phone in seen_phones:
            metrics['removed_phone_dupe'] += 1
            continue

        # Not a duplicate - keep it
        if email:
            seen_emails.add(email)
        if phone:
            seen_phones.add(phone)
        unique_droppers.append(d)

    metrics['after'] = len(unique_droppers)
    return unique_droppers, metrics


# =============================================================================
# CSV Export
# =============================================================================

def export_gupshup_csv(droppers, category, timestamp):
    """
    Export droppers to Gupshup-ready CSV file.
    """
    filename = f"gupshup_{category}_{timestamp}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)

    # Filter by category
    category_droppers = [d for d in droppers if d['category'] == category]

    if not category_droppers:
        return None, 0

    with open(filepath, 'w') as f:
        # Header
        f.write("Phone,fname,quiz_url\n")

        # Data rows
        for d in category_droppers:
            phone = format_phone_for_gupshup(d['phone'])
            fname = (d.get('fname') or '').replace(',', ' ').strip()
            quiz_url = d.get('quiz_url') or ''

            if phone:
                f.write(f"{phone},{fname},{quiz_url}\n")

    return filepath, len(category_droppers)


# =============================================================================
# Main Functions
# =============================================================================

def print_funnel_report(data_metrics, filter_metrics, dedup_metrics, category_counts, timestamp):
    """Print the funnel metrics report"""
    print("\n" + "=" * 60)
    print(f"QUIZ DROPPERS FUNNEL - {timestamp[:8]}")
    print("=" * 60)

    print("\n1. DATA SOURCES:")
    print(f"   Total quiz completions:        {data_metrics['quizzes']:,}")
    print(f"   Mamo captured transactions:    {data_metrics['mamo']:,}")
    print(f"   WooCommerce completed orders:  {data_metrics['woo']:,}")
    print(f"   Antoine (legacy) customers:    {data_metrics.get('antoine', 0):,}")
    print(f"   Unsubscribed users:            {data_metrics['unsub']:,}")

    print("\n2. FILTERING FUNNEL:")
    print(f"   Starting quiz records:         {filter_metrics['total_quizzes']:,}")
    if filter_metrics['excluded_date_filter'] > 0:
        print(f"   - Excluded (date filter):      -{filter_metrics['excluded_date_filter']:,}")
    print(f"   - Excluded (test emails):      -{filter_metrics['excluded_test']:,}")
    print(f"   - Excluded (no phone):         -{filter_metrics['excluded_no_phone']:,}")
    print(f"   - Excluded (converted-lookup): -{filter_metrics['excluded_converted_lookup']:,}")
    print(f"   - Excluded (converted-direct): -{filter_metrics['excluded_converted_direct']:,}")
    print(f"   - Excluded (unsubscribed):     -{filter_metrics['excluded_unsubscribed']:,}")
    print(f"   = Potential droppers:          {filter_metrics['potential_droppers']:,}")

    print("\n3. DEDUPLICATION:")
    print(f"   - Removed (duplicate email):   -{dedup_metrics['removed_email_dupe']:,}")
    print(f"   - Removed (duplicate phone):   -{dedup_metrics['removed_phone_dupe']:,}")
    print(f"   = Final unique droppers:       {dedup_metrics['after']:,}")

    print("\n4. BY QUIZ TYPE:")
    for cat, count in sorted(category_counts.items()):
        print(f"   {cat.replace('_', ' ').title():30} {count:,}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Quiz Droppers Segmentation for Gupshup")
    parser.add_argument("--audit", action="store_true", help="Show funnel metrics without generating files")
    parser.add_argument("--execute", action="store_true", help="Generate CSV files")
    parser.add_argument("--since", type=str, help="Filter quizzes since date (YYYY-MM-DD)")
    args = parser.parse_args()

    if not args.audit and not args.execute:
        print("Please specify --audit or --execute")
        print("\nUsage:")
        print("  python quiz_droppers.py --audit           # Show funnel metrics")
        print("  python quiz_droppers.py --execute         # Generate CSV files")
        print("  python quiz_droppers.py --execute --since 2025-06-01")
        return

    # Parse date filter
    since_date = None
    if args.since:
        try:
            since_date = datetime.strptime(args.since, "%Y-%m-%d")
            print(f"Filtering quizzes since: {args.since}")
        except ValueError:
            print(f"Invalid date format: {args.since}. Use YYYY-MM-DD")
            return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\nQuiz Droppers Segmentation - {timestamp}")
    print("-" * 50)

    # ==========================================================================
    # STEP 1: FETCH DATA
    # ==========================================================================
    print("\nFetching data from Airtable...")

    # Fetch quiz records
    print("  - Fetching quiz completions...")
    quiz_fields = ["Email", "Phone Number", "Date", "Product Link", "Quiz Type", "quiz_url",
                   "first_name", "User", "never_ordered", "unsubscribed_whattsapp (from User)"]
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

    # Fetch antoine (legacy) customers - these are converters not in Mamo/WooCommerce
    print("  - Fetching antoine (legacy) customers...")
    antoine_fields = ["user_email", "phone_standarised", "billing_phone"]
    antoine_filter = "{is_customer_antoine}=TRUE()"
    antoine_users = fetch_all_records(USER_TABLE, fields=antoine_fields, filter_formula=antoine_filter)
    print(f"    Found {len(antoine_users):,} antoine customers")

    data_metrics = {
        'quizzes': len(quiz_records),
        'mamo': len(mamo_records),
        'woo': len(woo_orders),
        'unsub': len(unsub_users),
        'antoine': len(antoine_users),
    }

    # ==========================================================================
    # STEP 2: BUILD EXCLUSION SETS
    # ==========================================================================
    print("\nBuilding exclusion sets...")

    converter_emails, converter_phones = build_converter_sets(mamo_records, woo_orders)

    # Add antoine (legacy) customers to converter sets
    # These are customers who converted before Mamo/WooCommerce integration
    for u in antoine_users:
        f = u.get("fields", {})
        email = normalize_email(f.get("user_email"))
        if email:
            converter_emails.add(email)
        for phone in [f.get("phone_standarised"), f.get("billing_phone")]:
            norm_phone = normalize_phone_for_matching(phone)
            if norm_phone:
                converter_phones.add(norm_phone)

    print(f"  - Converter emails: {len(converter_emails):,} (incl. antoine)")
    print(f"  - Converter phones: {len(converter_phones):,} (incl. antoine)")

    unsub_emails, unsub_phones = build_unsub_sets(unsub_users)
    print(f"  - Unsub emails: {len(unsub_emails):,}")
    print(f"  - Unsub phones: {len(unsub_phones):,}")

    # ==========================================================================
    # STEP 3: FILTER QUIZ RECORDS
    # ==========================================================================
    print("\nFiltering quiz records...")

    droppers, filter_metrics = filter_quiz_droppers(
        quiz_records,
        converter_emails,
        converter_phones,
        unsub_emails,
        unsub_phones,
        since_date
    )
    print(f"  - Potential droppers: {len(droppers):,}")

    # ==========================================================================
    # STEP 4: DEDUPLICATE
    # ==========================================================================
    print("\nDeduplicating...")

    unique_droppers, dedup_metrics = deduplicate_droppers(droppers)
    print(f"  - Final unique droppers: {len(unique_droppers):,}")

    # ==========================================================================
    # STEP 5: CATEGORIZE
    # ==========================================================================
    category_counts = defaultdict(int)
    for d in unique_droppers:
        category_counts[d['category']] += 1

    # ==========================================================================
    # PRINT FUNNEL REPORT
    # ==========================================================================
    print_funnel_report(data_metrics, filter_metrics, dedup_metrics, category_counts, timestamp)

    # ==========================================================================
    # STEP 6: EXPORT CSVs (if execute mode)
    # ==========================================================================
    if args.execute:
        print("\nExporting CSV files...")

        # Ensure output directory exists
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        categories_to_export = ['hair_loss', 'sexual_health', 'beard_growth']
        exported_files = []

        for cat in categories_to_export:
            filepath, count = export_gupshup_csv(unique_droppers, cat, timestamp)
            if filepath:
                exported_files.append((filepath, count))
                print(f"  - {os.path.basename(filepath)}: {count:,} records")
            else:
                print(f"  - {cat}: 0 records (skipped)")

        print("\nExport complete!")
        print(f"Files saved to: {OUTPUT_DIR}")

        # Validation summary
        print("\n" + "-" * 50)
        print("VALIDATION CHECKLIST:")
        print("-" * 50)

        total_exported = sum(count for _, count in exported_files)
        print(f"  Total records exported: {total_exported:,}")

        # Check for issues
        issues = []
        for d in unique_droppers:
            if not d.get('phone'):
                issues.append("Record without phone found")
            if not d.get('quiz_url'):
                issues.append("Record without quiz_url found")

        if issues:
            print(f"  Issues found: {len(set(issues))}")
            for issue in set(issues):
                print(f"    - {issue}")
        else:
            print("  No issues found")
    else:
        print("\nRun with --execute to generate CSV files")


if __name__ == "__main__":
    main()
