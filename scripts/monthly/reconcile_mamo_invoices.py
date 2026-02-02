"""
Reconcile MAMO POM Payments with Pharmacy Operations Invoices

This script performs a two-way reconciliation between:
- Mamo POM payments (Product Category = POM SH, POM HL, POM BG)
- Pharmacy Operations (Magenta) records

Matching is done by User ID, Email, or Phone (parallel matching).

Output categories:
- MATCHED_WITH_INVOICE: Payment matched to Pharmacy Ops with Invoice Number
- MATCHED_NO_INVOICE: Payment matched but Invoice Number is empty
- PAYMENT_NO_MATCH: Mamo payment with no matching Pharmacy Ops
- PHARMACY_NO_PAYMENT: Pharmacy Ops with no matching Mamo payment

Usage:
    python scripts/monthly/reconcile_mamo_invoices.py --month 2025-12 --audit
    python scripts/monthly/reconcile_mamo_invoices.py --month 2025-12 --export

Documentation: docs/airtable_data_architecture.md
"""

import requests
import argparse
import csv
import time
from datetime import datetime
from collections import defaultdict
import os
from dotenv import load_dotenv
load_dotenv()

# API Configuration
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
MAMO_TABLE = "tbl7WfjTqWMnsqpbs"
PHARMACY_OPS_TABLE = "tbl5MDz6ZRUosdsEQ"
USER_TABLE = "tblMtIskMF3X3nKWC"

POM_CATEGORIES = ["POM SH", "POM HL", "POM BG"]

headers = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json"
}


def parse_month(month_str):
    """Parse month string like '2025-12' into year and month"""
    parts = month_str.split("-")
    return int(parts[0]), int(parts[1])


def normalize_phone(phone):
    """Normalize phone number for matching"""
    if not phone:
        return None
    # Remove common prefixes and non-digits
    phone = str(phone).strip()
    phone = phone.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if len(phone) < 7:
        return None
    return phone


def normalize_email(email):
    """Normalize email for matching"""
    if not email:
        return None
    return email.strip().lower()


def fetch_all_records(table_id, filter_formula=None):
    """Fetch all records from an Airtable table with pagination"""
    all_records = []
    offset = None

    while True:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        if filter_formula:
            params["filterByFormula"] = filter_formula

        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            print(f"   Error fetching {table_id}: {resp.status_code}")
            break

        data = resp.json()
        all_records.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break
        time.sleep(0.2)

    return all_records


def fetch_mamo_pom_payments(year, month):
    """Fetch Mamo POM payments for the specified month"""
    print(f"Fetching Mamo POM payments for {year}-{month:02d}...")

    # Build date filter
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    filter_formula = f'AND({{status}}="captured", IS_AFTER({{created_date}}, "{start_date}"), IS_BEFORE({{created_date}}, "{end_date}"))'

    all_records = fetch_all_records(MAMO_TABLE, filter_formula)

    # Filter for POM categories
    pom_payments = []
    excluded_no_product = 0
    excluded_non_pom = 0
    category_counts = defaultdict(int)

    for r in all_records:
        fields = r.get("fields", {})
        product_cat = fields.get("Product Category", [])

        if not product_cat:
            excluded_no_product += 1
            continue

        # Check if any category is POM
        is_pom = False
        for cat in product_cat:
            if cat in POM_CATEGORIES:
                is_pom = True
                category_counts[cat] += 1
                break

        if is_pom:
            pom_payments.append({
                "record_id": r["id"],
                "id": fields.get("id", ""),
                "created_date": fields.get("created_date", ""),
                "amount": fields.get("amount", 0),
                "sender_name": fields.get("senderName", "") or fields.get("customer_details_name", ""),
                "sender_email": normalize_email(fields.get("senderEmail", "") or fields.get("customer_details_email", "")),
                "sender_phone": normalize_phone(fields.get("senderMobile", "") or fields.get("customer_details_phone_number", "")),
                "user_link": fields.get("User", []),
                "product_category": product_cat[0] if product_cat else "",
                "subscription_id": fields.get("subscription_id", ""),
            })
        else:
            excluded_non_pom += 1

    print(f"  Total captured: {len(all_records)}")
    print(f"  POM payments: {len(pom_payments)}")
    for cat in POM_CATEGORIES:
        if category_counts[cat]:
            print(f"    - {cat}: {category_counts[cat]}")
    print(f"  Excluded (no product): {excluded_no_product}")
    print(f"  Excluded (non-POM): {excluded_non_pom}")

    return pom_payments


