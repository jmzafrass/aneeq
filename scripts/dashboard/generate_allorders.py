#!/usr/bin/env python3
"""
Generate allorders.csv for the dashboard.

Reads the existing CSV, fixes name_uid using Airtable lookups,
and appends new orders from Nov 2025 onwards.

Usage:
    python3 scripts/dashboard/generate_allorders.py
    python3 scripts/dashboard/generate_allorders.py --dry-run
"""

import csv
import io
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json",
}

WC_BASE_URL = os.getenv("WC_BASE_URL")
WC_AUTH = HTTPBasicAuth(os.getenv("WC_CONSUMER_KEY"), os.getenv("WC_CONSUMER_SECRET"))

TABLES = {
    "orders": "tblWByCCtBE1dR6ox",
    "mamo": "tbl7WfjTqWMnsqpbs",
    "user": "tblMtIskMF3X3nKWC",
    "product": "tblsU18ZUEMiirxJl",
}

CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "dashboard", "public", "data", "allorders.csv"
)

CSV_COLUMNS = [
    "Order_id",
    "Type",
    "Status Order",
    "Order Date",
    "Price",
    "Category",
    "SKUs",
    "Customer",
    "Location",
    "Notes",
    "Status Customer",
    "name_uid",
]

# Cutoff: existing data ends at Oct 2025
NEW_ORDER_CUTOFF = "2025-10-31"


# =============================================================================
# Airtable fetch
# =============================================================================


def fetch_all_records(table_id, fields=None, filter_formula=None):
    """Fetch all records from an Airtable table with pagination."""
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
            print(f"  ERROR fetching {table_id}: {resp.status_code} {resp.text[:200]}")
            break

        data = resp.json()
        all_records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break

    return all_records


# =============================================================================
# Helpers
# =============================================================================


def normalize_name(name):
    """Normalize a customer name for matching."""
    if not name:
        return ""
    # Remove Arabic/special chars, lowercase, collapse whitespace
    n = re.sub(r"[^\w\s]", "", name.lower(), flags=re.UNICODE)
    return " ".join(n.split())


def clean_order_id(oid):
    """Extract the matchable part of an Order_id."""
    oid = oid.strip()
    # "Order 6219" → "6219"
    if oid.startswith("Order "):
        return oid[6:].strip()
    # "ordef 8096" → "8096"
    if oid.startswith("ordef "):
        return oid[6:].strip()
    return oid


def is_hex10(s):
    """Check if a string is a 10-char hex ID (Mamo without PAY- prefix)."""
    return len(s) == 10 and all(c in "0123456789ABCDEFabcdef" for c in s)


def is_old_uid(uid):
    """Check if a name_uid is the old sequential N00XXX format."""
    return bool(re.match(r"^N\d{3,}$", uid.strip()))


