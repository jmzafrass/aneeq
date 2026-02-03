#!/usr/bin/env python3
"""
Generate purchase_retention.csv and ltv_by_category_sku.csv from allorders.csv.

Uses subscription-aware retention: subscribers are counted as "active" (retained)
for the full duration of their billing cadence, not just when they make a purchase.
This matches the logic in dashboard/src/lib/orders/churn.ts.

Generates 3 segments per cohort:
  - "all"         = all customers, subscription-aware
  - "subscribers"  = only customers whose first purchase included a subscription (POM HL/BG)
  - "onetime"      = only non-subscription first-purchase customers, purchase-based

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
# Constants (from compute.ts / constants.ts)
# =============================================================================

CATEGORY_PRIORITY = ["pom hl", "pom bg", "pom sh", "otc hl", "otc sh", "otc sk"]
SUBSCRIPTION_CATEGORIES = {"pom hl", "pom bg"}
MAX_OFFSET = 12  # compute.ts uses offsets 0..12

# Magenta pricing started July 2025
MAGENTA_START_KEY = "2025-07"

# COGS per SKU (matches dashboard/src/lib/orders/catalogue.ts)
LEGACY_COGS: Dict[str, float] = {
    "ultimate revival": 465.12,
    "power regrowth": 444.21,
    "essential boost": 235.75,
    "oral mix": 233.74,
    "oral minoxidil": 214.99,
    "vital recharge": 235.75,
    "max power": 332.95,
    "delay spray": 69.04,
    "essential routine": 62.32,
    "advanced routine": 80.48,
    "cleanser": 23.73,
    "moisturizer spf": 23.73,
    "moisturizer": 26.0,
    "eye cream": 28.27,
    "serum": 23.73,
    "shampoo": 23.73,
    "conditioner": 23.73,
    "regrowth hair pack": 37.35,
    "regrowth pack": 37.35,
    "beard growth serum": 159.0,
}

MAGENTA_COGS: Dict[str, float] = {
    "ultimate revival": 284.7,
    "power regrowth": 271.7,
    "essential boost": 142.35,
    "oral mix": 142.35,
    "oral minoxidil": 129.35,
    "vital recharge": 142.35,
    "max power": 207.35,
    "delay spray": 69.04,
    "essential routine": 62.32,
    "advanced routine": 80.48,
    "cleanser": 23.73,
    "moisturizer spf": 23.73,
    "moisturizer": 26.0,
    "eye cream": 28.27,
    "serum": 23.73,
    "shampoo": 23.73,
    "conditioner": 23.73,
    "regrowth hair pack": 37.35,
    "regrowth pack": 37.35,
    "beard growth serum": 159.0,
}


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


def parse_cadence(notes: str) -> int:
    """Parse billing cadence from Notes field.
    Matches churn.ts parseCadence(): extracts numbers before month/months/mo/mos,
    sums them, defaults to 1.
    Also handles plain numbers (e.g. '1', '3') that don't have 'month' suffix."""
    notes = (notes or '').strip()
    if not notes:
        return 1
    # First try "N month(s)" pattern (matches churn.ts)
    matches = re.findall(r'(\d+)\s*(?:month|months|mo|mos)', notes, re.IGNORECASE)
    if matches:
        total = sum(int(m) for m in matches)
        return total if total > 0 else 1
    # Fall back to plain number
    match = re.match(r'^(\d+)$', notes)
    if match:
        val = int(match.group(1))
        return val if val > 0 else 1
    return 1


def is_subscription_order(order) -> bool:
    """Check if order contains subscription categories (POM HL or POM BG)."""
    return any(cat in SUBSCRIPTION_CATEGORIES for cat in order.categories)


def calculate_order_cogs(skus: List[str], month_key: str) -> float:
    """Calculate total COGS for an order based on SKUs and order month.
    Uses Magenta pricing from July 2025 onward."""
    cogs_table = MAGENTA_COGS if month_key >= MAGENTA_START_KEY else LEGACY_COGS
    total_cogs = 0.0
    for sku in skus:
        sku_norm = sku.lower().strip()
        total_cogs += cogs_table.get(sku_norm, 0.0)
    return total_cogs


