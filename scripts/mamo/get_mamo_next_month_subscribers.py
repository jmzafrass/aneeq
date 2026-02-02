import os
import sys
import csv
from datetime import datetime, date, timezone, timedelta
import requests
from typing import Optional, Tuple, List, Dict
from dotenv import load_dotenv
load_dotenv()


# Configuration
API_KEY = os.getenv("MAMO_API_KEY")
# Note: Subscriptions endpoints live under Manage API, not Business API.
# See: https://mamopay.readme.io/reference/get_subscriptions-subscriptionid-subscribers
BASE_URL = "https://business.mamopay.com/manage_api/v1"

HEADERS = {
    # Use application/json like in get_mamo.py
    "accept": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}


def get_json(url: str, params: Optional[Dict] = None, debug: bool = False) -> Dict:
    """GET a URL and return parsed JSON with clearer errors when the body isn't JSON."""
    resp = requests.get(url, headers=HEADERS, params=params or {})
    ct = resp.headers.get("content-type", "").lower()
    status = resp.status_code
    text_preview = (resp.text or "")[:500]
    if debug:
        print(f"DEBUG GET {url} status={status} ct={ct} len={len(resp.text or '')}")
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        msg = f"HTTP {status} from {url}. Body preview: {text_preview}"
        raise requests.HTTPError(msg) from e
    # Some gateways return 200 text/html (login page) when auth is missing/invalid
    if "json" not in ct:
        raise requests.HTTPError(
            f"Unexpected content-type '{ct}' from {url}. Body preview: {text_preview}.\n"
            f"Check that MAMO_API_KEY is a valid Business API token and headers are correct."
        )
    try:
        return resp.json()
    except Exception as e:
        raise requests.JSONDecodeError(
            f"Failed to parse JSON from {url}. Body preview: {text_preview}",
            doc=text_preview,
            pos=0,
        )


def month_bounds_for_next_month(today: Optional[date] = None) -> Tuple[datetime, datetime]:
    """Return [start, end) datetimes (UTC) of next calendar month from Dubai timezone perspective.

    This accounts for the fact that payments scheduled for late UTC times on the last day
    of the previous month actually occur on the first day of the target month in Dubai time.

    Dubai is UTC+4, so we subtract 4 hours to capture payments that fall into the target
    month when viewed from Dubai's perspective.
    """
    if today is None:
        today = date.today()

    year = today.year + (1 if today.month == 12 else 0)
    month = 1 if today.month == 12 else today.month + 1

    # Dubai timezone offset (UTC+4)
    dubai_offset = timedelta(hours=4)

    # Adjust for Dubai timezone perspective
    # Start 4 hours earlier to capture late previous day UTC = early target day Dubai
    start = datetime(year, month, 1, tzinfo=timezone.utc) - dubai_offset

    # Compute first day of the following month
    next_year = year + (1 if month == 12 else 0)
    next_month = 1 if month == 12 else month + 1
    end = datetime(next_year, next_month, 1, tzinfo=timezone.utc) - dubai_offset

    return start, end


def parse_dt(val: Optional[str]) -> Optional[datetime]:
    """Parse various datetime formats into aware UTC datetimes if possible."""
    if not val or not isinstance(val, str):
        return None

    fmts = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y-%m-%d-%H-%M-%S",  # observed in other Mamo payloads
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(val, fmt)
            # If no tzinfo, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def next_payment_datetime_from_subscriber(sub: Dict) -> Optional[datetime]:
    """Best-effort extraction of next payment datetime from a subscriber record.

    Tries common key variants used by APIs.
    """
    candidate_keys = [
        "next_payment_at",
        "next_payment_date",
        "next_billing_at",
        "next_charge_at",
        "nextPaymentAt",
        "nextPaymentDate",
        "nextBillingAt",
        "nextChargeAt",
    ]

    for key in candidate_keys:
        if key in sub:
            dt = parse_dt(sub.get(key))
            if dt:
                return dt

    # Try common nesting locations if present
    for parent in ("billing", "payment", "schedule", "subscription", "metadata"):
        nested = sub.get(parent)
        if isinstance(nested, dict):
            for key in candidate_keys:
                if key in nested:
                    dt = parse_dt(nested.get(key))
                    if dt:
                        return dt

    return None


