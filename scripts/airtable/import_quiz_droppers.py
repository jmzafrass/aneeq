#!/usr/bin/env python3
"""
Import Quiz Droppers to Airtable adhoc_campaign_aneeq Table

This script imports quiz dropper data (non-converters) from the telehealth
provider Excel export to the adhoc_campaign_aneeq table for campaign enrollment.

Logic:
- Excludes test records (names containing 'test', starting with 'alexy', 'alexey', or 'antoine')
- Excludes converters (records with real doctor names like "Dr. Hassan Galadari")
- Only imports quiz droppers (Doctor Name = "Dr Aneeq General Practitioner")
- Uses Email + Date + Quiz Type as unique key
- Creates new records if no match found
- Updates existing records if match found

Usage:
    python3 scripts/airtable/import_quiz_droppers.py <excel_file> [--dry-run]
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

# Airtable Configuration - adhoc_campaign_aneeq base
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = 'appQWeYNzZ2IU68iH'
TABLE_ID = 'tbleLSKMeFP1LF5hT'  # adhoc_campaign_aneeq table

# Main base for WooCommerce/Mamo converter check
MAIN_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
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


def load_excel_data(file_path: str) -> pd.DataFrame:
    """Load and clean Excel data from telehealth export."""
    df = pd.read_excel(file_path)
    print(f"Loaded {len(df)} rows from Excel")
    return df


def apply_exclusions(df: pd.DataFrame) -> pd.DataFrame:
    """Remove test records and alexy/alexey/antoine names."""
    original_count = len(df)

    # Normalize patient name for matching
    df['_name_lower'] = df['Patient Name'].str.lower().fillna('')

    # Exclusion rules for test/alexy/alexey/antoine
    exclusion_mask = (
        df['_name_lower'].str.contains('test', na=False) |
        df['_name_lower'].str.startswith('alexy') |
        df['_name_lower'].str.startswith('alexey') |
        df['_name_lower'].str.startswith('antoine')
    )

    excluded = df[exclusion_mask]
    df_clean = df[~exclusion_mask].copy()

    # Clean up temp column
    df_clean = df_clean.drop(columns=['_name_lower'])

    print(f"Excluded {len(excluded)} test/alexy/alexey/antoine records")

    return df_clean


def filter_quiz_droppers(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only quiz droppers (non-converters) based on Doctor Name."""
    before_count = len(df)

    # Keep only records with the quiz-only doctor (non-converters)
    df_droppers = df[df['Doctor Name'] == QUIZ_ONLY_DOCTOR].copy()

    converters_count = before_count - len(df_droppers)
    print(f"Excluded {converters_count} converters (real doctor consultations)")
    print(f"Quiz droppers remaining: {len(df_droppers)}")

    return df_droppers


