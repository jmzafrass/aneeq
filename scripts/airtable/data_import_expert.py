#!/usr/bin/env python3
"""
Data Import Expert - Unified Consultation & Quiz Dropper Importer

This script handles the daily import process for telehealth consultation data:
1. Table 1 (instapract): Imports ALL quiz users as a log (TOF)
2. Table 2 (adhoc_campaign_aneeq): Imports only quiz droppers for campaign enrollment

Features:
- Excludes test/alexy/alexey/antoine records
- Detects converters via Doctor Name + WooCommerce/Mamo email check
- Auto-maps quiz_url based on Quiz Type + Quiz Result
- Prevents double-enrollment in campaigns
- Deduplicates records

Usage:
    python3 scripts/airtable/data_import_expert.py <excel_file> [--dry-run]

Example:
    python3 scripts/airtable/data_import_expert.py ~/Downloads/Consultations-20260123143509.xlsx
    python3 scripts/airtable/data_import_expert.py ~/Downloads/Consultations-20260123143509.xlsx --dry-run
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import os
from dotenv import load_dotenv
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")

# Table 1: instapract (main base) - All quiz users log
INSTAPRACT_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
INSTAPRACT_TABLE_ID = 'tbleLSKMeFP1LF5hT'

# Table 2: adhoc_campaign_aneeq (campaign base) - Quiz droppers only
ADHOC_BASE_ID = 'appQWeYNzZ2IU68iH'
ADHOC_TABLE_ID = 'tbleLSKMeFP1LF5hT'

# WooCommerce & Mamo tables for converter detection
WOOCOMMERCE_TABLE_ID = 'tblWByCCtBE1dR6ox'
MAMO_TABLE_ID = 'tbl7WfjTqWMnsqpbs'

# Doctor name that indicates quiz-only (non-converter)
QUIZ_ONLY_DOCTOR = 'Dr Aneeq General Practitioner'

# Quiz URL mapping based on Quiz Type + Quiz Result
QUIZ_URL_MAPPING = {
    ("Beard growth", "-"): "beard-growth-serum/",
    ("Hair Loss", "-"): "moderate-hair-loss/",
    ("Hair Loss", "critical"): "critical-hair-loss/",
    ("Hair Loss", "moderate"): "moderate-hair-loss/",
    ("Hair Loss", "severe"): "severe-hair-loss/",
    ("Sexual Health", "-"): "moderate-ed/",
    ("Sexual Health", "Mild ED"): "moderate-ed/",
    ("Sexual Health", "Moderate ED"): "moderate-ed/",
    ("Sexual Health", "Severe ED"): "severe-ed/",
}

HEADERS = {
    'Authorization': f'Bearer {AIRTABLE_TOKEN}',
    'Content-Type': 'application/json'
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def print_header(title):
    """Print a formatted header."""
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_subheader(title):
    """Print a formatted subheader."""
    print()
    print(f"--- {title} ---")


def load_excel_data(file_path: str) -> pd.DataFrame:
    """Load Excel data from telehealth export."""
    df = pd.read_excel(file_path)
    print(f"Loaded {len(df)} rows from Excel")
    return df


def apply_exclusions(df: pd.DataFrame) -> pd.DataFrame:
    """Remove test records and alexy/alexey/antoine names."""
    df = df.copy()
    df['_name_lower'] = df['Patient Name'].str.lower().fillna('')

    exclusion_mask = (
        df['_name_lower'].str.contains('test', na=False) |
        df['_name_lower'].str.startswith('alexy') |
        df['_name_lower'].str.startswith('alexey') |
        df['_name_lower'].str.startswith('antoine')
    )

    excluded_count = exclusion_mask.sum()
    df_clean = df[~exclusion_mask].copy()
    df_clean = df_clean.drop(columns=['_name_lower'])

    print(f"Excluded {excluded_count} test/alexy/alexey/antoine records")
    return df_clean


def filter_quiz_droppers(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only quiz droppers (non-converters) based on Doctor Name."""
    df_droppers = df[df['Doctor Name'] == QUIZ_ONLY_DOCTOR].copy()
    converters_count = len(df) - len(df_droppers)
    print(f"Excluded {converters_count} converters (real doctor consultations)")
    return df_droppers


