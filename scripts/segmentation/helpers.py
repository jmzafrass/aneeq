"""
Segmentation Helpers Module

Common functions for building marketing segmentation files.
Used by the segmentation agent and individual segmentation scripts.
"""

import requests
import re
from typing import Set, Dict, List, Optional, Tuple
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()

# =============================================================================
# API Configuration
# =============================================================================

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")

# Table IDs
TABLES = {
    'instapract': 'tbleLSKMeFP1LF5hT',
    'user': 'tblMtIskMF3X3nKWC',
    'mamo': 'tbl7WfjTqWMnsqpbs',
    'orders': 'tblWByCCtBE1dR6ox',
    'subscriptions': 'tblf0AONAdsaBwo8P',
    'pharmacy': 'tbl5MDz6ZRUosdsEQ',
}

HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json"
}

# =============================================================================
# Test Email Patterns
# =============================================================================

TEST_EMAIL_PATTERNS = [
    r'^test[@.]',
    r'@test\.com$',
    r'@example\.com$',
    r'^fake[@.]',
    r'^demo[@.]',
    r'@mailinator\.com$',
    r'@aneeq\.co$',
    r'^test\d*@',
    r'@yopmail\.com$',
    r'@tempmail\.',
    r'^amazon$',
    r'@amazon\.com$',
]


def is_test_email(email: Optional[str]) -> bool:
    """Check if email matches test/fake patterns."""
    if not email:
        return False
    email_lower = email.strip().lower()
    for pattern in TEST_EMAIL_PATTERNS:
        if re.search(pattern, email_lower):
            return True
    return False


# =============================================================================
# Normalization Functions
# =============================================================================

def normalize_email(email: Optional[str]) -> Optional[str]:
    """Normalize email for matching."""
    if not email:
        return None
    return email.strip().lower()


def normalize_phone(phone) -> Optional[str]:
    """
    Normalize phone number to digits-only format for matching.

    Handles various formats:
    - +971 50 123 4567
    - 971501234567
    - 0501234567
    - 501234567
    - 971501234567.0 (number type)

    Returns normalized format (e.g., 971501234567) or None if invalid.
    """
    if not phone:
        return None

    # Convert to string (handles float like 971501234567.0)
    phone_str = str(phone).strip()
    if '.' in phone_str:
        phone_str = phone_str.split('.')[0]

    # Remove ALL non-digits
    digits = re.sub(r'\D', '', phone_str)

    if not digits or len(digits) < 8:
        return None

    # UAE normalization
    if digits.startswith('00971'):
        digits = digits[2:]           # 00971... -> 971...
    elif digits.startswith('0') and len(digits) == 10:
        digits = '971' + digits[1:]   # 05x... -> 9715x...
    elif len(digits) == 9 and digits[0] == '5':
        digits = '971' + digits       # 5x... -> 9715x...

    # Validate length
    if len(digits) < 9 or len(digits) > 15:
        return None

    return digits


# =============================================================================
# Airtable API Functions
# =============================================================================

def fetch_all_records(
    table_id: str,
    fields: Optional[List[str]] = None,
    filter_formula: Optional[str] = None,
    max_records: Optional[int] = None
) -> List[Dict]:
    """
    Fetch all records from an Airtable table with pagination.

    Args:
        table_id: Airtable table ID
        fields: List of field names to fetch (None = all fields)
        filter_formula: Airtable formula to filter records
        max_records: Maximum number of records to fetch (None = all)

    Returns:
        List of record dictionaries
    """
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

        resp = requests.get(url, headers=HEADERS, params=params)

        if resp.status_code != 200:
            print(f"Error fetching from {table_id}: {resp.text[:100]}")
            break

        data = resp.json()
        all_records.extend(data.get("records", []))

        if max_records and len(all_records) >= max_records:
            all_records = all_records[:max_records]
            break

        offset = data.get("offset")
        if not offset:
            break

    return all_records


# =============================================================================
# Converter Set Building
# =============================================================================

