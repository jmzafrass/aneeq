#!/usr/bin/env python3
"""
Generate purchase_retention.csv and ltv_by_category_sku.csv from allorders.csv.

Reverse-engineered from dashboard/src/lib/orders/compute.ts
Replicates the exact cohort retention and cumulative LTV algorithms.

Usage:
    python3 scripts/dashboard/generate_retention_ltv.py
    python3 scripts/dashboard/generate_retention_ltv.py --dry-run
"""

import csv
import os
import re
import sys
from datetime import date
from collections import defaultdict
from typing import Dict, Set, List, Optional, Tuple

# =============================================================================
# Paths
# =============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, 'dashboard', 'public', 'data')
ALLORDERS_CSV = os.path.join(DATA_DIR, 'allorders.csv')
RETENTION_CSV = os.path.join(DATA_DIR, 'purchase_retention.csv')
LTV_CSV = os.path.join(DATA_DIR, 'ltv_by_category_sku.csv')

# =============================================================================
# Constants (from compute.ts)
# =============================================================================

CATEGORY_PRIORITY = ["pom hl", "pom bg", "pom sh", "otc hl", "otc sh", "otc sk"]
SUBSCRIPTION_CATEGORIES = {"pom hl", "pom bg"}
MAX_OFFSET = 12  # compute.ts uses offsets 0..12


# =============================================================================
# Helper Functions
# =============================================================================

def ym(d: date) -> str:
    """Format date as YYYY-MM (matches compute.ts ym())."""
    return f"{d.year}-{d.month:02d}"


def add_months(d: date, months: int) -> date:
    """Add months to a date, returning first of that month.
    Matches compute.ts addMonths(): new Date(y, m + months, 1)."""
    total = d.year * 12 + (d.month - 1) + months
    y = total // 12
    m = total % 12 + 1
    return date(y, m, 1)


def clamp_as_of_month(max_month: str) -> str:
    """Clamp to min(max_month, last fully completed calendar month).
    Matches compute.ts clampAsOfMonth()."""
    today = date.today()
    # Last fully completed month = previous month's 1st
    if today.month == 1:
        last_full = date(today.year - 1, 12, 1)
    else:
        last_full = date(today.year, today.month - 1, 1)
    baseline = ym(last_full)
    if not max_month:
        return baseline
    return max_month if max_month < baseline else baseline


def parse_date_ddmmyyyy(raw: str) -> Optional[date]:
    """Parse dd/mm/yyyy date. Our allorders.csv uses this format exclusively."""
    if not raw or not raw.strip():
        return None
    raw = raw.strip().split(' ')[0]
    try:
        parts = raw.replace('-', '/').split('/')
        if len(parts) != 3:
            return None
        if len(parts[0]) == 4:
            # YYYY-MM-DD
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        else:
            # DD/MM/YYYY
            return date(int(parts[2]), int(parts[1]), int(parts[0]))
    except (ValueError, IndexError):
        return None


def split_values(raw: str) -> List[str]:
    """Split semicolon/comma-separated values, lowercase and strip.
    Matches compute.ts splitValues()."""
    if not raw:
        return []
    return [v.strip().lower() for v in re.split(r'[;,]', raw) if v.strip()]


def prioritize_category(categories: List[str]) -> str:
    """Pick highest-priority category from list.
    Matches compute.ts prioritizeCategory()."""
    unique = list(dict.fromkeys(c for c in categories if c))
    priority_map = {cat: i for i, cat in enumerate(CATEGORY_PRIORITY)}
    unique.sort(key=lambda c: (priority_map.get(c, float('inf')), c))
    return unique[0] if unique else ""


def to_number(raw: str) -> float:
    """Parse price string to float. Matches compute.ts toNumber()."""
    if not raw:
        return 0.0
    cleaned = raw.replace(',', '')
    match = re.search(r'[-+]?\d*\.?\d+', cleaned)
    if not match:
        return 0.0
    val = float(match.group(0))
    return val if val == val else 0.0  # NaN guard


# =============================================================================
# Order Data Structure
# =============================================================================