# =============================================================================
# Order Data Structure
# =============================================================================

class Order:
    __slots__ = ('id', 'uid', 'date', 'month_key', 'price', 'cogs', 'gross_margin', 'categories', 'skus', 'notes')

    def __init__(self, oid: str, uid: str, d: date, price: float,
                 categories: List[str], skus: List[str], notes: str):
        self.id = oid
        self.uid = uid
        self.date = d
        self.month_key = ym(d)
        self.price = price
        self.cogs = calculate_order_cogs(skus, self.month_key)
        self.gross_margin = max(0.0, price - self.cogs)  # Never negative
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
# Core Computation — Subscription-Aware Retention + LTV
# =============================================================================

def compute_retention_and_ltv(orders: List[Order]) -> Tuple[List[dict], List[dict]]:
    """Compute subscription-aware cohort retention and cumulative LTV.

    For retention:
      - Subscribers are "active" for the full billing cadence period after each purchase.
        E.g., a 3-month subscriber who bought in Jan is active in Jan, Feb, Mar.
      - One-time buyers are active only in their purchase month.
      - Three segments: "all" (mixed), "subscribers" (sub-only), "onetime" (ot-only).

    For LTV:
      - Uses actual purchase revenue (not projected).
      - Segments control which UIDs are included in the cohort denominator.
    """

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
    uid_is_subscriber: Dict[str, bool] = {}

    for uid, user_orders in orders_by_uid.items():
        user_orders.sort(key=lambda o: o.date)
        first_month = ym(user_orders[0].date)
        uid_first_month[uid] = first_month
        same_month = [o for o in user_orders if ym(o.date) == first_month]
        all_cats = []
        for o in same_month:
            all_cats.extend(o.categories)
        uid_first_category[uid] = prioritize_category(all_cats)
        # A subscriber is someone whose first-month orders include a subscription category
        uid_is_subscriber[uid] = any(is_subscription_order(o) for o in same_month)

    sub_count = sum(1 for v in uid_is_subscriber.values() if v)
    ot_count = sum(1 for v in uid_is_subscriber.values() if not v)
    print(f"  Segment split: {sub_count} subscribers, {ot_count} one-time")

    # --- Propagate cadence for subscription orders with empty notes ---
    # Build per-customer known cadence from orders that have explicit notes
    uid_known_cadence: Dict[str, List[Tuple[date, int]]] = defaultdict(list)
    for o in orders:
        if is_subscription_order(o) and o.notes.strip():
            cadence = parse_cadence(o.notes)
            uid_known_cadence[o.uid].append((o.date, cadence))

    # Sort by date descending so most recent is first
    for uid in uid_known_cadence:
        uid_known_cadence[uid].sort(key=lambda x: x[0], reverse=True)

    # For subscription orders with no notes, inherit from same customer's most recent known order
    propagated = 0
    for o in orders:
        if is_subscription_order(o) and not o.notes.strip():
            if o.uid in uid_known_cadence:
                o.notes = str(uid_known_cadence[o.uid][0][1])
                propagated += 1
    if propagated:
        print(f"  Cadence propagation: {propagated} orders inherited from same customer")

    # --- Purchase month sets (original, for fallback / one-time) ---
    purchases_by_uid: Dict[str, Set[str]] = defaultdict(set)
    purchases_by_uid_by_cat: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))

    for o in orders:
        month = ym(o.date)
        if month > as_of_month:
            continue
        purchases_by_uid[o.uid].add(month)
        for cat in o.categories:
            purchases_by_uid_by_cat[o.uid][cat].add(month)

    # --- Subscription-aware active month sets ---
    # Mirrors churn.ts: subscribers projected forward by cadence
    active_months_by_uid: Dict[str, Set[str]] = defaultdict(set)
    active_months_by_uid_by_cat: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))

    cadence_stats = defaultdict(int)
    for o in orders:
        month = ym(o.date)
        if month > as_of_month:
            continue

        if is_subscription_order(o):
            cadence = parse_cadence(o.notes)
            cadence_stats[cadence] += 1
            for i in range(cadence):
                projected = ym(add_months(o.date, i))
                if projected > as_of_month:
                    break
                active_months_by_uid[o.uid].add(projected)
                # Category-level: only project subscription categories
                for cat in o.categories:
                    if cat in SUBSCRIPTION_CATEGORIES:
                        active_months_by_uid_by_cat[o.uid][cat].add(projected)
                    else:
                        # Non-sub categories in a sub order: only purchase month
                        if i == 0:
                            active_months_by_uid_by_cat[o.uid][cat].add(projected)
        else:
            # One-time: active only in purchase month
            active_months_by_uid[o.uid].add(month)
            for cat in o.categories:
                active_months_by_uid_by_cat[o.uid][cat].add(month)

    print(f"  Cadence distribution: {dict(sorted(cadence_stats.items()))}")

    # --- Revenue maps (what customer paid) ---
    revenue_by_uid: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    revenue_by_uid_by_cat: Dict[str, Dict[str, Dict[str, float]]] = \
        defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    # --- Gross margin maps (Revenue - COGS) ---
    margin_by_uid: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    margin_by_uid_by_cat: Dict[str, Dict[str, Dict[str, float]]] = \
        defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    for o in orders:
        month = ym(o.date)
        if month > as_of_month:
            continue
        # Revenue
        revenue_by_uid[o.uid][month] += o.price
        if o.categories:
            rev_share = o.price / len(o.categories)
            for cat in o.categories:
                revenue_by_uid_by_cat[o.uid][cat][month] += rev_share
        # Gross margin
        margin_by_uid[o.uid][month] += o.gross_margin
        if o.categories:
            margin_share = o.gross_margin / len(o.categories)
            for cat in o.categories:
                margin_by_uid_by_cat[o.uid][cat][month] += margin_share

    # --- Build cohorts ---
    # Overall: cohort_month -> set of uids
    overall_cohorts: Dict[str, Set[str]] = defaultdict(set)
    sub_cohorts: Dict[str, Set[str]] = defaultdict(set)
    ot_cohorts: Dict[str, Set[str]] = defaultdict(set)

    for uid, cohort in uid_first_month.items():
        overall_cohorts[cohort].add(uid)
        if uid_is_subscriber[uid]:
            sub_cohorts[cohort].add(uid)
        else:
            ot_cohorts[cohort].add(uid)

    # Category: cohort_month -> category -> set of uids
    category_cohorts: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
    category_sub_cohorts: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
    category_ot_cohorts: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))

    for uid, cohort in uid_first_month.items():
        cat = uid_first_category.get(uid, '')
        if not cat:
            continue
        category_cohorts[cohort][cat].add(uid)
        if uid_is_subscriber[uid]:
            category_sub_cohorts[cohort][cat].add(uid)
        else:
            category_ot_cohorts[cohort][cat].add(uid)

    # =================================================================
    # RETENTION — subscription-aware
    # =================================================================
    retention_rows: List[dict] = []

    def compute_segment_retention(
        cohort_map: Dict[str, Set[str]],
        active_map: Dict[str, Set[str]],
        segment: str,
        dimension: str,
        first_value: str,
        metric: str,
    ):
        for cohort_month in sorted(cohort_map.keys()):
            users = cohort_map[cohort_month]
            if not users:
                continue
            cohort_size = len(users)
            cohort_date = date(int(cohort_month[:4]), int(cohort_month[5:7]), 1)

            for offset in range(MAX_OFFSET + 1):
                target_month = ym(add_months(cohort_date, offset))
                if target_month > as_of_month:
                    break

                retained = sum(
                    1 for uid in users
                    if target_month in active_map.get(uid, set())
                )
                pct = (retained / cohort_size * 100) if cohort_size else 0

                retention_rows.append({
                    'cohort_month': f"{cohort_month}-01",
                    'dimension': dimension,
                    'first_value': first_value,
                    'm': offset,
                    'metric': metric,
                    'segment': segment,
                    'cohort_size': cohort_size,
                    'retention': f"{pct:.2f}%",
                })

    def compute_category_segment_retention(
        cat_cohort_map: Dict[str, Dict[str, Set[str]]],
        active_map_any: Dict[str, Set[str]],
        active_map_cat: Dict[str, Dict[str, Set[str]]],
        segment: str,
    ):
        for cohort_month in sorted(cat_cohort_map.keys()):
            for category in sorted(cat_cohort_map[cohort_month].keys()):
                users = cat_cohort_map[cohort_month][category]
                if not users:
                    continue
                cohort_size = len(users)
                cohort_date = date(int(cohort_month[:4]), int(cohort_month[5:7]), 1)

                for offset in range(MAX_OFFSET + 1):
                    target_month = ym(add_months(cohort_date, offset))
                    if target_month > as_of_month:
                        break

                    retained_any = sum(
                        1 for uid in users
                        if target_month in active_map_any.get(uid, set())
                    )
                    retained_same = sum(
                        1 for uid in users
                        if target_month in active_map_cat.get(uid, {}).get(category, set())
                    )

                    pct_any = (retained_any / cohort_size * 100) if cohort_size else 0
                    pct_same = (retained_same / cohort_size * 100) if cohort_size else 0

                    retention_rows.append({
                        'cohort_month': f"{cohort_month}-01",
                        'dimension': 'category',
                        'first_value': category,
                        'm': offset,
                        'metric': 'any',
                        'segment': segment,
                        'cohort_size': cohort_size,
                        'retention': f"{pct_any:.2f}%",
                    })
                    retention_rows.append({
                        'cohort_month': f"{cohort_month}-01",
                        'dimension': 'category',
                        'first_value': category,
                        'm': offset,
                        'metric': 'same',
                        'segment': segment,
                        'cohort_size': cohort_size,
                        'retention': f"{pct_same:.2f}%",
                    })

    # --- Segment "all": subscription-aware for everyone ---
    compute_segment_retention(overall_cohorts, active_months_by_uid, 'all', 'overall', 'ALL', 'any')
    compute_category_segment_retention(category_cohorts, active_months_by_uid, active_months_by_uid_by_cat, 'all')

    # --- Segment "subscribers": subscription-aware, subscriber UIDs only ---
    compute_segment_retention(sub_cohorts, active_months_by_uid, 'subscribers', 'overall', 'ALL', 'any')
    compute_category_segment_retention(category_sub_cohorts, active_months_by_uid, active_months_by_uid_by_cat, 'subscribers')

    # --- Segment "onetime": purchase-based, one-time UIDs only ---
    compute_segment_retention(ot_cohorts, purchases_by_uid, 'onetime', 'overall', 'ALL', 'any')
    compute_category_segment_retention(category_ot_cohorts, purchases_by_uid, purchases_by_uid_by_cat, 'onetime')

    # =================================================================
    # LTV — segmented
    # =================================================================
    ltv_rows: List[dict] = []

    def compute_segment_ltv(
        cohort_map: Dict[str, Set[str]],
        segment: str,
        dimension: str,
        first_value: str,
        metric: str,
        value_map: Dict[str, Dict[str, float]],
        measure: str,
    ):
        for cohort_month in sorted(cohort_map.keys()):
            users = cohort_map[cohort_month]
            if not users:
                continue
            cohort_size = len(users)
            cohort_date = date(int(cohort_month[:4]), int(cohort_month[5:7]), 1)

            for offset in range(MAX_OFFSET + 1):
                target_date = add_months(cohort_date, offset)
                if ym(target_date) > as_of_month:
                    break

                total = 0.0
                for uid in users:
                    month_values = value_map.get(uid, {})
                    for step in range(offset + 1):
                        key = ym(add_months(cohort_date, step))
                        total += month_values.get(key, 0)

                ltv = round(total / cohort_size, 2) if cohort_size else 0

                ltv_rows.append({
                    'cohort_type': 'purchase',
                    'cohort_month': f"{cohort_month}-01",
                    'dimension': dimension,
                    'first_value': first_value,
                    'm': offset,
                    'metric': metric,
                    'measure': measure,
                    'segment': segment,
                    'cohort_size': cohort_size,
                    'ltv_per_user': ltv,
                })

    def compute_category_segment_ltv(
        cat_cohort_map: Dict[str, Dict[str, Set[str]]],
        segment: str,
        value_by_uid: Dict[str, Dict[str, float]],
        value_by_uid_by_cat: Dict[str, Dict[str, Dict[str, float]]],
        measure: str,
    ):
        for cohort_month in sorted(cat_cohort_map.keys()):
            for category in sorted(cat_cohort_map[cohort_month].keys()):
                users = cat_cohort_map[cohort_month][category]
                if not users:
                    continue
                cohort_size = len(users)
                cohort_date = date(int(cohort_month[:4]), int(cohort_month[5:7]), 1)

                for offset in range(MAX_OFFSET + 1):
                    target_date = add_months(cohort_date, offset)
                    if ym(target_date) > as_of_month:
                        break

                    total_any = 0.0
                    total_same = 0.0
                    for uid in users:
                        month_values = value_by_uid.get(uid, {})
                        for step in range(offset + 1):
                            key = ym(add_months(cohort_date, step))
                            total_any += month_values.get(key, 0)

                        cat_values = value_by_uid_by_cat.get(uid, {}).get(category, {})
                        for step in range(offset + 1):
                            key = ym(add_months(cohort_date, step))
                            total_same += cat_values.get(key, 0)

                    ltv_any = round(total_any / cohort_size, 2) if cohort_size else 0
                    ltv_same = round(total_same / cohort_size, 2) if cohort_size else 0

                    ltv_rows.append({
                        'cohort_type': 'purchase',
                        'cohort_month': f"{cohort_month}-01",
                        'dimension': 'category',
                        'first_value': category,
                        'm': offset,
                        'metric': 'any',
                        'measure': measure,
                        'segment': segment,
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
                        'measure': measure,
                        'segment': segment,
                        'cohort_size': cohort_size,
                        'ltv_per_user': ltv_same,
                    })

    # Overall LTV by segment - REVENUE
    compute_segment_ltv(overall_cohorts, 'all', 'overall', 'ALL', 'any', revenue_by_uid, 'revenue')
    compute_segment_ltv(sub_cohorts, 'subscribers', 'overall', 'ALL', 'any', revenue_by_uid, 'revenue')
    compute_segment_ltv(ot_cohorts, 'onetime', 'overall', 'ALL', 'any', revenue_by_uid, 'revenue')

    # Overall LTV by segment - GROSS MARGIN
    compute_segment_ltv(overall_cohorts, 'all', 'overall', 'ALL', 'any', margin_by_uid, 'gm')
    compute_segment_ltv(sub_cohorts, 'subscribers', 'overall', 'ALL', 'any', margin_by_uid, 'gm')
    compute_segment_ltv(ot_cohorts, 'onetime', 'overall', 'ALL', 'any', margin_by_uid, 'gm')

    # Category LTV by segment - REVENUE
    compute_category_segment_ltv(category_cohorts, 'all', revenue_by_uid, revenue_by_uid_by_cat, 'revenue')
    compute_category_segment_ltv(category_sub_cohorts, 'subscribers', revenue_by_uid, revenue_by_uid_by_cat, 'revenue')
    compute_category_segment_ltv(category_ot_cohorts, 'onetime', revenue_by_uid, revenue_by_uid_by_cat, 'revenue')

    # Category LTV by segment - GROSS MARGIN
    compute_category_segment_ltv(category_cohorts, 'all', margin_by_uid, margin_by_uid_by_cat, 'gm')
    compute_category_segment_ltv(category_sub_cohorts, 'subscribers', margin_by_uid, margin_by_uid_by_cat, 'gm')
    compute_category_segment_ltv(category_ot_cohorts, 'onetime', margin_by_uid, margin_by_uid_by_cat, 'gm')

    return retention_rows, ltv_rows