def build_converter_sets(
    include_mamo: bool = True,
    include_woo: bool = True,
    include_antoine: bool = True,
    mamo_status: str = "captured",
    woo_statuses: List[str] = None
) -> Tuple[Set[str], Set[str]]:
    """
    Build sets of emails and phones that have made purchases.

    Args:
        include_mamo: Include Mamo transactions
        include_woo: Include WooCommerce orders
        include_antoine: Include antoine (legacy) customers
        mamo_status: Mamo status to filter (default: 'captured')
        woo_statuses: WooCommerce statuses to filter (default: ['completed', 'processing'])

    Returns:
        Tuple of (converter_emails, converter_phones) sets
    """
    if woo_statuses is None:
        woo_statuses = ['completed', 'processing']

    converter_emails = set()
    converter_phones = set()

    # Mamo Transactions
    if include_mamo:
        mamo_records = fetch_all_records(
            TABLES['mamo'],
            fields=["customer_details_email", "customer_details_phone_number"],
            filter_formula=f"{{status}}='{mamo_status}'"
        )
        for m in mamo_records:
            f = m.get("fields", {})
            if email := normalize_email(f.get("customer_details_email")):
                converter_emails.add(email)
            if phone := normalize_phone(f.get("customer_details_phone_number")):
                converter_phones.add(phone)

    # WooCommerce Orders
    if include_woo:
        woo_filter = "OR(" + ",".join(f"{{status}}='{s}'" for s in woo_statuses) + ")"
        woo_orders = fetch_all_records(
            TABLES['orders'],
            fields=["Email (Billing)", "Phone (Billing)"],
            filter_formula=woo_filter
        )
        for o in woo_orders:
            f = o.get("fields", {})
            if email := normalize_email(f.get("Email (Billing)")):
                converter_emails.add(email)
            if phone := normalize_phone(f.get("Phone (Billing)")):
                converter_phones.add(phone)

    # Antoine (Legacy) Customers
    if include_antoine:
        antoine_users = fetch_all_records(
            TABLES['user'],
            fields=["user_email", "phone_standarised", "billing_phone"],
            filter_formula="{is_customer_antoine}=TRUE()"
        )
        for u in antoine_users:
            f = u.get("fields", {})
            if email := normalize_email(f.get("user_email")):
                converter_emails.add(email)
            for phone_field in ["phone_standarised", "billing_phone"]:
                if phone := normalize_phone(f.get(phone_field)):
                    converter_phones.add(phone)

    return converter_emails, converter_phones


def build_unsub_sets() -> Tuple[Set[str], Set[str]]:
    """
    Build sets of emails and phones that have unsubscribed from WhatsApp.

    Returns:
        Tuple of (unsub_emails, unsub_phones) sets
    """
    unsub_emails = set()
    unsub_phones = set()

    unsub_users = fetch_all_records(
        TABLES['user'],
        fields=["user_email", "phone_standarised", "billing_phone"],
        filter_formula="{unsubscribed_whattsapp}=TRUE()"
    )

    for u in unsub_users:
        f = u.get("fields", {})
        if email := normalize_email(f.get("user_email")):
            unsub_emails.add(email)
        for phone_field in ["phone_standarised", "billing_phone"]:
            if phone := normalize_phone(f.get(phone_field)):
                unsub_phones.add(phone)

    return unsub_emails, unsub_phones


# =============================================================================
# Deduplication
# =============================================================================

