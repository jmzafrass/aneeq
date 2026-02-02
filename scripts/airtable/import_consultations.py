#!/usr/bin/env python3
"""
Import Consultations to Airtable instapract Table

This script imports consultation data from the telehealth provider Excel export
to the Airtable instapract table (TOF log of all quiz users).

Logic:
- Excludes test records (names containing 'test', starting with 'alexy' or 'antoine')
- Uses Email + Date + Quiz Type as unique key
- Creates new records if no match found
- Updates existing records if match found
- Allows multiple quiz results per email (different dates/quiz types)

Usage:
    python3 scripts/airtable/import_consultations.py <excel_file> [--dry-run]
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

# Airtable Configuration
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_ID = 'tbleLSKMeFP1LF5hT'  # instapract table

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
    """Remove test records and alexy/antoine names."""
    original_count = len(df)

    # Normalize patient name for matching
    df['_name_lower'] = df['Patient Name'].str.lower().fillna('')

    # Exclusion rules
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

    print(f"Excluded {len(excluded)} test/alexy/antoine records")
    print(f"Remaining: {len(df_clean)} records to process")

    return df_clean


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


def extract_first_name(full_name: str) -> str:
    """Extract first name from full name."""
    if pd.isna(full_name) or not full_name:
        return ''
    parts = str(full_name).strip().split()
    return parts[0] if parts else ''


def fetch_existing_records() -> dict:
    """Fetch all existing records from Airtable instapract table."""
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

    # Build lookup dict: (email, date, quiz_type) -> record_id
    existing = {}
    for rec in all_records:
        fields = rec.get('fields', {})
        email = (fields.get('Email') or '').lower().strip()
        date = fields.get('Date', '')
        quiz_type = fields.get('Quiz Type', '')

        key = (email, date, quiz_type)
        existing[key] = rec['id']

    return existing


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

    # Note: first_name and phone_number are computed fields in Airtable - don't write to them
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
    parser = argparse.ArgumentParser(description='Import consultations to Airtable instapract table')
    parser.add_argument('excel_file', help='Path to the Excel file from telehealth export')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without making them')

    args = parser.parse_args()

    if not Path(args.excel_file).exists():
        print(f"Error: File not found: {args.excel_file}")
        sys.exit(1)

    print("=" * 60)
    print("INSTAPRACT TABLE IMPORT")
    print("=" * 60)

    if args.dry_run:
        print("[DRY RUN MODE - No changes will be made]")

    print()

    # Step 1: Load Excel data
    df = load_excel_data(args.excel_file)

    # Step 2: Apply exclusions
    df_clean = apply_exclusions(df)

    if len(df_clean) == 0:
        print("No records to process after exclusions.")
        sys.exit(0)

    # Step 2b: Deduplicate Excel data (same Email + Date + Quiz Type)
    df_clean = deduplicate_excel_data(df_clean)

    # Step 3: Fetch existing Airtable records
    existing = fetch_existing_records()

    # Step 4: Categorize records for create/update
    to_create = []
    to_update = []
    skipped = 0

    print("\nProcessing records...")
    for idx, row in df_clean.iterrows():
        fields = prepare_record_fields(row)

        # Build lookup key
        email = (fields.get('Email') or '').lower().strip()
        date = fields.get('Date', '')
        quiz_type = fields.get('Quiz Type', '')

        if not email:
            skipped += 1
            continue

        key = (email, date, quiz_type)

        if key in existing:
            # Update existing record
            record_id = existing[key]
            to_update.append({
                'id': record_id,
                'fields': fields
            })
        else:
            # Create new record
            to_create.append(fields)

    # Deduplicate updates (keep last occurrence for each record_id)
    seen_ids = {}
    for rec in to_update:
        seen_ids[rec['id']] = rec  # Later entries overwrite earlier
    to_update = list(seen_ids.values())

    print(f"\nSummary:")
    print(f"  - Records to create: {len(to_create)}")
    print(f"  - Records to update: {len(to_update)}")
    print(f"  - Skipped (no email): {skipped}")

    # Step 5: Execute changes
    if to_create:
        print(f"\nCreating {len(to_create)} new records...")
        created = create_records(to_create, dry_run=args.dry_run)
        print(f"  Created: {created}")

    if to_update:
        print(f"\nUpdating {len(to_update)} existing records...")
        updated = update_records(to_update, dry_run=args.dry_run)
        print(f"  Updated: {updated}")

    print("\n" + "=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)


if __name__ == '__main__':
    main()