def levenshtein(s1, s2):
    """Compute Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def fuzzy_match(name, user_by_name, max_dist=3):
    """Find best fuzzy match for a name in the user map."""
    name_norm = normalize_name(name)
    if not name_norm:
        return None

    best_uid = None
    best_dist = max_dist + 1

    for uname, uid in user_by_name.items():
        # Quick length check to skip obviously different names
        if abs(len(uname) - len(name_norm)) > max_dist:
            continue
        d = levenshtein(name_norm, uname)
        if d < best_dist:
            best_dist = d
            best_uid = uid

    if best_dist <= max_dist:
        return best_uid

    # Substring containment: one name contains the other
    for uname, uid in user_by_name.items():
        if len(name_norm) >= 5 and len(uname) >= 5:
            if name_norm in uname or uname in name_norm:
                return uid

    return None


def parse_date_dd_mm_yyyy(s):
    """Parse dd/mm/yyyy to datetime."""
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y")
    except (ValueError, AttributeError):
        return None


def format_date_dd_mm_yyyy(dt):
    """Format datetime as dd/mm/yyyy."""
    return dt.strftime("%d/%m/%Y")


def parse_iso_to_ddmmyyyy(s):
    """Parse ISO 8601 date string to dd/mm/yyyy."""
    if not s:
        return ""
    # Strip timezone info for simpler parsing on Python 3.9
    s = s.strip().replace("Z", "").split("+")[0]
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return format_date_dd_mm_yyyy(dt)
        except ValueError:
            continue
    return ""


def derive_type(fields):
    """Derive the Type column for a new WC order."""
    created_via = (fields.get("created_via") or "").lower()
    categories = fields.get("Category (from Product) (from Last Update Items)") or []
    if isinstance(categories, str):
        categories = [categories]

    if created_via == "subscription":
        return "Sub Renewal"

    has_pom = any("POM" in c for c in categories)
    if has_pom:
        return "New Sub"
    return "One time"


def format_price(val):
    """Format price value preserving original CSV style."""
    if val is None:
        return ""
    try:
        f = float(val)
        # If integer, show without decimals
        if f == int(f):
            return str(int(f))
        return str(f)
    except (ValueError, TypeError):
        return str(val)


def format_notes_months(billing_cycle):
    """Convert billing_cycle to 'X months' format. Handles: 3, '3×month', '2 months', etc."""
    if not billing_cycle:
        return ""
    bc_str = str(billing_cycle).strip()
    if bc_str in ("—", "-", "", "None"):
        return ""
    # Try to extract number from formats like "3×month", "2×month", "1×month"
    m = re.match(r"(\d+)\s*[×x×]\s*month", bc_str, re.IGNORECASE)
    if m:
        months = int(m.group(1))
    else:
        try:
            months = int(float(bc_str))
        except (ValueError, TypeError):
            # Try "N months" or "N month" format
            m2 = re.match(r"(\d+)\s*month", bc_str, re.IGNORECASE)
            if m2:
                months = int(m2.group(1))
            else:
                return ""
    if months > 1:
        return f"{months} months"
    if months == 1:
        return "1"
    return ""


# =============================================================================
# Product catalogue & fallbacks
# =============================================================================


def fetch_product_catalogue():
    """Fetch Product table and build product_id → (category, product_name) map."""
    recs = fetch_all_records(
        TABLES["product"],
        fields=["ID", "Category", "product_name"],
    )
    catalogue = {}
    for rec in recs:
        f = rec.get("fields", {})
        pid = f.get("ID")
        if pid is not None:
            catalogue[str(pid)] = (
                f.get("Category", ""),
                f.get("product_name", ""),
            )
    return catalogue


def wc_api_get_order(order_id):
    """Fetch a single order from WooCommerce API."""
    try:
        resp = requests.get(
            f"{WC_BASE_URL}/orders/{order_id}",
            auth=WC_AUTH,
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None


def wc_api_get_customer(customer_id):
    """Fetch a WC customer profile by ID."""
    try:
        resp = requests.get(
            f"{WC_BASE_URL}/customers/{customer_id}",
            auth=WC_AUTH,
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None


def resolve_wc_product_from_api(order_id, product_catalogue):
    """Call WC API for an order, return (category, sku_name, customer, city)."""
    o = wc_api_get_order(order_id)
    if not o:
        return None, None, None, None

    categories = []
    sku_names = []
    for li in o.get("line_items", []):
        pid = str(li.get("product_id", ""))
        vid = str(li.get("variation_id", "0"))
        cat, pname = None, None

        # Try product_id first, then variation_id
        if pid in product_catalogue:
            cat, pname = product_catalogue[pid]
        elif vid != "0" and vid in product_catalogue:
            cat, pname = product_catalogue[vid]

        if cat:
            categories.append(cat)
        if pname:
            sku_names.append(pname)

        if not cat:
            # Fallback: infer category from line item name
            name = li.get("name", "")
            clean = name.split(" - ")[0].strip() if " - " in name else name
            inferred_cat = _infer_wc_category(clean)
            if inferred_cat:
                categories.append(inferred_cat)
            if clean:
                sku_names.append(clean)

    billing = o.get("billing", {})
    customer = f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip()
    city = billing.get("city", "")

    # Fallback: shipping name
    if not customer:
        shipping = o.get("shipping", {})
        customer = f"{shipping.get('first_name', '')} {shipping.get('last_name', '')}".strip()

    # Fallback: WC customer profile
    if not customer:
        cid = o.get("customer_id", 0)
        if cid:
            c = wc_api_get_customer(cid)
            if c:
                customer = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()

    return (
        ", ".join(dict.fromkeys(categories)) if categories else None,
        ", ".join(dict.fromkeys(sku_names)) if sku_names else None,
        customer or None,
        city or None,
    )


def _infer_wc_category(product_name):
    """Infer category from a WC product name when not found in catalogue."""
    if not product_name:
        return None
    name = product_name.lower()
    # POM HL
    if any(k in name for k in ["minoxidil", "finasteride", "dutasteride", "essential boost",
                                "power regrowth", "ultimate revival"]):
        if "sildenafil" in name or "tadalafil" in name or "dapoxetine" in name:
            return "POM SH"
        return "POM HL"
    # POM SH
    if any(k in name for k in ["sildenafil", "tadalafil", "dapoxetine",
                                "max power", "vital recharge"]):
        return "POM SH"
    # POM BG
    if "beard" in name:
        return "POM BG"
    # OTC
    if "delay" in name and "spray" in name:
        return "OTC SH"
    if "shampoo" in name or "conditioner" in name or "regrowth" in name:
        return "OTC HL"
    if any(k in name for k in ["cleanser", "moisturizer", "vitamin c", "eye cream", "skin care"]):
        return "OTC SK"
    # Catch-all for hair loss products (serum, rx, etc.)
    if any(k in name for k in ["hair loss", "hair", "serum", "rx"]):
        return "POM HL"
    return None


# Keyword → (Category, Product Name) for Mamo payment_name inference
MAMO_PRODUCT_KEYWORDS = [
    # POM HL products (order matters: more specific first)
    (["dutasteride", "minoxidil"], "POM HL", "Oral Dutasteride + Minoxidil"),
    (["finasteride", "minoxidil", "oral"], "POM HL", "Oral Finasteride + Minoxidil"),
    (["topical", "foam", "oral"], "POM HL", "Topical Minoxidil + Finasteride Foam"),
    (["topical", "finasteride", "minoxidil"], "POM HL", "Topical Minoxidil + Finasteride Foam"),
    (["0.25%", "finasteride"], "POM HL", "Topical Minoxidil + Finasteride Foam"),
    (["finasteride", "foam"], "POM HL", "Topical Minoxidil + Finasteride Foam"),
    (["ultimate", "revival"], "POM HL", "Ultimate Revival"),
    (["power", "regrowth"], "POM HL", "Power Regrowth"),
    (["essential", "boost"], "POM HL", "Essential Boost"),
    (["oral", "minoxidil"], "POM HL", "Oral Minoxidil"),
    (["minoxidil", "foam"], "POM HL", "Topical Minoxidil + Finasteride Foam"),
    # POM SH
    (["sildenafil", "tadalafil"], "POM SH", "oral Sildenafil + Tadalafil"),
    (["tadalafil"], "POM SH", "Oral Tadalafil"),
    (["sildenafil"], "POM SH", "Oral Sildenafil"),
    (["max", "power"], "POM SH", "Max Power"),
    (["vital", "recharge"], "POM SH", "Vital Recharge"),
    # POM BG
    (["beard"], "POM BG", "Beard growth serum"),
    # OTC
    (["delay", "spray"], "OTC SH", "Delay Spray"),
    (["shampoo"], "OTC HL", "Restore Shampoo"),
    (["regrowth", "pack"], "OTC HL", "Regrowth Hair Pack"),
    (["conditioner"], "OTC HL", "Revive Hair Conditioner"),
    (["skin", "care", "advance"], "OTC SK", "Advanced Skin Care Routine"),
    (["skin", "care"], "OTC SK", "Essential Skin Care Routine For Men"),
    (["cleanser"], "OTC SK", "Face Cleanser"),
    (["moisturizer"], "OTC SK", "Moisturizer with SPF 50"),
    (["vitamin", "c"], "OTC SK", "Vitamin C Serum"),
    (["eye", "cream"], "OTC SK", "Eye Cream"),
]


def infer_mamo_product(payment_name, amount=None):
    """Infer (category, product_name) from Mamo payment_name via keyword matching."""
    if not payment_name:
        return None, None
    text = payment_name.lower().strip()

    # Exact keyword matching
    for keywords, category, product_name in MAMO_PRODUCT_KEYWORDS:
        if all(kw in text for kw in keywords):
            return category, product_name

    # Generic "Aneeq" links or supplements — best-effort from amount
    if text in ("aneeq",):
        # These are ad-hoc Mamo payments without product info.
        # Default to POM HL as it's the most common product category.
        return "POM HL", ""

    # Price adjustments / discounts — still an order, assume POM HL
    if any(k in text for k in ("discount", "price difference", "duta")):
        return "POM HL", ""

    return None, None


# =============================================================================
# Main
# =============================================================================


def main():
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("GENERATE ALLORDERS.CSV")
    print("=" * 60)
    if dry_run:
        print("  ** DRY RUN — no files will be written **\n")

    # ------------------------------------------------------------------
    # 1. Read existing CSV
    # ------------------------------------------------------------------
    print("1. Reading existing allorders.csv ...")
    csv_path = os.path.abspath(CSV_PATH)
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        existing_rows = list(reader)
    print(f"   {len(existing_rows)} rows loaded")

    # Collect existing Order_ids for dedup later
    existing_oids = set()
    for r in existing_rows:
        oid = clean_order_id(r["Order_id"])
        if oid:
            existing_oids.add(oid)
            # Also add the raw form
            existing_oids.add(r["Order_id"].strip())

    # ------------------------------------------------------------------
    # 2. Fetch all Airtable data
    # ------------------------------------------------------------------
    print("\n2. Fetching Airtable data ...")

    print("   Fetching woocommerce_orders ...")
    wc_records = fetch_all_records(
        TABLES["orders"],
        fields=[
            "id", "customer_id", "status", "date_created",
            "total", "Category (from Product) (from Last Update Items)",
            "Product Name",
            "First Name (Billing)", "Last Name (Billing)",
            "City (Billing)", "created_via",
        ],
    )
    print(f"   → {len(wc_records)} WC orders")

    print("   Fetching Mamo Transactions ...")
    mamo_records = fetch_all_records(
        TABLES["mamo"],
        fields=[
            "id", "status", "amount", "created_date",
            "User", "Order_id",
            "customer_details_name", "customer_details_email",
            "Product Category", "Product Display Name",
            "Type", "billing_cycle", "subscription_frequency_interval",
            "payment_name", "external_id",
        ],
    )
    print(f"   → {len(mamo_records)} Mamo transactions")

    print("   Fetching Users ...")
    user_records = fetch_all_records(
        TABLES["user"],
        fields=[
            "source_user_id", "first_name", "last_name",
            "is_customer_antoine",
        ],
    )
    print(f"   → {len(user_records)} Users")

    print("   Fetching Product catalogue ...")
    product_catalogue = fetch_product_catalogue()
    print(f"   → {len(product_catalogue)} products")

    # ------------------------------------------------------------------
    # 3. Build lookup maps
    # ------------------------------------------------------------------
    print("\n3. Building lookup maps ...")

    # WC order id → customer_id (which equals source_user_id for WC customers)
    wc_map = {}
    wc_by_id = {}
    for rec in wc_records:
        f = rec.get("fields", {})
        oid = str(f.get("id", "")).strip()
        cid = str(f.get("customer_id", "")).strip()
        if oid and cid and cid != "0":
            wc_map[oid] = cid
        if oid:
            wc_by_id[oid] = f

    # User record_id → source_user_id
    user_by_recid = {}
    user_by_name = {}
    for rec in user_records:
        f = rec.get("fields", {})
        uid = str(f.get("source_user_id", "")).strip()
        if uid:
            user_by_recid[rec["id"]] = uid
            # Name map for fallback matching
            first = f.get("first_name") or ""
            last = f.get("last_name") or ""
            name = normalize_name(f"{first} {last}")
            if name and name not in user_by_name:
                user_by_name[name] = uid

    # Mamo id → User record_id (ONLY via User link, NOT via Order_id)
    mamo_to_user_recid = {}
    mamo_by_id = {}
    for rec in mamo_records:
        f = rec.get("fields", {})
        mid = str(f.get("id", "")).strip()
        if not mid:
            continue
        mamo_by_id[mid] = f
        user_link = f.get("User")
        if user_link and isinstance(user_link, list) and len(user_link) > 0:
            mamo_to_user_recid[mid] = user_link[0]
            # Also map hex without PAY- prefix
            if mid.startswith("PAY-"):
                mamo_to_user_recid[mid[4:]] = user_link[0]

    # WC Airtable record_id → WC order id (to resolve Mamo Order_id links)
    wc_recid_to_oid = {}
    for rec in wc_records:
        f = rec.get("fields", {})
        oid = str(f.get("id", "")).strip()
        if oid:
            wc_recid_to_oid[rec["id"]] = oid

    print(f"   WC map: {len(wc_map)} order→customer_id entries")
    print(f"   WC recid→oid: {len(wc_recid_to_oid)} entries")
    print(f"   Mamo→User: {len(mamo_to_user_recid)} entries")
    print(f"   User by name: {len(user_by_name)} entries")
    print(f"   User by recid: {len(user_by_recid)} entries")

    # ------------------------------------------------------------------
    # 4. Step 1: Fix name_uid via Order_id → Airtable lookup
    # ------------------------------------------------------------------
    print("\n4. Step 1: Fixing name_uid via Airtable Order_id lookup ...")

    name_to_uid = {}  # verified name → uid mapping built from matched rows
    step1_wc = 0
    step1_mamo = 0
    step1_unmatched = 0

    for row in existing_rows:
        oid = clean_order_id(row["Order_id"])
        cust_name = normalize_name(row.get("Customer", ""))

        # Try WC match first
        if oid in wc_map:
            row["name_uid"] = wc_map[oid]
            if cust_name:
                name_to_uid[cust_name] = wc_map[oid]
            step1_wc += 1
            continue

        # Try Mamo match (by id field, including hex without PAY- prefix)
        user_recid = mamo_to_user_recid.get(oid)
        if user_recid and user_recid in user_by_recid:
            uid = user_by_recid[user_recid]
            row["name_uid"] = uid
            if cust_name:
                name_to_uid[cust_name] = uid
            step1_mamo += 1
            continue

        step1_unmatched += 1

    print(f"   WC matched: {step1_wc}")
    print(f"   Mamo matched: {step1_mamo}")
    print(f"   Unmatched: {step1_unmatched}")

    # ------------------------------------------------------------------
    # 5. Step 2 Tier A: Propagate verified IDs to unmatched rows
    # ------------------------------------------------------------------
    print("\n5. Step 2 Tier A: Propagating verified name→uid ...")
    tier_a = 0
    for row in existing_rows:
        if is_old_uid(row["name_uid"]):
            cust_name = normalize_name(row.get("Customer", ""))
            if cust_name in name_to_uid:
                row["name_uid"] = name_to_uid[cust_name]
                tier_a += 1
    print(f"   Propagated: {tier_a}")

    # ------------------------------------------------------------------
    # 6. Step 2 Tier B: Exact match in User table by name
    # ------------------------------------------------------------------
    print("\n6. Step 2 Tier B: Exact name match in User table ...")
    tier_b = 0
    for row in existing_rows:
        if is_old_uid(row["name_uid"]):
            cust_name = normalize_name(row.get("Customer", ""))
            if cust_name in user_by_name:
                uid = user_by_name[cust_name]
                row["name_uid"] = uid
                name_to_uid[cust_name] = uid
                tier_b += 1
    print(f"   Matched: {tier_b}")

    # ------------------------------------------------------------------
    # 7. Step 2 Tier C: Fuzzy match
    # ------------------------------------------------------------------
    print("\n7. Step 2 Tier C: Fuzzy matching ...")
    tier_c = 0
    unknown_counter = 0
    unknown_name_map = {}  # normalized name → unknown_N (for consistency)
    still_unmatched = []
    for row in existing_rows:
        if is_old_uid(row["name_uid"]):
            cust_name = row.get("Customer", "").strip()
            cust_norm = normalize_name(cust_name)
            best = fuzzy_match(cust_name, user_by_name, max_dist=3)
            if best:
                row["name_uid"] = best
                name_to_uid[cust_norm] = best
                tier_c += 1
            elif cust_norm in unknown_name_map:
                # Same name already assigned an unknown ID
                row["name_uid"] = unknown_name_map[cust_norm]
            else:
                unknown_counter += 1
                uid = f"unknown_{unknown_counter}"
                row["name_uid"] = uid
                unknown_name_map[cust_norm] = uid
                name_to_uid[cust_norm] = uid
                still_unmatched.append(f"  {cust_name} → {uid}")
    print(f"   Fuzzy matched: {tier_c}")
    print(f"   Truly unknown: {unknown_counter} (unique names)")
    if still_unmatched:
        print("   Unmatched names:")
        for s in still_unmatched:
            print(f"   {s}")

    # ------------------------------------------------------------------
    # 8. Consistency: propagate any newly discovered UIDs
    # ------------------------------------------------------------------
    print("\n8. Consistency pass ...")
    consistency_fixes = 0
    for row in existing_rows:
        if row["name_uid"].startswith("unknown_"):
            cust_name = normalize_name(row.get("Customer", ""))
            if cust_name in name_to_uid:
                row["name_uid"] = name_to_uid[cust_name]
                consistency_fixes += 1
    print(f"   Fixed: {consistency_fixes}")

    # ------------------------------------------------------------------
    # 8b. Fix empty Notes (billing cycle) on existing rows
    # ------------------------------------------------------------------
    print("\n8b. Fixing empty Notes (billing cycle) ...")
    notes_fixed_wc = 0
    notes_fixed_mamo = 0
    for row in existing_rows:
        if row.get("Notes", "").strip():
            continue  # Already has Notes
        oid = clean_order_id(row["Order_id"])

        # WC subscription renewals: default 1 month
        if oid.isdigit():
            row_type = (row.get("Type") or "").strip()
            if row_type == "Sub Renewal":
                row["Notes"] = "1"
                notes_fixed_wc += 1
                continue

        # Mamo orders: look up billing_cycle, then subscription_frequency_interval
        mf = mamo_by_id.get(oid)
        if not mf and oid.startswith("PAY-"):
            mf = mamo_by_id.get(oid[4:])
        if mf:
            # Try billing_cycle first
            bc = mf.get("billing_cycle")
            notes_val = format_notes_months(bc)
            # Fallback: subscription_frequency_interval (integer months)
            if not notes_val:
                sfi = mf.get("subscription_frequency_interval")
                notes_val = format_notes_months(sfi)
            if notes_val:
                row["Notes"] = notes_val
                notes_fixed_mamo += 1

    print(f"   WC Sub Renewal → '1': {notes_fixed_wc}")
    print(f"   Mamo billing_cycle:   {notes_fixed_mamo}")

    # ------------------------------------------------------------------
    # 9. Fetch new orders (Nov 2025+)
    # ------------------------------------------------------------------
    print("\n9. Fetching new orders (Nov 2025 → present) ...")

    # New WC orders: processing/completed, after Oct 2025
    new_wc_filter = (
        "AND("
        "OR({status}='processing',{status}='completed'),"
        "IS_AFTER({date_created},'2025-10-31')"
        ")"
    )
    new_wc_records = fetch_all_records(
        TABLES["orders"],
        fields=[
            "id", "customer_id", "status", "date_created",
            "total", "Category (from Product) (from Last Update Items)",
            "Product Name",
            "First Name (Billing)", "Last Name (Billing)",
            "City (Billing)", "created_via",
        ],
        filter_formula=new_wc_filter,
    )
    print(f"   New WC orders fetched: {len(new_wc_records)}")

    # ALL captured Mamo after Oct 2025 (source of truth from Nov onwards)
    new_mamo_filter = (
        "AND("
        "{status}='captured',"
        "IS_AFTER({created_date},'2025-10-31')"
        ")"
    )
    new_mamo_records = fetch_all_records(
        TABLES["mamo"],
        fields=[
            "id", "status", "amount", "created_date",
            "User", "Order_id",
            "customer_details_name", "customer_details_email",
            "Product Category", "Product Display Name",
            "Type", "billing_cycle", "subscription_frequency_interval",
            "payment_name",
        ],
        filter_formula=new_mamo_filter,
    )
    print(f"   New Mamo fetched: {len(new_mamo_records)} (all captured, source of truth)")

    # Build new rows
    new_rows = []
    skipped_existing = 0

    # Process new WC orders
    for rec in new_wc_records:
        f = rec.get("fields", {})
        oid = str(f.get("id", "")).strip()
        if not oid:
            continue
        if oid in existing_oids:
            skipped_existing += 1
            continue

        # Parse date
        date_str = parse_iso_to_ddmmyyyy(f.get("date_created", ""))

        # Category
        cats = f.get("Category (from Product) (from Last Update Items)") or []
        if isinstance(cats, list):
            category = ", ".join(str(c) for c in cats)
        else:
            category = str(cats)

        # SKUs
        products = f.get("Product Name") or []
        if isinstance(products, list):
            skus = ", ".join(str(p) for p in products)
        else:
            skus = str(products)

        # Customer name
        first = (f.get("First Name (Billing)") or "").strip()
        last = (f.get("Last Name (Billing)") or "").strip()
        customer = f"{first} {last}".strip()

        # Location
        location = (f.get("City (Billing)") or "").strip()

        # name_uid
        cid = str(f.get("customer_id", "")).strip()
        if cid and cid != "0":
            uid = cid
        else:
            uid = ""

        # Notes: WC subscription renewals are monthly billing cycles
        order_type = derive_type(f)
        notes = "1" if order_type == "Sub Renewal" else ""

        new_rows.append({
            "Order_id": oid,
            "Type": order_type,
            "Status Order": "Delivered",
            "Order Date": date_str,
            "Price": format_price(f.get("total")),
            "Category": category,
            "SKUs": skus,
            "Customer": customer,
            "Location": location,
            "Notes": notes,
            "Status Customer": "",
            "name_uid": uid,
        })
        existing_oids.add(oid)

    # Process ALL captured Mamo (source of truth from Nov onwards)
    # Skip only if the Mamo ID or its linked WC order ID is already in the CSV
    mamo_added = 0
    mamo_covered_by_wc = 0
    for rec in new_mamo_records:
        f = rec.get("fields", {})
        mid = str(f.get("id", "")).strip()
        if not mid:
            continue

        # Check if Mamo ID already in CSV
        if mid in existing_oids:
            skipped_existing += 1
            continue
        hex_id = mid[4:] if mid.startswith("PAY-") else mid
        if hex_id in existing_oids:
            skipped_existing += 1
            continue

        # Check if linked WC order is already in CSV (covered by WC fetch)
        order_links = f.get("Order_id") or []
        if isinstance(order_links, list) and len(order_links) > 0:
            wc_covered = False
            for recid in order_links:
                wc_oid = wc_recid_to_oid.get(recid, "")
                if wc_oid and wc_oid in existing_oids:
                    wc_covered = True
                    break
            if wc_covered:
                mamo_covered_by_wc += 1
                continue

        # This Mamo transaction is NOT yet in CSV — add it
        # Parse date (use Mamo created_date = actual payment date)
        date_str = parse_iso_to_ddmmyyyy(f.get("created_date", ""))

        # Customer name
        customer = (f.get("customer_details_name") or "").strip()

        # Category (lookup field returns a list)
        cats = f.get("Product Category") or []
        if isinstance(cats, list):
            category = ", ".join(str(c) for c in cats)
        else:
            category = str(cats).strip()

        # SKUs (lookup field returns a list)
        sku_list = f.get("Product Display Name") or []
        if isinstance(sku_list, list):
            skus = ", ".join(str(s) for s in sku_list)
        else:
            skus = str(sku_list).strip()

        # Type
        type_val = (f.get("Type") or "").strip()

        # Notes from billing_cycle → subscription_frequency_interval fallback
        notes = format_notes_months(f.get("billing_cycle"))
        if not notes:
            notes = format_notes_months(f.get("subscription_frequency_interval"))

        # name_uid via User link
        uid = ""
        user_link = f.get("User")
        if user_link and isinstance(user_link, list) and len(user_link) > 0:
            uid = user_by_recid.get(user_link[0], "")

        new_rows.append({
            "Order_id": mid,
            "Type": type_val,
            "Status Order": "Delivered",
            "Order Date": date_str,
            "Price": format_price(f.get("amount")),
            "Category": category,
            "SKUs": skus,
            "Customer": customer,
            "Location": "",
            "Notes": notes,
            "Status Customer": "",
            "name_uid": uid,
        })
        existing_oids.add(mid)
        mamo_added += 1

    print(f"   Mamo: {mamo_added} added, {mamo_covered_by_wc} covered by WC orders")

    print(f"   New rows to append: {len(new_rows)}")
    print(f"   Skipped (already in CSV): {skipped_existing}")

    # ------------------------------------------------------------------
    # 9b. Resolve empty UIDs on new rows via name matching
    # ------------------------------------------------------------------
    print("\n9b. Resolving empty UIDs on new rows ...")
    new_resolved_name = 0
    new_resolved_user = 0
    new_resolved_fuzzy = 0
    new_still_empty = 0
    new_empty_names = []
    for row in new_rows:
        if row["name_uid"]:
            continue
        cust_name = normalize_name(row.get("Customer", ""))
        if cust_name in name_to_uid:
            row["name_uid"] = name_to_uid[cust_name]
            new_resolved_name += 1
        elif cust_name in user_by_name:
            row["name_uid"] = user_by_name[cust_name]
            new_resolved_user += 1
        else:
            # Try fuzzy match
            best = fuzzy_match(row.get("Customer", ""), user_by_name, max_dist=3)
            if best:
                row["name_uid"] = best
                name_to_uid[cust_name] = best
                new_resolved_fuzzy += 1
            elif cust_name in unknown_name_map:
                row["name_uid"] = unknown_name_map[cust_name]
            else:
                unknown_counter += 1
                uid = f"unknown_{unknown_counter}"
                row["name_uid"] = uid
                unknown_name_map[cust_name] = uid
                new_still_empty += 1
                new_empty_names.append(f"  {row.get('Customer', '')} → {uid}")
    print(f"   Via name propagation: {new_resolved_name}")
    print(f"   Via User table name:  {new_resolved_user}")
    print(f"   Via fuzzy match:      {new_resolved_fuzzy}")
    print(f"   Assigned unknown_N:   {new_still_empty}")
    if new_empty_names:
        print("   Unmatched new order names:")
        for s in new_empty_names:
            print(f"   {s}")

    # ------------------------------------------------------------------
    # 9c. Fix missing Category/SKUs/Customer across ALL rows
    # ------------------------------------------------------------------
    all_rows_combined = existing_rows + new_rows
    print("\n9c. Fixing missing products across all rows ...")

    # Collect ALL rows needing product fix
    wc_missing = []
    mamo_missing = []
    for row in all_rows_combined:
        if row["Category"].strip():
            continue
        oid = clean_order_id(row["Order_id"])
        if oid.isdigit():
            wc_missing.append(row)
        elif oid.startswith("PAY-") or is_hex10(oid):
            mamo_missing.append(row)

    # Also check ALL rows with Category but empty SKUs (WC only)
    wc_missing_sku = [
        r for r in all_rows_combined
        if r["Category"].strip() and not r["SKUs"].strip() and clean_order_id(r["Order_id"]).isdigit()
    ]

    # Collect ALL rows with empty Customer
    wc_missing_name = [
        r for r in all_rows_combined
        if not r["Customer"].strip()
    ]

    print(f"   WC orders missing Category:  {len(wc_missing)}")
    print(f"   WC orders missing SKUs only: {len(wc_missing_sku)}")
    print(f"   Mamo missing Category:       {len(mamo_missing)}")
    print(f"   WC orders missing Customer:  {len(wc_missing_name)}")

    # Fix WC via API (batch with rate limiting)
    wc_fixed_cat = 0
    wc_fixed_sku = 0
    wc_fixed_name = 0
    # Merge all WC rows needing API calls, dedup by Order_id
    wc_to_fix_map = {}
    for row in wc_missing + wc_missing_sku + wc_missing_name:
        oid = clean_order_id(row["Order_id"])
        if oid not in wc_to_fix_map:
            wc_to_fix_map[oid] = []
        wc_to_fix_map[oid].append(row)

    if wc_to_fix_map:
        print(f"   Calling WC API for {len(wc_to_fix_map)} unique orders ...")
        for i, (oid, rows_for_oid) in enumerate(wc_to_fix_map.items()):
            cat, sku, customer, city = resolve_wc_product_from_api(oid, product_catalogue)
            for row in rows_for_oid:
                if cat and not row["Category"].strip():
                    row["Category"] = cat
                    wc_fixed_cat += 1
                if sku and not row["SKUs"].strip():
                    row["SKUs"] = sku
                    wc_fixed_sku += 1
                if customer and not row["Customer"].strip():
                    row["Customer"] = customer
                    wc_fixed_name += 1
                if city and not row["Location"].strip():
                    row["Location"] = city
            # Rate limit: WC API allows ~10 req/sec
            if (i + 1) % 10 == 0:
                time.sleep(1)
        print(f"   WC API: fixed {wc_fixed_cat} categories, {wc_fixed_sku} SKUs, {wc_fixed_name} names")

    # Fix Mamo via external_id (WC API) then payment_name inference
    mamo_fixed = 0
    mamo_fixed_wc = 0
    for row in mamo_missing:
        oid = clean_order_id(row["Order_id"])
        mamo_fields = mamo_by_id.get(oid, {})
        if not mamo_fields and oid.startswith("PAY-"):
            mamo_fields = mamo_by_id.get(oid[4:], {})

        # Try 1: external_id → WC API
        ext_id = mamo_fields.get("external_id", "")
        if ext_id and ext_id.strip().isdigit():
            cat, sku, _, _ = resolve_wc_product_from_api(ext_id.strip(), product_catalogue)
            if cat:
                row["Category"] = cat
                mamo_fixed += 1
                mamo_fixed_wc += 1
            if sku and not row["SKUs"].strip():
                row["SKUs"] = sku
            if cat:
                continue

        # Try 2: payment_name keyword inference
        pname = mamo_fields.get("payment_name", "")
        amt = mamo_fields.get("amount")
        cat, sku = infer_mamo_product(pname, amount=amt)
        if cat:
            row["Category"] = cat
            mamo_fixed += 1
        if sku and not row["SKUs"].strip():
            row["SKUs"] = sku
        if not cat and pname:
            print(f"   WARNING: Could not infer product from: \"{pname}\" ({oid})")
    print(f"   Mamo: fixed {mamo_fixed}/{len(mamo_missing)} ({mamo_fixed_wc} via WC API)")

    # Final pass: fix remaining empty Customer names via Airtable User table
    uid_to_name = {}
    for rec in user_records:
        f = rec.get("fields", {})
        uid = str(f.get("source_user_id", "")).strip()
        first = (f.get("first_name") or "").strip()
        last = (f.get("last_name") or "").strip()
        name = f"{first} {last}".strip()
        if uid and name:
            uid_to_name[uid] = name

    name_from_user = 0
    still_empty_names = []
    for row in all_rows_combined:
        if not row["Customer"].strip() and row["name_uid"]:
            uid = row["name_uid"]
            if uid in uid_to_name:
                row["Customer"] = uid_to_name[uid]
                name_from_user += 1
            else:
                still_empty_names.append(f"  {row['Order_id']} uid={uid}")
    if name_from_user or still_empty_names:
        print(f"   Customer names from User table: {name_from_user}")
    if still_empty_names:
        print(f"   Still empty Customer ({len(still_empty_names)}):")
        for s in still_empty_names:
            print(f"   {s}")

    # ------------------------------------------------------------------
    # 10. Sort and write
    # ------------------------------------------------------------------
    all_rows = all_rows_combined

    # Sort by Order Date
    def sort_key(row):
        dt = parse_date_dd_mm_yyyy(row.get("Order Date", ""))
        return dt or datetime.min

    all_rows.sort(key=sort_key)

    # Summary
    uid_counts = defaultdict(int)
    for r in all_rows:
        uid = r["name_uid"]
        if is_old_uid(uid):
            uid_counts["N00XXX (unfixed)"] += 1
        elif uid.startswith("unknown_"):
            uid_counts["unknown_NNN"] += 1
        elif uid == "":
            uid_counts["empty"] += 1
        else:
            uid_counts["resolved"] += 1

    dates = [parse_date_dd_mm_yyyy(r["Order Date"]) for r in all_rows if parse_date_dd_mm_yyyy(r["Order Date"])]
    min_date = min(dates) if dates else None
    max_date = max(dates) if dates else None

    # Product gap count
    empty_cat_count = sum(1 for r in all_rows if not r["Category"].strip())
    empty_sku_count = sum(1 for r in all_rows if not r["SKUs"].strip())
    empty_cust_count = sum(1 for r in all_rows if not r["Customer"].strip())

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total rows:        {len(all_rows)}")
    print(f"  Existing (fixed):  {len(existing_rows)}")
    print(f"  New appended:      {len(new_rows)}")
    print(f"  Date range:        {format_date_dd_mm_yyyy(min_date) if min_date else '?'} → {format_date_dd_mm_yyyy(max_date) if max_date else '?'}")
    print()
    print("  name_uid breakdown:")
    for k, v in sorted(uid_counts.items()):
        print(f"    {k:25} {v}")
    print()
    print(f"  Step 1 — WC Order_id:      {step1_wc}")
    print(f"  Step 1 — Mamo→User:        {step1_mamo}")
    print(f"  Step 2A — Name propagated:  {tier_a}")
    print(f"  Step 2B — Exact name match: {tier_b}")
    print(f"  Step 2C — Fuzzy match:      {tier_c}")
    print(f"  Consistency fixes:          {consistency_fixes}")
    print(f"  Truly unknown:              {unknown_counter}")
    print()
    print("  Product gaps remaining:")
    print(f"    Empty Category:  {empty_cat_count}")
    print(f"    Empty SKUs:      {empty_sku_count}")
    print(f"    Empty Customer:  {empty_cust_count}")
    print("=" * 60)

    if dry_run:
        print("\n  ** DRY RUN — no files written **")
        return

    # Write CSV
    print(f"\nWriting {csv_path} ...")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print(f"Done. {len(all_rows)} rows written.")


if __name__ == "__main__":
    main()