class Order:
    __slots__ = ('id', 'uid', 'date', 'month_key', 'price', 'categories', 'skus', 'notes')

    def __init__(self, oid: str, uid: str, d: date, price: float,
                 categories: List[str], skus: List[str], notes: str):
        self.id = oid
        self.uid = uid
        self.date = d
        self.month_key = ym(d)
        self.price = price
        self.categories = categories
        self.skus = skus
        self.notes = notes


# =============================================================================
# CSV Loading
# =============================================================================

def load_orders(csv_path: str) -> List[Order]:
    """Load delivered orders from allorders.csv.
    Matches compute.ts parseOrders() filter: status === 'delivered', uid required."""
    orders = []
    skipped_status = 0
    skipped_date = 0
    skipped_uid = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            status = (row.get('Status Order', '') or '').strip().lower()
            if status != 'delivered':
                skipped_status += 1
                continue

            d = parse_date_ddmmyyyy(row.get('Order Date', ''))
            if d is None:
                skipped_date += 1
                continue

            uid = (row.get('name_uid', '') or '').strip()
            if not uid:
                skipped_uid += 1
                continue

            order_id = (row.get('Order_id', '') or '').strip()
            if not order_id:
                order_id = f"{ym(d)}:{hash(str(row))}"

            price = to_number(row.get('Price', ''))
            categories = split_values(row.get('Category', ''))
            skus = split_values(row.get('SKUs', ''))
            notes = row.get('Notes', '') or ''

            orders.append(Order(order_id, uid, d, price, categories, skus, notes))

    if skipped_status or skipped_date or skipped_uid:
        print(f"  Skipped: {skipped_status} non-delivered, {skipped_date} bad date, {skipped_uid} no uid")

    return orders


# =============================================================================
# Core Computation (mirrors compute.ts computeAllFromOrders)
# =============================================================================