def fetch_pharmacy_ops(year, month):
    """Fetch Pharmacy Operations for the specified month"""
    print(f"\nFetching Pharmacy Operations for {year}-{month:02d}...")

    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    filter_formula = f'AND(IS_AFTER({{Date}}, "{start_date}"), IS_BEFORE({{Date}}, "{end_date}"))'

    all_records = fetch_all_records(PHARMACY_OPS_TABLE, filter_formula)

    # Process records
    pharmacy_ops = []
    with_invoice = 0
    without_invoice = 0

    for r in all_records:
        fields = r.get("fields", {})
        invoice = fields.get("Invoice Number", "")

        if invoice:
            with_invoice += 1
        else:
            without_invoice += 1

        pharmacy_ops.append({
            "record_id": r["id"],
            "date": fields.get("Date", ""),
            "invoice_number": invoice,
            "status": fields.get("Status", ""),
            "user_link": fields.get("User", []),
            "email_input": normalize_email(fields.get("email_input", "")),
            "phone": normalize_phone(fields.get("Phone Number", "")),
            "patient_name": fields.get("Patient Name", ""),
            "trigger_by": fields.get("Trigger by", ""),
        })

    print(f"  Total records: {len(pharmacy_ops)}")
    print(f"  With Invoice: {with_invoice}")
    print(f"  Without Invoice: {without_invoice}")

    return pharmacy_ops


def build_pharmacy_index(pharmacy_ops):
    """Build lookup indexes for Pharmacy Operations"""
    by_user_id = defaultdict(list)
    by_email = defaultdict(list)
    by_phone = defaultdict(list)

    for op in pharmacy_ops:
        # Index by User link
        user_links = op.get("user_link", [])
        if user_links:
            user_id = user_links[0] if isinstance(user_links, list) else user_links
            by_user_id[user_id].append(op)

        # Index by email
        email = op.get("email_input")
        if email:
            by_email[email].append(op)

        # Index by phone
        phone = op.get("phone")
        if phone:
            by_phone[phone].append(op)

    return by_user_id, by_email, by_phone


def build_mamo_index(mamo_payments):
    """Build lookup indexes for Mamo payments"""
    by_user_id = defaultdict(list)
    by_email = defaultdict(list)
    by_phone = defaultdict(list)

    for payment in mamo_payments:
        # Index by User link
        user_links = payment.get("user_link", [])
        if user_links:
            user_id = user_links[0] if isinstance(user_links, list) else user_links
            by_user_id[user_id].append(payment)

        # Index by email
        email = payment.get("sender_email")
        if email:
            by_email[email].append(payment)

        # Index by phone
        phone = payment.get("sender_phone")
        if phone:
            by_phone[phone].append(payment)

    return by_user_id, by_email, by_phone