def deduplicate_by_key(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicates based on Email + Date + Quiz Type."""
    before = len(df)
    df = df.copy()
    df['_email_norm'] = df['Email'].str.lower().str.strip()
    df['_date_norm'] = df['Date'].astype(str)
    df['_quiz_type_norm'] = df['Quiz Type'].fillna('')

    df_dedup = df.drop_duplicates(
        subset=['_email_norm', '_date_norm', '_quiz_type_norm'],
        keep='last'
    ).copy()

    df_dedup = df_dedup.drop(columns=['_email_norm', '_date_norm', '_quiz_type_norm'])
    removed = before - len(df_dedup)
    if removed > 0:
        print(f"Deduplicated: removed {removed} duplicate rows")
    return df_dedup


def convert_date_format(date_str) -> str:
    """Convert date from DD-MM-YYYY to YYYY-MM-DD format."""
    if pd.isna(date_str) or not date_str:
        return None
    try:
        dt = datetime.strptime(str(date_str), '%d-%m-%Y')
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        try:
            datetime.strptime(str(date_str), '%Y-%m-%d')
            return str(date_str)
        except ValueError:
            return None


def get_quiz_url(quiz_type: str, quiz_result: str) -> str:
    """Get quiz_url based on Quiz Type and Quiz Result mapping."""
    return QUIZ_URL_MAPPING.get((quiz_type, quiz_result), None)


def fetch_all_records(base_id: str, table_id: str) -> list:
    """Fetch all records from an Airtable table."""
    all_records = []
    offset = None

    while True:
        url = f'https://api.airtable.com/v0/{base_id}/{table_id}?pageSize=100'
        if offset:
            url += f'&offset={offset}'

        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()

        all_records.extend(data.get('records', []))
        offset = data.get('offset')

        if not offset:
            break

    return all_records


def fetch_converter_emails() -> set:
    """Fetch all emails that have converted via WooCommerce or Mamo."""
    converter_emails = set()

    # WooCommerce emails
    records = fetch_all_records(INSTAPRACT_BASE_ID, WOOCOMMERCE_TABLE_ID)
    for rec in records:
        email = (rec.get('fields', {}).get('Email (Billing)') or '').lower().strip()
        if email:
            converter_emails.add(email)

    woo_count = len(converter_emails)

    # Mamo emails
    records = fetch_all_records(INSTAPRACT_BASE_ID, MAMO_TABLE_ID)
    for rec in records:
        email = (rec.get('fields', {}).get('customer_details_email') or '').lower().strip()
        if email:
            converter_emails.add(email)

    print(f"  WooCommerce emails: {woo_count}")
    print(f"  Total converter emails: {len(converter_emails)}")

    return converter_emails


def create_records_batch(base_id: str, table_id: str, records: list, dry_run: bool = False) -> int:
    """Create records in batches of 10."""
    if dry_run:
        return len(records)

    created = 0
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        payload = {'records': [{'fields': rec} for rec in batch]}
        url = f'https://api.airtable.com/v0/{base_id}/{table_id}'
        resp = requests.post(url, headers=HEADERS, json=payload)

        if resp.status_code == 200:
            created += len(batch)
        else:
            print(f"  Error creating batch: {resp.status_code} - {resp.text[:200]}")

    return created


def update_records_batch(base_id: str, table_id: str, records: list, dry_run: bool = False) -> int:
    """Update records in batches of 10."""
    if dry_run:
        return len(records)

    updated = 0
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        payload = {'records': batch}
        url = f'https://api.airtable.com/v0/{base_id}/{table_id}'
        resp = requests.patch(url, headers=HEADERS, json=payload)

        if resp.status_code == 200:
            updated += len(batch)
        else:
            print(f"  Error updating batch: {resp.status_code} - {resp.text[:200]}")

    return updated


# =============================================================================
# TABLE 1: INSTAPRACT (All Quiz Users Log)
# =============================================================================

def prepare_instapract_fields(row: pd.Series) -> dict:
    """Prepare fields for instapract table."""
    date_converted = convert_date_format(row.get('Date'))
    patient_name = str(row.get('Patient Name', '')).strip()

    phone = row.get('Phone Number')
    if pd.notna(phone):
        try:
            phone = int(float(phone))  # Handle both int and float strings
        except (ValueError, TypeError):
            phone = None  # Invalid phone (e.g., "-")
    else:
        phone = None

    fields = {
        'Patient Name': patient_name if patient_name else None,
        'Phone Number': phone,
        'MRN': str(row.get('MRN', '')).strip() if pd.notna(row.get('MRN')) else None,
        'Date': date_converted,
        'Email': str(row.get('Email', '')).strip().lower() if pd.notna(row.get('Email')) else None,
        'Quiz Type': str(row.get('Quiz Type', '')).strip() if pd.notna(row.get('Quiz Type')) else None,
        'Quiz Result': str(row.get('Quiz Result', '')).strip() if pd.notna(row.get('Quiz Result')) else None,
        'Doctor Name': str(row.get('Doctor Name', '')).strip() if pd.notna(row.get('Doctor Name')) else None,
    }

    return {k: v for k, v in fields.items() if v is not None}


def import_to_instapract(df: pd.DataFrame, dry_run: bool = False) -> dict:
    """Import all quiz users to instapract table (Table 1)."""
    print_header("TABLE 1: INSTAPRACT (All Quiz Users Log)")

    # Apply exclusions
    df_clean = apply_exclusions(df)
    if len(df_clean) == 0:
        print("No records to process.")
        return {'created': 0, 'updated': 0}

    # Deduplicate
    df_clean = deduplicate_by_key(df_clean)

    # Fetch existing records
    print("Fetching existing Airtable records...")
    existing_records = fetch_all_records(INSTAPRACT_BASE_ID, INSTAPRACT_TABLE_ID)
    print(f"  Found {len(existing_records)} existing records")

    # Build lookup: (email, date, quiz_type) -> record_id
    existing = {}
    for rec in existing_records:
        fields = rec.get('fields', {})
        email = (fields.get('Email') or '').lower().strip()
        date = fields.get('Date', '')
        quiz_type = fields.get('Quiz Type', '')
        existing[(email, date, quiz_type)] = rec['id']

    # Categorize records
    to_create = []
    to_update = []

    for _, row in df_clean.iterrows():
        fields = prepare_instapract_fields(row)
        email = (fields.get('Email') or '').lower().strip()
        date = fields.get('Date', '')
        quiz_type = fields.get('Quiz Type', '')

        if not email:
            continue

        key = (email, date, quiz_type)
        if key in existing:
            to_update.append({'id': existing[key], 'fields': fields})
        else:
            to_create.append(fields)

    # Deduplicate updates
    seen_ids = {}
    for rec in to_update:
        seen_ids[rec['id']] = rec
    to_update = list(seen_ids.values())

    print_subheader("Summary")
    print(f"  Records to create: {len(to_create)}")
    print(f"  Records to update: {len(to_update)}")

    # Execute
    created = 0
    updated = 0

    if to_create:
        print(f"\nCreating {len(to_create)} records..." + (" [DRY RUN]" if dry_run else ""))
        created = create_records_batch(INSTAPRACT_BASE_ID, INSTAPRACT_TABLE_ID, to_create, dry_run)
        print(f"  Created: {created}")

    if to_update:
        print(f"\nUpdating {len(to_update)} records..." + (" [DRY RUN]" if dry_run else ""))
        updated = update_records_batch(INSTAPRACT_BASE_ID, INSTAPRACT_TABLE_ID, to_update, dry_run)
        print(f"  Updated: {updated}")

    return {'created': created, 'updated': updated}


# =============================================================================
# TABLE 2: ADHOC_CAMPAIGN_ANEEQ (Quiz Droppers Only)
# =============================================================================

def prepare_adhoc_fields(row: pd.Series) -> dict:
    """Prepare fields for adhoc_campaign_aneeq table."""
    date_converted = convert_date_format(row.get('Date'))
    patient_name = str(row.get('Patient Name', '')).strip()

    phone = row.get('Phone Number')
    if pd.notna(phone):
        try:
            phone = int(float(phone))  # Handle both int and float strings
        except (ValueError, TypeError):
            phone = None  # Invalid phone (e.g., "-")
    else:
        phone = None

    quiz_type = str(row.get('Quiz Type', '')).strip() if pd.notna(row.get('Quiz Type')) else None
    quiz_result = str(row.get('Quiz Result', '')).strip() if pd.notna(row.get('Quiz Result')) else None
    quiz_url = get_quiz_url(quiz_type, quiz_result) if quiz_type and quiz_result else None

    fields = {
        'Patient Name': patient_name if patient_name else None,
        'Phone Number': phone,
        'MRN': str(row.get('MRN', '')).strip() if pd.notna(row.get('MRN')) else None,
        'Date': date_converted,
        'Email': str(row.get('Email', '')).strip().lower() if pd.notna(row.get('Email')) else None,
        'Quiz Type': quiz_type,
        'Quiz Result': quiz_result,
        'quiz_url': quiz_url,
    }

    return {k: v for k, v in fields.items() if v is not None}


def import_to_adhoc_campaign(df: pd.DataFrame, dry_run: bool = False) -> dict:
    """Import quiz droppers to adhoc_campaign_aneeq table (Table 2)."""
    print_header("TABLE 2: ADHOC_CAMPAIGN_ANEEQ (Quiz Droppers Only)")

    # Apply exclusions
    df_clean = apply_exclusions(df)
    if len(df_clean) == 0:
        print("No records to process.")
        return {'created': 0, 'skipped_enrolled': 0, 'skipped_converted': 0}

    # Filter to quiz droppers only
    df_droppers = filter_quiz_droppers(df_clean)
    if len(df_droppers) == 0:
        print("No quiz droppers to process.")
        return {'created': 0, 'skipped_enrolled': 0, 'skipped_converted': 0}

    # Deduplicate
    df_droppers = deduplicate_by_key(df_droppers)
    print(f"Quiz droppers to process: {len(df_droppers)}")

    # Fetch existing emails from adhoc table
    print("\nFetching existing enrolled emails...")
    existing_records = fetch_all_records(ADHOC_BASE_ID, ADHOC_TABLE_ID)
    existing_emails = set()
    for rec in existing_records:
        email = (rec.get('fields', {}).get('Email') or '').lower().strip()
        if email:
            existing_emails.add(email)
    print(f"  Already enrolled: {len(existing_emails)}")

    # Fetch converter emails
    print("\nFetching converter emails (WooCommerce + Mamo)...")
    converter_emails = fetch_converter_emails()

    # Categorize records
    to_create = []
    skipped_enrolled = 0
    skipped_converted = 0

    for _, row in df_droppers.iterrows():
        fields = prepare_adhoc_fields(row)
        email = (fields.get('Email') or '').lower().strip()

        if not email:
            continue

        if email in existing_emails:
            skipped_enrolled += 1
            continue

        if email in converter_emails:
            skipped_converted += 1
            continue

        to_create.append(fields)
        existing_emails.add(email)  # Prevent duplicates from same file

    print_subheader("Summary")
    print(f"  Records to create: {len(to_create)}")
    print(f"  Skipped (already enrolled): {skipped_enrolled}")
    print(f"  Skipped (already converted): {skipped_converted}")

    # Execute
    created = 0
    if to_create:
        print(f"\nCreating {len(to_create)} records..." + (" [DRY RUN]" if dry_run else ""))
        created = create_records_batch(ADHOC_BASE_ID, ADHOC_TABLE_ID, to_create, dry_run)
        print(f"  Created: {created}")

    return {
        'created': created,
        'skipped_enrolled': skipped_enrolled,
        'skipped_converted': skipped_converted
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Data Import Expert - Import consultations to Airtable',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/airtable/data_import_expert.py ~/Downloads/Consultations.xlsx
  python3 scripts/airtable/data_import_expert.py ~/Downloads/Consultations.xlsx --dry-run
        """
    )
    parser.add_argument('excel_file', help='Path to the Excel file from telehealth export')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without making them')

    args = parser.parse_args()

    if not Path(args.excel_file).exists():
        print(f"Error: File not found: {args.excel_file}")
        sys.exit(1)

    print_header("DATA IMPORT EXPERT")
    print(f"File: {args.excel_file}")
    if args.dry_run:
        print("[DRY RUN MODE - No changes will be made]")

    # Load data
    df = load_excel_data(args.excel_file)

    # Import to Table 1
    result1 = import_to_instapract(df, dry_run=args.dry_run)

    # Import to Table 2
    result2 = import_to_adhoc_campaign(df, dry_run=args.dry_run)

    # Final summary
    print_header("FINAL SUMMARY")
    print()
    print("Table 1 (instapract - All Quiz Users):")
    print(f"  Created: {result1['created']}")
    print(f"  Updated: {result1['updated']}")
    print()
    print("Table 2 (adhoc_campaign_aneeq - Quiz Droppers):")
    print(f"  Created: {result2['created']}")
    print(f"  Skipped (already enrolled): {result2['skipped_enrolled']}")
    print(f"  Skipped (already converted): {result2['skipped_converted']}")
    print()
    print("=" * 60)
    print("  IMPORT COMPLETE")
    print("=" * 60)


if __name__ == '__main__':
    main()