# =============================================================================
# CSV Writers
# =============================================================================

def write_retention_csv(rows: List[dict], filepath: str) -> int:
    fieldnames = ['cohort_month', 'dimension', 'first_value', 'm', 'metric', 'segment', 'cohort_size', 'retention']
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def write_ltv_csv(rows: List[dict], filepath: str) -> int:
    fieldnames = ['cohort_type', 'cohort_month', 'dimension', 'first_value',
                  'm', 'metric', 'measure', 'segment', 'cohort_size', 'ltv_per_user']
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
    print("Subscription-aware retention (ports churn.ts logic)")
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
    print(f"  Date range: {unique_months[0] if unique_months else '?'} -> {unique_months[-1] if unique_months else '?'}")

    # Category breakdown
    cat_counts: Dict[str, int] = defaultdict(int)
    for o in orders:
        for c in o.categories:
            cat_counts[c] += 1
    print(f"\n  Categories in orders:")
    for cat in sorted(cat_counts.keys()):
        print(f"    {cat:20s} {cat_counts[cat]:,}")

    print(f"\n2. COMPUTING COHORT METRICS (subscription-aware)")
    retention_rows, ltv_rows = compute_retention_and_ltv(orders)

    # Summaries
    for seg in ('all', 'subscribers', 'onetime'):
        seg_ret = [r for r in retention_rows if r['segment'] == seg and r['dimension'] == 'overall']
        seg_ltv = [r for r in ltv_rows if r['segment'] == seg and r['dimension'] == 'overall']
        print(f"\n  Segment '{seg}':")
        print(f"    Retention rows (overall): {len(seg_ret)}")
        print(f"    LTV rows (overall):       {len(seg_ltv)}")

        # Show M0/M1 for recent cohorts
        m0_rows = [r for r in seg_ret if r['m'] == 0]
        m1_rows = {r['cohort_month']: r for r in seg_ret if r['m'] == 1}
        if m0_rows:
            print(f"    Recent cohorts:")
            for r in m0_rows[-5:]:
                cm = r['cohort_month']
                m1 = m1_rows.get(cm)
                m1_str = m1['retention'] if m1 else '-'
                print(f"      {cm}: n={r['cohort_size']:3d}, M0={r['retention']}, M1={m1_str}")

    total_ret = len(retention_rows)
    total_ltv = len(ltv_rows)
    print(f"\n  Total retention rows: {total_ret}")
    print(f"  Total LTV rows:      {total_ltv}")

    if dry_run:
        print(f"\n3. DRY RUN — skipping file writes")
    else:
        print(f"\n3. WRITING CSV FILES")
        n_ret = write_retention_csv(retention_rows, RETENTION_CSV)
        print(f"  Wrote {n_ret} rows -> {RETENTION_CSV}")

        n_ltv = write_ltv_csv(ltv_rows, LTV_CSV)
        print(f"  Wrote {n_ltv} rows -> {LTV_CSV}")

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
    ltv_overall_all = [r for r in ltv_rows if r['dimension'] == 'overall' and r['segment'] == 'all']
    ltv_issues = 0
    for cm in sorted(set(r['cohort_month'] for r in ltv_overall_all)):
        cohort_rows = sorted(
            [r for r in ltv_overall_all if r['cohort_month'] == cm],
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

    # Check: POM HL subscriber M1 retention (Antoine's benchmark: ~79-82%)
    pom_hl_sub = [r for r in retention_rows
                  if r['dimension'] == 'category' and r['first_value'] == 'pom hl'
                  and r['segment'] == 'subscribers' and r['metric'] == 'same']
    pom_m1 = {r['cohort_month']: r for r in pom_hl_sub if r['m'] == 1}
    if pom_m1:
        print(f"\n  POM HL subscriber 'same' retention (M1) — target ~79-82%:")
        for cm in sorted(pom_m1.keys())[-6:]:
            r = pom_m1[cm]
            print(f"    {cm}: n={r['cohort_size']}, M1={r['retention']}")

    print("\n" + "=" * 60)
    if dry_run:
        print("DRY RUN COMPLETE — no files written")
    else:
        print("DONE — CSV files generated successfully")
    print("=" * 60)


if __name__ == '__main__':
    main()