def reconcile(mamo_payments, pharmacy_ops):
    """Perform two-way reconciliation"""
    print("\nReconciling...")

    # Build indexes
    pharm_by_user, pharm_by_email, pharm_by_phone = build_pharmacy_index(pharmacy_ops)
    mamo_by_user, mamo_by_email, mamo_by_phone = build_mamo_index(mamo_payments)

    results = []
    matched_pharmacy_ids = set()
    matched_mamo_ids = set()

    # Direction 1: Mamo → Pharmacy
    for payment in mamo_payments:
        matched_ops = []
        match_method = None

        # Try matching by User ID
        user_links = payment.get("user_link", [])
        if user_links:
            user_id = user_links[0] if isinstance(user_links, list) else user_links
            if user_id in pharm_by_user:
                matched_ops = pharm_by_user[user_id]
                match_method = "user_id"

        # Try matching by email if no user match
        if not matched_ops and payment.get("sender_email"):
            email = payment["sender_email"]
            if email in pharm_by_email:
                matched_ops = pharm_by_email[email]
                match_method = "email"

        # Try matching by phone if still no match
        if not matched_ops and payment.get("sender_phone"):
            phone = payment["sender_phone"]
            if phone in pharm_by_phone:
                matched_ops = pharm_by_phone[phone]
                match_method = "phone"

        if matched_ops:
            # Use first match (could be enhanced to find closest date)
            matched_op = matched_ops[0]
            has_invoice = bool(matched_op.get("invoice_number"))

            status = "MATCHED_WITH_INVOICE" if has_invoice else "MATCHED_NO_INVOICE"

            results.append({
                "status": status,
                "mamo_payment_id": payment["id"],
                "mamo_record_id": payment["record_id"],
                "payment_date": payment["created_date"],
                "amount": payment["amount"],
                "customer_name": payment["sender_name"],
                "customer_email": payment["sender_email"] or "",
                "product_category": payment["product_category"],
                "invoice_number": matched_op.get("invoice_number", ""),
                "pharmacy_status": matched_op.get("status", ""),
                "pharmacy_date": matched_op.get("date", ""),
                "match_method": match_method,
                "pharmacy_record_id": matched_op["record_id"],
            })

            matched_mamo_ids.add(payment["record_id"])
            matched_pharmacy_ids.add(matched_op["record_id"])
        else:
            # No match found
            results.append({
                "status": "PAYMENT_NO_MATCH",
                "mamo_payment_id": payment["id"],
                "mamo_record_id": payment["record_id"],
                "payment_date": payment["created_date"],
                "amount": payment["amount"],
                "customer_name": payment["sender_name"],
                "customer_email": payment["sender_email"] or "",
                "product_category": payment["product_category"],
                "invoice_number": "",
                "pharmacy_status": "",
                "pharmacy_date": "",
                "match_method": "",
                "pharmacy_record_id": "",
            })
            matched_mamo_ids.add(payment["record_id"])

    # Direction 2: Pharmacy → Mamo (find unmatched pharmacy ops)
    for op in pharmacy_ops:
        if op["record_id"] in matched_pharmacy_ids:
            continue

        # This pharmacy op was not matched to any Mamo payment
        results.append({
            "status": "PHARMACY_NO_PAYMENT",
            "mamo_payment_id": "",
            "mamo_record_id": "",
            "payment_date": "",
            "amount": 0,
            "customer_name": op.get("patient_name", ""),
            "customer_email": op.get("email_input", ""),
            "product_category": "",
            "invoice_number": op.get("invoice_number", ""),
            "pharmacy_status": op.get("status", ""),
            "pharmacy_date": op.get("date", ""),
            "match_method": "",
            "pharmacy_record_id": op["record_id"],
        })

    return results


def generate_summary(results):
    """Generate summary statistics"""
    summary = {
        "MATCHED_WITH_INVOICE": 0,
        "MATCHED_NO_INVOICE": 0,
        "PAYMENT_NO_MATCH": 0,
        "PHARMACY_NO_PAYMENT": 0,
        "total_matched_amount": 0,
        "total_unmatched_amount": 0,
    }

    for r in results:
        status = r["status"]
        summary[status] = summary.get(status, 0) + 1

        if status in ["MATCHED_WITH_INVOICE", "MATCHED_NO_INVOICE"]:
            summary["total_matched_amount"] += r.get("amount", 0) or 0
        elif status == "PAYMENT_NO_MATCH":
            summary["total_unmatched_amount"] += r.get("amount", 0) or 0

    return summary