def compute_retention_and_ltv(orders: List[Order]) -> Tuple[List[dict], List[dict]]:
    """Compute cohort retention and cumulative LTV.
    Exact port of compute.ts lines 527-725."""

    if not orders:
        return [], []

    # --- asOfMonth ---
    max_month = max(o.month_key for o in orders)
    as_of_month = clamp_as_of_month(max_month)
    print(f"  Max month in data: {max_month}")
    print(f"  asOfMonth (clamped): {as_of_month}")

    # --- Group orders by uid, find first month & first category ---
    orders_by_uid: Dict[str, List[Order]] = defaultdict(list)
    for o in orders:
        orders_by_uid[o.uid].append(o)

    uid_first_month: Dict[str, str] = {}
    uid_first_category: Dict[str, str] = {}

    for uid, user_orders in orders_by_uid.items():
        user_orders.sort(key=lambda o: o.date)
        first_month = ym(user_orders[0].date)
        uid_first_month[uid] = first_month
        same_month = [o for o in user_orders if ym(o.date) == first_month]
        all_cats = []
        for o in same_month:
            all_cats.extend(o.categories)
        uid_first_category[uid] = prioritize_category(all_cats)

    # --- Purchase month sets (lines 544-557) ---
    purchases_by_uid: Dict[str, Set[str]] = defaultdict(set)
    purchases_by_uid_by_cat: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))

    for o in orders:
        month = ym(o.date)
        if month > as_of_month:
            continue
        purchases_by_uid[o.uid].add(month)
        for cat in o.categories:
            purchases_by_uid_by_cat[o.uid][cat].add(month)

    # --- Revenue maps (lines 632-650) ---
    revenue_by_uid: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    revenue_by_uid_by_cat: Dict[str, Dict[str, Dict[str, float]]] = \
        defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    for o in orders:
        month = ym(o.date)
        if month > as_of_month:
            continue
        revenue_by_uid[o.uid][month] += o.price
        if o.categories:
            share = o.price / len(o.categories)
            for cat in o.categories:
                revenue_by_uid_by_cat[o.uid][cat][month] += share

    # --- Build cohorts ---
    # Overall: cohort_month → set of uids (lines 561-565)
    overall_cohorts: Dict[str, Set[str]] = defaultdict(set)
    for uid, cohort in uid_first_month.items():
        overall_cohorts[cohort].add(uid)

    # Category: cohort_month → category → set of uids (lines 588-596)
    category_cohorts: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
    for uid, cohort in uid_first_month.items():
        cat = uid_first_category.get(uid, '')
        if not cat:
            continue
        category_cohorts[cohort][cat].add(uid)

    # =================================================================
    # RETENTION (lines 559-630)
    # =================================================================
    retention_rows: List[dict] = []

    # Overall retention (lines 567-586)
    for cohort_month in sorted(overall_cohorts.keys()):
        users = overall_cohorts[cohort_month]
        cohort_size = len(users)
        cohort_date = date(int(cohort_month[:4]), int(cohort_month[5:7]), 1)

        for offset in range(MAX_OFFSET + 1):
            target_month = ym(add_months(cohort_date, offset))
            if target_month > as_of_month:
                break

            retained = sum(
                1 for uid in users
                if target_month in purchases_by_uid.get(uid, set())
            )
            pct = (retained / cohort_size * 100) if cohort_size else 0

            retention_rows.append({
                'cohort_month': f"{cohort_month}-01",
                'dimension': 'overall',
                'first_value': 'ALL',
                'm': offset,
                'metric': 'any',
                'cohort_size': cohort_size,
                'retention': f"{pct:.2f}%",
            })

    # Category retention (lines 598-630)
    for cohort_month in sorted(category_cohorts.keys()):
        for category in sorted(category_cohorts[cohort_month].keys()):
            users = category_cohorts[cohort_month][category]
            cohort_size = len(users)
            cohort_date = date(int(cohort_month[:4]), int(cohort_month[5:7]), 1)

            for offset in range(MAX_OFFSET + 1):
                target_month = ym(add_months(cohort_date, offset))
                if target_month > as_of_month:
                    break

                retained_any = sum(
                    1 for uid in users
                    if target_month in purchases_by_uid.get(uid, set())
                )
                retained_same = sum(
                    1 for uid in users
                    if target_month in purchases_by_uid_by_cat.get(uid, {}).get(category, set())
                )

                pct_any = (retained_any / cohort_size * 100) if cohort_size else 0
                pct_same = (retained_same / cohort_size * 100) if cohort_size else 0

                retention_rows.append({
                    'cohort_month': f"{cohort_month}-01",
                    'dimension': 'category',
                    'first_value': category,
                    'm': offset,
                    'metric': 'any',
                    'cohort_size': cohort_size,
                    'retention': f"{pct_any:.2f}%",
                })
                retention_rows.append({
                    'cohort_month': f"{cohort_month}-01",
                    'dimension': 'category',
                    'first_value': category,
                    'm': offset,
                    'metric': 'same',
                    'cohort_size': cohort_size,
                    'retention': f"{pct_same:.2f}%",
                })

    # =================================================================
    # LTV (lines 632-725)
    # =================================================================
    ltv_rows: List[dict] = []

    # Overall LTV (lines 654-678)
    for cohort_month in sorted(overall_cohorts.keys()):
        users = overall_cohorts[cohort_month]
        cohort_size = len(users)
        cohort_date = date(int(cohort_month[:4]), int(cohort_month[5:7]), 1)

        for offset in range(MAX_OFFSET + 1):
            target_date = add_months(cohort_date, offset)
            if ym(target_date) > as_of_month:
                break

            # Cumulative revenue from month 0 through month offset
            total = 0.0
            for uid in users:
                month_rev = revenue_by_uid.get(uid, {})
                for step in range(offset + 1):
                    key = ym(add_months(cohort_date, step))
                    total += month_rev.get(key, 0)

            ltv = round(total / cohort_size, 2) if cohort_size else 0

            ltv_rows.append({
                'cohort_type': 'purchase',
                'cohort_month': f"{cohort_month}-01",
                'dimension': 'overall',
                'first_value': 'ALL',
                'm': offset,
                'metric': 'any',
                'measure': 'gross_margin',
                'cohort_size': cohort_size,
                'ltv_per_user': ltv,
            })

    # Category LTV (lines 681-725)
    for cohort_month in sorted(category_cohorts.keys()):
        for category in sorted(category_cohorts[cohort_month].keys()):
            users = category_cohorts[cohort_month][category]
            cohort_size = len(users)
            cohort_date = date(int(cohort_month[:4]), int(cohort_month[5:7]), 1)

            for offset in range(MAX_OFFSET + 1):
                target_date = add_months(cohort_date, offset)
                if ym(target_date) > as_of_month:
                    break

                total_any = 0.0
                total_same = 0.0
                for uid in users:
                    # "any" = all revenue across all categories
                    month_rev = revenue_by_uid.get(uid, {})
                    for step in range(offset + 1):
                        key = ym(add_months(cohort_date, step))
                        total_any += month_rev.get(key, 0)

                    # "same" = revenue only from this specific category
                    cat_rev = revenue_by_uid_by_cat.get(uid, {}).get(category, {})
                    for step in range(offset + 1):
                        key = ym(add_months(cohort_date, step))
                        total_same += cat_rev.get(key, 0)

                ltv_any = round(total_any / cohort_size, 2) if cohort_size else 0
                ltv_same = round(total_same / cohort_size, 2) if cohort_size else 0

                ltv_rows.append({
                    'cohort_type': 'purchase',
                    'cohort_month': f"{cohort_month}-01",
                    'dimension': 'category',
                    'first_value': category,
                    'm': offset,
                    'metric': 'any',
                    'measure': 'gross_margin',
                    'cohort_size': cohort_size,
                    'ltv_per_user': ltv_any,
                })
                ltv_rows.append({
                    'cohort_type': 'purchase',
                    'cohort_month': f"{cohort_month}-01",
                    'dimension': 'category',
                    'first_value': category,
                    'm': offset,
                    'metric': 'same',
                    'measure': 'gross_margin',
                    'cohort_size': cohort_size,
                    'ltv_per_user': ltv_same,
                })

    return retention_rows, ltv_rows