def is_active_subscriber(sub: Dict) -> bool:
    """Heuristic to decide if a subscriber is active.

    Checks common boolean flags and status strings at top-level and nested objects.
    Defaults to False if no positive signal is found and no negative signal is detected.
    """
    # Explicit boolean flags
    for key in ("active", "is_active", "isActive", "enabled"):
        if key in sub and isinstance(sub[key], bool):
            return bool(sub[key])

    # Negative timestamp signals
    for key in ("cancelled_at", "canceled_at", "ended_at", "paused_at"):
        if sub.get(key):
            return False

    # Status strings
    status_keys = ("status", "state", "subscription_status", "lifecycle_status")
    for key in status_keys:
        val = sub.get(key)
        if isinstance(val, str):
            low = val.lower()
            if low in ("active", "on"):
                return True
            if low in ("canceled", "cancelled", "inactive", "paused", "disabled", "ended"):
                return False

    # Check common nesting
    for parent in ("subscription", "customer", "membership"):
        nested = sub.get(parent)
        if isinstance(nested, dict):
            for key in ("is_active", "isActive"):
                if key in nested and isinstance(nested[key], bool):
                    return bool(nested[key])
            for key in status_keys:
                val = nested.get(key)
                if isinstance(val, str):
                    low = val.lower()
                    if low == "active":
                        return True
                    if low in ("canceled", "cancelled", "inactive", "paused", "disabled", "ended"):
                        return False

    # No conclusive signal; be strict and exclude
    return False


def fetch_subscribers(subscription_id: str, per_page: int = 100, debug: bool = False) -> List[Dict]:
    """Fetch all subscribers for a given subscription, following pagination."""
    url = f"{BASE_URL}/subscriptions/{subscription_id}/subscribers"
    page = 1
    out: List[Dict] = []
    while True:
        payload = get_json(url, params={"page": page, "per_page": per_page}, debug=debug)

        # Handle both list and dict responses
        if isinstance(payload, list):
            # Direct list response (like Mamo's subscriber endpoint)
            batch = payload
        else:
            # Wrapped response with data field
            raw_batch = payload.get("data", [])
            # Flatten JSON:API style items: merge attributes into root for easier access
            batch = []
            for item in raw_batch:
                if isinstance(item, dict) and "attributes" in item:
                    flat = {"id": item.get("id"), "type": item.get("type")}
                    attrs = item.get("attributes") or {}
                    if isinstance(attrs, dict):
                        flat.update(attrs)
                    batch.append(flat)
                else:
                    batch.append(item)
        
        if not batch:
            break
        out.extend(batch)

        # For list responses, check if we got less than requested (indicates last page)
        if isinstance(payload, list):
            if len(batch) < per_page:
                break
            page += 1
        else:
            # For dict responses, check pagination metadata
            meta = payload.get("pagination_meta") or payload.get("meta") or {}
            total_pages = meta.get("total_pages") or meta.get("totalPages")
            links = payload.get("links") or {}
            has_next_link = bool(links.get("next"))
            if total_pages is not None:
                if page >= int(total_pages):
                    break
                page += 1
            elif has_next_link:
                page += 1
            else:
                # Fallback: stop when last page smaller than per_page
                if len(batch) < per_page:
                    break
                page += 1
    return out


def fetch_subscriptions(per_page: int = 100, debug: bool = False) -> List[Dict]:
    """Fetch all subscription identifiers from payment links.

    Since the /subscriptions endpoint is not available, we extract subscription
    identifiers from the /links endpoint instead (following the Airtable approach).

    Returns a list of dicts with 'id' field containing subscription identifiers (MPB-SUB-*).
    """
    url = f"{BASE_URL}/links"
    page = 1
    subscription_ids = set()

    if debug:
        print(f"DEBUG: Fetching subscription IDs from {url}")

    while True:
        payload = get_json(url, params={"page": page, "per_page": per_page}, debug=debug)
        raw_batch = payload.get("data", [])

        if not raw_batch:
            break

        # Extract subscription identifiers from payment links
        for item in raw_batch:
            if isinstance(item, dict):
                subscription = item.get("subscription")
                if subscription and isinstance(subscription, dict):
                    sub_id = subscription.get("identifier")
                    if sub_id:
                        subscription_ids.add(sub_id)

        # Handle pagination
        meta = payload.get("pagination_meta") or payload.get("meta") or {}
        total_pages = meta.get("total_pages") or meta.get("totalPages")
        links = payload.get("links") or {}
        has_next_link = bool(links.get("next"))

        if total_pages is not None:
            if page >= int(total_pages):
                break
            page += 1
        elif has_next_link:
            page += 1
        else:
            if len(raw_batch) < per_page:
                break
            page += 1

    # Return as list of dicts with 'id' field for compatibility
    return [{"id": sub_id} for sub_id in sorted(subscription_ids)]