def deduplicate_records(
    records: List[Dict],
    date_field: str = 'date',
    email_field: str = 'email',
    phone_field: str = 'phone'
) -> Tuple[List[Dict], Dict]:
    """
    Deduplicate records by email and phone, keeping most recent.

    Args:
        records: List of record dictionaries
        date_field: Field name containing date for sorting
        email_field: Field name containing email
        phone_field: Field name containing phone

    Returns:
        Tuple of (unique_records, metrics_dict)
    """
    metrics = {
        'before': len(records),
        'removed_email_dupe': 0,
        'removed_phone_dupe': 0,
        'after': 0,
    }

    # Sort by date descending (most recent first)
    sorted_records = sorted(
        records,
        key=lambda x: x.get(date_field) or '',
        reverse=True
    )

    seen_emails = set()
    seen_phones = set()
    unique_records = []

    for r in sorted_records:
        email = r.get(email_field)
        phone = r.get(phone_field)

        if email and email in seen_emails:
            metrics['removed_email_dupe'] += 1
            continue

        if phone and phone in seen_phones:
            metrics['removed_phone_dupe'] += 1
            continue

        if email:
            seen_emails.add(email)
        if phone:
            seen_phones.add(phone)
        unique_records.append(r)

    metrics['after'] = len(unique_records)
    return unique_records, metrics


# =============================================================================
# CSV Export
# =============================================================================

def export_gupshup_csv(
    records: List[Dict],
    filepath: str,
    phone_field: str = 'phone',
    name_field: str = 'fname',
    extra_field: str = 'quiz_url',
    extra_header: str = 'quiz_url'
) -> int:
    """
    Export records to Gupshup-ready CSV.

    Args:
        records: List of record dictionaries
        filepath: Output file path
        phone_field: Field containing phone number
        name_field: Field containing first name
        extra_field: Additional field to include
        extra_header: Header name for extra field

    Returns:
        Number of records written
    """
    count = 0
    with open(filepath, 'w') as f:
        f.write(f"Phone,fname,{extra_header}\n")

        for r in records:
            phone = r.get(phone_field)
            if not phone:
                continue

            fname = (r.get(name_field) or '').replace(',', ' ').strip()
            extra = r.get(extra_field) or ''

            f.write(f"{phone},{fname},{extra}\n")
            count += 1

    return count


# =============================================================================
# Lookup Field Parsing
# =============================================================================

def parse_lookup_boolean(raw_value) -> Optional[bool]:
    """
    Parse Airtable lookup field that returns arrays like [True], [False], [None].

    Args:
        raw_value: Raw value from Airtable API

    Returns:
        True, False, or None
    """
    if isinstance(raw_value, list) and raw_value:
        return raw_value[0]
    return None


def is_converter_by_lookup(user_link, never_ordered_raw) -> bool:
    """
    Check if a quiz record is a converter based on User link and never_ordered lookup.

    Logic:
    - If User linked + never_ordered is NOT [True] → IS a converter
    - If no User link → Cannot determine (return False)

    Args:
        user_link: User field value (list of record IDs or None)
        never_ordered_raw: never_ordered lookup field value

    Returns:
        True if this is a converter, False otherwise
    """
    has_user_link = bool(user_link)

    if not has_user_link:
        return False

    never_ordered_is_true = False
    if isinstance(never_ordered_raw, list) and never_ordered_raw and never_ordered_raw[0] is True:
        never_ordered_is_true = True

    # If user is linked but never_ordered is NOT True, they have ordered
    return has_user_link and not never_ordered_is_true


# =============================================================================
# Utility Functions
# =============================================================================

def generate_timestamp() -> str:
    """Generate timestamp string for file naming."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def print_funnel_metrics(
    title: str,
    data_sources: Dict[str, int],
    exclusions: Dict[str, int],
    final_count: int,
    category_breakdown: Optional[Dict[str, int]] = None
):
    """Print formatted funnel metrics report."""
    print("\n" + "=" * 60)
    print(f"{title}")
    print("=" * 60)

    print("\n1. DATA SOURCES:")
    for name, count in data_sources.items():
        print(f"   {name:30} {count:,}")

    print("\n2. EXCLUSIONS:")
    total_excluded = 0
    for name, count in exclusions.items():
        if count > 0:
            print(f"   - {name:28} -{count:,}")
            total_excluded += count
    print(f"   {'Total excluded':30} -{total_excluded:,}")

    print(f"\n3. FINAL COUNT: {final_count:,}")

    if category_breakdown:
        print("\n4. BY CATEGORY:")
        for cat, count in sorted(category_breakdown.items()):
            print(f"   {cat:30} {count:,}")

    print("=" * 60)