# =============================================================================
# CSV Writers
# =============================================================================

def write_retention_csv(rows: List[dict], filepath: str) -> int:
    fieldnames = ['cohort_month', 'dimension', 'first_value', 'm', 'metric', 'cohort_size', 'retention']
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def write_ltv_csv(rows: List[dict], filepath: str) -> int:
    fieldnames = ['cohort_type', 'cohort_month', 'dimension', 'first_value',
                  'm', 'metric', 'measure', 'cohort_size', 'ltv_per_user']
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


# =============================================================================
# Main
# =============================================================================

def main():
    dry_run = '--dry-run' in sys.argv

    print("=" * 60)
    print("GENERATE RETENTION & LTV CSVs")
    print("Reverse-engineered from dashboard/src/lib/orders/compute.ts")
    if dry_run:
        print("  *** DRY RUN — no files will be written ***")
    print("=" * 60)

    print(f"\n1. LOADING ORDERS")
    print(f"  Source: {ALLORDERS_CSV}")
    orders = load_orders(ALLORDERS_CSV)
    unique_uids = set(o.uid for o in orders)
    unique_months = sorted(set(o.month_key for o in orders))
    print(f"  Delivered orders: {len(orders)}")
    print(f"  Unique customers: {len(unique_uids)}")
    print(f"  Date range: {unique_months[0] if unique_months else '?'} → {unique_months[-1] if unique_months else '?'}")

    # Category breakdown
    cat_counts: Dict[str, int] = defaultdict(int)
    for o in orders:
        for c in o.categories:
            cat_counts[c] += 1
    print(f"\n  Categories in orders:")
    for cat in sorted(cat_counts.keys()):
        print(f"    {cat:20s} {cat_counts[cat]:,}")

    print(f"\n2. COMPUTING COHORT METRICS")
    retention_rows, ltv_rows = compute_retention_and_ltv(orders)

    # Summaries
    ret_overall = [r for r in retention_rows if r['dimension'] == 'overall']
    ret_category = [r for r in retention_rows if r['dimension'] == 'category']
    ltv_overall = [r for r in ltv_rows if r['dimension'] == 'overall']
    ltv_category = [r for r in ltv_rows if r['dimension'] == 'category']

    ret_cohorts = sorted(set(r['cohort_month'] for r in retention_rows))
    ltv_cohorts = sorted(set(r['cohort_month'] for r in ltv_rows))

    print(f"\n  RETENTION:")
    print(f"    Overall rows:  {len(ret_overall)}")
    print(f"    Category rows: {len(ret_category)}")
    print(f"    Total rows:    {len(retention_rows)}")
    print(f"    Cohorts:       {len(ret_cohorts)} ({ret_cohorts[0] if ret_cohorts else '?'} → {ret_cohorts[-1] if ret_cohorts else '?'})")

    # Show overall cohort sizes
    print(f"\n    Overall cohort sizes:")
    seen_cohorts = set()
    for r in ret_overall:
        cm = r['cohort_month']
        if cm not in seen_cohorts and r['m'] == 0:
            seen_cohorts.add(cm)
            print(f"      {cm}: {r['cohort_size']} users, retention m0={r['retention']}")

    # Category cohort breakdown
    cat_in_ret = sorted(set(r['first_value'] for r in ret_category))
    print(f"\n    Categories in retention: {', '.join(cat_in_ret)}")

    print(f"\n  LTV:")
    print(f"    Overall rows:  {len(ltv_overall)}")
    print(f"    Category rows: {len(ltv_category)}")
    print(f"    Total rows:    {len(ltv_rows)}")
    print(f"    Cohorts:       {len(ltv_cohorts)} ({ltv_cohorts[0] if ltv_cohorts else '?'} → {ltv_cohorts[-1] if ltv_cohorts else '?'})")

    # Show overall LTV at m=0 for each cohort
    print(f"\n    Overall LTV (m=0) by cohort:")
    for r in ltv_overall:
        if r['m'] == 0:
            print(f"      {r['cohort_month']}: {r['cohort_size']} users, LTV/user = {r['ltv_per_user']}")

    if dry_run:
        print(f"\n3. DRY RUN — skipping file writes")
    else:
        print(f"\n3. WRITING CSV FILES")
        n_ret = write_retention_csv(retention_rows, RETENTION_CSV)
        print(f"  Wrote {n_ret} rows → {RETENTION_CSV}")

        n_ltv = write_ltv_csv(ltv_rows, LTV_CSV)
        print(f"  Wrote {n_ltv} rows → {LTV_CSV}")

    # Spot checks
    print(f"\n4. SPOT CHECKS")

    # Check: m=0 retention should always be 100%
    bad_m0 = [r for r in retention_rows if r['m'] == 0 and r['retention'] != '100.00%']
    if bad_m0:
        print(f"  WARNING: {len(bad_m0)} rows have m=0 retention != 100%")
        for r in bad_m0[:5]:
            print(f"    {r}")
    else:
        print(f"  OK: All m=0 retention = 100.00%")

    # Check: LTV should be monotonically non-decreasing per cohort
    ltv_issues = 0
    for cm in sorted(set(r['cohort_month'] for r in ltv_overall)):
        cohort_rows = sorted(
            [r for r in ltv_overall if r['cohort_month'] == cm],
            key=lambda r: r['m']
        )
        prev = 0
        for r in cohort_rows:
            if r['ltv_per_user'] < prev:
                ltv_issues += 1
                if ltv_issues <= 3:
                    print(f"  WARNING: LTV decreased at {cm} m={r['m']}: {r['ltv_per_user']} < {prev}")
            prev = r['ltv_per_user']

    if ltv_issues == 0:
        print(f"  OK: Overall LTV is monotonically non-decreasing for all cohorts")
    elif ltv_issues > 3:
        print(f"  ... and {ltv_issues - 3} more LTV decrease warnings")

    # Check: retention categories match LTV categories
    ltv_cats = sorted(set(r['first_value'] for r in ltv_category))
    if cat_in_ret == ltv_cats:
        print(f"  OK: Retention and LTV have same categories")
    else:
        print(f"  WARNING: Category mismatch — Ret: {cat_in_ret}, LTV: {ltv_cats}")

    print("\n" + "=" * 60)
    if dry_run:
        print("DRY RUN COMPLETE — no files written")
    else:
        print("DONE — CSV files generated successfully")
    print("=" * 60)


if __name__ == '__main__':
    main()