def filter_active_subscribers(subscribers: List[Dict]) -> List[Dict]:
    """Filter subscribers to only include active ones, regardless of next payment date."""
    matched = []
    for sub in subscribers:
        if is_active_subscriber(sub):
            matched.append(sub)
    return matched


def export_csv(records: List[Dict], path: str) -> None:
    if not records:
        print("No records to export.")
        return
    # Collect columns from the union of keys (1-level flatten for common nested dicts)
    flat_records: List[Dict] = []
    all_cols: set = set()
    for rec in records:
        flat: Dict[str, str] = {}
        for k, v in rec.items():
            if isinstance(v, dict):
                for sk, sv in v.items():
                    flat[f"{k}_{sk}"] = sv
                    all_cols.add(f"{k}_{sk}")
            else:
                flat[k] = v
                all_cols.add(k)
        flat_records.append(flat)

    cols = sorted(all_cols)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(flat_records)
    print(f"Exported {len(records)} subscribers to {path}")


def main(argv: List[str]) -> int:
    if not API_KEY:
        print("Error: set MAMO_API_KEY environment variable.", file=sys.stderr)
        return 2

    args = argv[1:] or ["--all"]
    use_all = False
    subscription_id: Optional[str] = None
    csv_path = None
    debug = False
    include_all_status = False

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--all":
            use_all = True
            i += 1
        elif arg in {"--all-status", "--include-all-status"}:
            include_all_status = True
            i += 1
        elif arg == "--debug":
            debug = True
            i += 1
        elif arg == "--csv":
            if i + 1 >= len(args):
                print("--csv flag provided but no path given", file=sys.stderr)
                return 2
            csv_path = args[i + 1]
            i += 2
        elif subscription_id is None:
            subscription_id = arg
            i += 1
        else:
            print(f"Unrecognized argument '{arg}'", file=sys.stderr)
            return 2

    if not use_all and not subscription_id:
        use_all = True

    if use_all and subscription_id:
        print("Warning: both --all and a subscription id provided; defaulting to --all.")
        subscription_id = None

    combined_subscribers: List[Dict] = []
    if use_all:
        print(f"Fetching all subscriptions from {BASE_URL}...")
        subs_list = fetch_subscriptions(debug=debug)
        print(f"Found {len(subs_list)} subscriptions.")
        for s in subs_list:
            sid = s.get("id") or s.get("subscription_id")
            if not sid:
                continue
            sname = s.get("name") or s.get("title") or s.get("plan_name")
            print(f"- Fetching subscribers for {sid} ({sname or 'unnamed'})...")
            try:
                subs = fetch_subscribers(sid, debug=debug)
            except requests.HTTPError as e:
                print(f"  ! Error fetching subscribers for {sid}: {e}")
                continue
            # Attach subscription context to each record for traceability
            for rec in subs:
                rec.setdefault("subscription_id", sid)
                if sname:
                    rec.setdefault("subscription_name", sname)
            combined_subscribers.extend(subs)
        print(f"Fetched {len(combined_subscribers)} subscribers across all subscriptions.")
    else:
        print(f"Fetching subscribers for subscription {subscription_id}...")
        subs = fetch_subscribers(subscription_id)
        for rec in subs:
            rec.setdefault("subscription_id", subscription_id)
        combined_subscribers = subs
        print(f"Fetched {len(combined_subscribers)} subscribers total.")

    if include_all_status:
        matched = combined_subscribers
        print(f"Including all subscribers (active and inactive) — total: {len(matched)}")
    else:
        matched = filter_active_subscribers(combined_subscribers)
        print(f"Filtered to active subscribers only — matched {len(matched)} subscribers.")

    # Print a brief summary list (id/email/date if available)
    for sub in matched[:25]:  # keep output short
        dt = next_payment_datetime_from_subscriber(sub)
        ident = sub.get("id") or sub.get("subscriber_id") or sub.get("customer_id")
        email = (
            sub.get("email")
            or (sub.get("customer") or {}).get("email")
            or (sub.get("user") or {}).get("email")
        )
        print(f"- id={ident} email={email} next_payment={dt.isoformat() if dt else 'N/A'}")

    if csv_path:
        export_csv(matched, csv_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