def deduplicate_excel_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicate rows from Excel data based on Email + Date + Quiz Type.
    Keeps the last occurrence (most recent in the file).
    """
    before_count = len(df)

    # Normalize email for dedup matching
    df['_email_norm'] = df['Email'].str.lower().str.strip()
    df['_date_norm'] = df['Date'].astype(str)
    df['_quiz_type_norm'] = df['Quiz Type'].fillna('')

    # Drop duplicates keeping last occurrence
    df_dedup = df.drop_duplicates(
        subset=['_email_norm', '_date_norm', '_quiz_type_norm'],
        keep='last'
    ).copy()

    # Clean up temp columns
    df_dedup = df_dedup.drop(columns=['_email_norm', '_date_norm', '_quiz_type_norm'])

    removed = before_count - len(df_dedup)
    if removed > 0:
        print(f"Deduplicated: removed {removed} duplicate rows (same Email + Date + Quiz Type)")

    return df_dedup


def convert_date_format(date_str: str) -> str:
    """Convert date from DD-MM-YYYY to YYYY-MM-DD format."""
    if pd.isna(date_str) or not date_str:
        return None
    try:
        # Try DD-MM-YYYY format (from Excel)
        dt = datetime.strptime(str(date_str), '%d-%m-%Y')
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        try:
            # Try YYYY-MM-DD format (already correct)
            datetime.strptime(str(date_str), '%Y-%m-%d')
            return str(date_str)
        except ValueError:
            print(f"  Warning: Could not parse date '{date_str}'")
            return None


def fetch_converter_emails() -> set:
    """Fetch all emails that have converted via WooCommerce or Mamo."""
    print("Fetching converter emails from WooCommerce + Mamo...")
    converter_emails = set()

    # Fetch WooCommerce order emails
    offset = None
    while True:
        url = f'https://api.airtable.com/v0/{MAIN_BASE_ID}/{WOOCOMMERCE_TABLE_ID}?pageSize=100'
        if offset:
            url += f'&offset={offset}'
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        for rec in data.get('records', []):
            email = (rec.get('fields', {}).get('Email (Billing)') or '').lower().strip()
            if email:
                converter_emails.add(email)
        offset = data.get('offset')
        if not offset:
            break

    woo_count = len(converter_emails)

    # Fetch Mamo transaction emails
    offset = None
    while True:
        url = f'https://api.airtable.com/v0/{MAIN_BASE_ID}/{MAMO_TABLE_ID}?pageSize=100'
        if offset:
            url += f'&offset={offset}'
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        for rec in data.get('records', []):
            email = (rec.get('fields', {}).get('customer_details_email') or '').lower().strip()
            if email:
                converter_emails.add(email)
        offset = data.get('offset')
        if not offset:
            break

    print(f"  WooCommerce emails: {woo_count}")
    print(f"  Total unique converter emails: {len(converter_emails)}")

    return converter_emails


def fetch_existing_records() -> set:
    """Fetch all existing emails from Airtable adhoc_campaign_aneeq table."""
    print("Fetching existing Airtable records...")
    all_records = []
    offset = None

    while True:
        url = f'https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}?pageSize=100'
        if offset:
            url += f'&offset={offset}'

        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()

        all_records.extend(data.get('records', []))
        offset = data.get('offset')

        if not offset:
            break

    print(f"Fetched {len(all_records)} existing records")

    # Build set of existing emails (skip if email already exists - no double enrollment)
    existing_emails = set()
    for rec in all_records:
        fields = rec.get('fields', {})
        email = (fields.get('Email') or '').lower().strip()
        if email:
            existing_emails.add(email)

    print(f"Unique emails already enrolled: {len(existing_emails)}")

    return existing_emails


def get_quiz_url(quiz_type: str, quiz_result: str) -> str:
    """Get quiz_url based on Quiz Type and Quiz Result mapping."""
    key = (quiz_type, quiz_result)
    return QUIZ_URL_MAPPING.get(key, None)


def prepare_record_fields(row: pd.Series) -> dict:
    """Prepare Airtable fields from Excel row."""
    # Convert date format
    date_converted = convert_date_format(row.get('Date'))

    # Patient name
    patient_name = str(row.get('Patient Name', '')).strip()

    # Normalize phone number
    phone = row.get('Phone Number')
    if pd.notna(phone):
        phone = int(phone)
    else:
        phone = None

    # Get Quiz Type and Quiz Result
    quiz_type = str(row.get('Quiz Type', '')).strip() if pd.notna(row.get('Quiz Type')) else None
    quiz_result = str(row.get('Quiz Result', '')).strip() if pd.notna(row.get('Quiz Result')) else None

    # Look up quiz_url from mapping
    quiz_url = None
    if quiz_type and quiz_result:
        quiz_url = get_quiz_url(quiz_type, quiz_result)

    # Note: first_name and phone_number are computed fields in Airtable - don't write to them
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

    # Remove None values
    fields = {k: v for k, v in fields.items() if v is not None}

    return fields


def create_records(records_to_create: list, dry_run: bool = False) -> int:
    """Create new records in Airtable (batch of up to 10)."""
    if dry_run:
        print(f"  [DRY RUN] Would create {len(records_to_create)} records")
        return len(records_to_create)

    created = 0
    # Airtable allows max 10 records per batch
    for i in range(0, len(records_to_create), 10):
        batch = records_to_create[i:i+10]

        payload = {
            'records': [{'fields': rec} for rec in batch]
        }

        url = f'https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}'
        resp = requests.post(url, headers=HEADERS, json=payload)

        if resp.status_code == 200:
            created += len(batch)
        else:
            print(f"  Error creating batch: {resp.status_code} - {resp.text}")

    return created


def update_records(records_to_update: list, dry_run: bool = False) -> int:
    """Update existing records in Airtable (batch of up to 10)."""
    if dry_run:
        print(f"  [DRY RUN] Would update {len(records_to_update)} records")
        return len(records_to_update)

    updated = 0
    # Airtable allows max 10 records per batch
    for i in range(0, len(records_to_update), 10):
        batch = records_to_update[i:i+10]

        payload = {
            'records': batch
        }

        url = f'https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}'
        resp = requests.patch(url, headers=HEADERS, json=payload)

        if resp.status_code == 200:
            updated += len(batch)
        else:
            print(f"  Error updating batch: {resp.status_code} - {resp.text}")

    return updated


def main():
    parser = argparse.ArgumentParser(description='Import quiz droppers to Airtable adhoc_campaign_aneeq table')
    parser.add_argument('excel_file', help='Path to the Excel file from telehealth export')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without making them')

    args = parser.parse_args()

    if not Path(args.excel_file).exists():
        print(f"Error: File not found: {args.excel_file}")
        sys.exit(1)

    print("=" * 60)
    print("ADHOC_CAMPAIGN_ANEEQ TABLE IMPORT (Quiz Droppers Only)")
    print("=" * 60)

    if args.dry_run:
        print("[DRY RUN MODE - No changes will be made]")

    print()

    # Step 1: Load Excel data
    df = load_excel_data(args.excel_file)

    # Step 2: Apply test/alexy/alexey/antoine exclusions
    df_clean = apply_exclusions(df)

    if len(df_clean) == 0:
        print("No records to process after exclusions.")
        sys.exit(0)

    # Step 3: Filter to only quiz droppers (exclude converters)
    df_droppers = filter_quiz_droppers(df_clean)

    if len(df_droppers) == 0:
        print("No quiz droppers to process (all records are converters).")
        sys.exit(0)

    # Step 4: Deduplicate Excel data (same Email + Date + Quiz Type)
    df_droppers = deduplicate_excel_data(df_droppers)

    # Step 5: Fetch existing emails from Airtable
    existing_emails = fetch_existing_records()

    # Step 5b: Fetch converter emails from WooCommerce + Mamo
    converter_emails = fetch_converter_emails()

    # Step 6: Categorize records - only create for truly new emails that haven't converted
    to_create = []
    skipped_no_email = 0
    skipped_already_enrolled = 0
    skipped_converter = 0

    print("\nProcessing records...")
    for idx, row in df_droppers.iterrows():
        fields = prepare_record_fields(row)

        email = (fields.get('Email') or '').lower().strip()

        if not email:
            skipped_no_email += 1
            continue

        if email in existing_emails:
            # Skip - already enrolled in a campaign journey
            skipped_already_enrolled += 1
            continue

        if email in converter_emails:
            # Skip - already converted via WooCommerce or Mamo
            skipped_converter += 1
            continue

        # Create new record (and mark email as seen to avoid duplicates from same file)
        to_create.append(fields)
        existing_emails.add(email)

    print(f"\nSummary:")
    print(f"  - Records to create: {len(to_create)}")
    print(f"  - Skipped (already enrolled): {skipped_already_enrolled}")
    print(f"  - Skipped (already converted): {skipped_converter}")
    print(f"  - Skipped (no email): {skipped_no_email}")

    # Step 7: Execute changes
    if to_create:
        print(f"\nCreating {len(to_create)} new records...")
        created = create_records(to_create, dry_run=args.dry_run)
        print(f"  Created: {created}")
    else:
        print("\nNo new records to create.")

    print("\n" + "=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)


if __name__ == '__main__':
    main()