def print_audit_report(results, summary, mamo_count, pharmacy_count):
    """Print audit report to console"""
    print("\n" + "=" * 60)
    print("RECONCILIATION RESULTS")
    print("=" * 60)

    total_payments = summary["MATCHED_WITH_INVOICE"] + summary["MATCHED_NO_INVOICE"] + summary["PAYMENT_NO_MATCH"]
    match_rate = (summary["MATCHED_WITH_INVOICE"] + summary["MATCHED_NO_INVOICE"]) / total_payments * 100 if total_payments else 0

    print(f"\n  Mamo POM payments processed: {mamo_count}")
    print(f"  Pharmacy Ops processed: {pharmacy_count}")

    print(f"\n  MATCHED_WITH_INVOICE:   {summary['MATCHED_WITH_INVOICE']:>4} (AED {summary['total_matched_amount']:,.2f})")
    print(f"  MATCHED_NO_INVOICE:     {summary['MATCHED_NO_INVOICE']:>4} (Pharmacy needs to add invoice)")
    print(f"  PAYMENT_NO_MATCH:       {summary['PAYMENT_NO_MATCH']:>4} (AED {summary['total_unmatched_amount']:,.2f})")
    print(f"  PHARMACY_NO_PAYMENT:    {summary['PHARMACY_NO_PAYMENT']:>4} (Pharmacy record without Mamo payment)")

    print(f"\n  Match Rate: {match_rate:.1f}%")

    # Show samples of problem cases
    no_invoice = [r for r in results if r["status"] == "MATCHED_NO_INVOICE"]
    if no_invoice:
        print(f"\n{'=' * 60}")
        print("MATCHED_NO_INVOICE (Pharmacy needs to add invoice):")
        for r in no_invoice[:5]:
            print(f"  {r['mamo_payment_id']}: {r['customer_email']} - AED {r['amount']:.2f} - {r['pharmacy_status']}")
        if len(no_invoice) > 5:
            print(f"  ... and {len(no_invoice) - 5} more")

    no_match = [r for r in results if r["status"] == "PAYMENT_NO_MATCH"]
    if no_match:
        print(f"\n{'=' * 60}")
        print("PAYMENT_NO_MATCH (No Pharmacy Ops record found):")
        for r in no_match[:5]:
            print(f"  {r['mamo_payment_id']}: {r['customer_email']} - AED {r['amount']:.2f} - {r['product_category']}")
        if len(no_match) > 5:
            print(f"  ... and {len(no_match) - 5} more")

    pharmacy_no_pay = [r for r in results if r["status"] == "PHARMACY_NO_PAYMENT"]
    if pharmacy_no_pay:
        print(f"\n{'=' * 60}")
        print("PHARMACY_NO_PAYMENT (No Mamo payment found):")
        for r in pharmacy_no_pay[:5]:
            inv = r['invoice_number'] or "(no invoice)"
            print(f"  {inv}: {r['customer_email']} - {r['pharmacy_status']}")
        if len(pharmacy_no_pay) > 5:
            print(f"  ... and {len(pharmacy_no_pay) - 5} more")


def generate_csv_report(results, filename):
    """Generate CSV report for accounting"""
    columns = [
        "status",
        "mamo_payment_id",
        "payment_date",
        "amount",
        "customer_name",
        "customer_email",
        "product_category",
        "invoice_number",
        "pharmacy_status",
        "pharmacy_date",
        "match_method",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"\nExported to: {filename}")


def main():
    parser = argparse.ArgumentParser(description="Reconcile MAMO POM Payments with Pharmacy Operations")
    parser.add_argument("--month", required=True, help="Target month (YYYY-MM)")
    parser.add_argument("--audit", action="store_true", help="Audit mode - display results")
    parser.add_argument("--export", action="store_true", help="Export CSV for accounting")
    parser.add_argument("--output", default=None, help="Output CSV filename")
    args = parser.parse_args()

    if not args.audit and not args.export:
        print("Please specify --audit or --export (or both)")
        return

    year, month = parse_month(args.month)

    print("=" * 60)
    print(f"MAMO POM RECONCILIATION - {year}-{month:02d}")
    print("=" * 60)

    # Fetch data
    mamo_payments = fetch_mamo_pom_payments(year, month)
    pharmacy_ops = fetch_pharmacy_ops(year, month)

    # Reconcile
    results = reconcile(mamo_payments, pharmacy_ops)
    summary = generate_summary(results)

    if args.audit:
        print_audit_report(results, summary, len(mamo_payments), len(pharmacy_ops))

    if args.export:
        output_file = args.output or f"data/csv/mamo_pom_reconciliation_{year}_{month:02d}.csv"
        generate_csv_report(results, output_file)

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
