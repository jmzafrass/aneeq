import argparse
import csv
import json
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

# --- Shared Config ----------------------------------------------------------
DEFAULT_EMAIL = "jmzafras@gmail.com"

# ⬇️  NEW production cookie: only the PHPSESSID value they gave you
DEFAULT_COOKIES = "PHPSESSID=dc8e8b14f9e2d2b580e33765e34eb92c"

HEADERS = {
    # ⬇️  NEW production APPID
    "APPID": "APPANEE0XZ",
    "Content-Type": "application/json",
    "Cookie": DEFAULT_COOKIES,
}


# Utility to save and pretty-print JSON
def save_and_print_json(data, filename):
    Path(filename).write_text(json.dumps(data, indent=4))
    print(f"\n🗂️  Full JSON response saved to {filename}:\n")
    print(json.dumps(data, indent=4))


def extract_buyer_persona(profile: dict) -> dict:
    """Trim profile down to buyer-persona friendly fields."""
    patient = profile.get("PatientProfile", {}) or {}
    location = profile.get("PatientProfileLocation", {}) or {}
    user = profile.get("User", {}) or {}
    return {
        "email": user.get("email"),
        "full_name": patient.get("display_name") or f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip(),
        "gender": patient.get("gender"),
        "age": patient.get("age"),
        "dob": patient.get("dob"),
        "phone": location.get("phone1"),
        "city": location.get("city_name"),
        "country": location.get("country_name"),
        "patient_id": patient.get("id"),
        "eid": patient.get("ssno"),
        "mrn": patient.get("mrno"),
        "currency_prefix": (profile.get("Currency") or {}).get("prefix"),
    }


def rate_limited_post(session: requests.Session, url: str, headers: dict, payload: dict, *, last_call_ts: float, max_per_minute: int) -> Tuple[requests.Response, float]:
    """POST with simple client-side rate limiting to avoid hammering the API."""
    min_interval = 60.0 / max_per_minute
    now = time.time()
    wait_for = min_interval - (now - last_call_ts)
    if wait_for > 0:
        time.sleep(wait_for)
    resp = session.post(url, headers=headers, json=payload, timeout=60)
    return resp, time.time()


def fetch_profile(email: str, headers: dict, session: requests.Session, last_call_ts: float, max_per_minute: int) -> Tuple[Optional[dict], float, Optional[str]]:
    profile_url = "https://prod-saas-api.instapract.ae/web/api/patient/pat-view"
    resp, ts = rate_limited_post(session, profile_url, headers, {"email": email}, last_call_ts=last_call_ts, max_per_minute=max_per_minute)
    try:
        body = resp.json()
    except requests.JSONDecodeError:
        return None, ts, f"Non-JSON response (status {resp.status_code})"
    if resp.status_code == 200 and body.get("success"):
        return body.get("data", {}), ts, None
    return None, ts, f"HTTP {resp.status_code}: {body}"


def persona_row(persona: Optional[dict], error: Optional[str]) -> Dict[str, str]:
    """Return a flat dict of persona fields ready to merge into a CSV row."""
    fields = {
        "persona_full_name": "",
        "persona_email": "",
        "persona_gender": "",
        "persona_age": "",
        "persona_dob": "",
        "persona_phone": "",
        "persona_city": "",
        "persona_country": "",
        "persona_patient_id": "",
        "persona_eid": "",
        "persona_mrn": "",
        "persona_currency_prefix": "",
        "persona_error": "",
    }
    if persona:
        fields.update(
            {
                "persona_full_name": persona.get("full_name", ""),
                "persona_email": persona.get("email", ""),
                "persona_gender": persona.get("gender", ""),
                "persona_age": persona.get("age", ""),
                "persona_dob": persona.get("dob", ""),
                "persona_phone": persona.get("phone", ""),
                "persona_city": persona.get("city", ""),
                "persona_country": persona.get("country", ""),
                "persona_patient_id": persona.get("patient_id", ""),
                "persona_eid": persona.get("eid", ""),
                "persona_mrn": persona.get("mrn", ""),
                "persona_currency_prefix": persona.get("currency_prefix", ""),
            }
        )
    if error:
        fields["persona_error"] = error
    return fields


def enrich_csv(args: argparse.Namespace, headers: dict) -> None:
    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv) if args.output_csv else input_path.with_name(f"{input_path.stem}_enriched.csv")

    if not input_path.is_file():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    rows = list(csv.DictReader(input_path.open(newline="", encoding="utf-8")))
    if not rows:
        print("Input CSV is empty; nothing to do.")
        return
    if "Email" not in rows[0]:
        raise KeyError("Input CSV must contain an 'Email' column")

    persona_cols = [
        "persona_full_name",
        "persona_email",
        "persona_gender",
        "persona_age",
        "persona_dob",
        "persona_phone",
        "persona_city",
        "persona_country",
        "persona_patient_id",
        "persona_eid",
        "persona_mrn",
        "persona_currency_prefix",
        "persona_error",
    ]

    cache: Dict[str, Tuple[Optional[dict], Optional[str]]] = {}
    last_ts = 0.0

    print(f"Enriching {len(rows)} rows from {input_path} with persona fields (throttle: {args.max_per_minute} req/min)")
    with requests.Session() as session:
        for idx, row in enumerate(rows, 1):
            raw_email = row.get("Email", "") or ""
            email = raw_email.strip()
            if not email:
                cache[email] = (None, "missing email")
                continue
            if email not in cache:
                profile, last_ts, error = fetch_profile(email, headers, session, last_ts, args.max_per_minute)
                persona = extract_buyer_persona(profile) if profile else None
                cache[email] = (persona, error)
                if idx % 10 == 0:
                    print(f"  Processed {idx}/{len(rows)}…")

    fieldnames = list(rows[0].keys()) + persona_cols
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            email = (row.get("Email", "") or "").strip()
            persona, error = cache.get(email, (None, "not fetched"))
            merged = {**row, **persona_row(persona, error)}
            writer.writerow(merged)

    print(f"✅ Enriched CSV written to {output_path} ({len(rows)} rows)")

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Instapract patient profile and buyer-persona friendly summary")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Patient email to query")
    parser.add_argument("--cookie", default=DEFAULT_COOKIES, help="Cookie header value (e.g., PHPSESSID=...)")
    parser.add_argument("--save-json", action="store_true", help="Save full profile JSON")
    parser.add_argument("--input-csv", help="Path to input CSV with an Email column")
    parser.add_argument("--output-csv", help="Where to write the enriched CSV (defaults to input path with _enriched)")
    parser.add_argument("--max-per-minute", type=int, default=90, help="Throttle API calls to avoid rate limits")
    args = parser.parse_args()

    headers = {**HEADERS, "Cookie": args.cookie}

    if args.input_csv:
        enrich_csv(args, headers)
        return

    # --- Single email interactive mode -----------------------------------------
    with requests.Session() as session:
        profile, _, error = fetch_profile(args.email, headers, session, last_call_ts=0.0, max_per_minute=args.max_per_minute)

    print("\n===========================")
    print("🔍 PATIENT PROFILE")
    print("===========================")

    if profile:
        if args.save_json:
            save_and_print_json(profile, "patient_profile_full.json")

        persona = extract_buyer_persona(profile)
        print("\n🧠 Buyer Persona Snapshot")
        print("-------------------------")
        for key, value in persona.items():
            print(f"{key:15}: {value}")

        print("\n👤 Name:        ", persona["full_name"])
        print("👫 Gender:      ", persona["gender"])
        print("🎂 DOB:         ", persona["dob"])
        print("📧 Email:       ", persona["email"])
        print("📞 Phone:       ", persona["phone"])
        print("🌆 City:        ", persona["city"])
        print("🌍 Country:     ", persona["country"])
        print("🆔 Patient ID:  ", persona["patient_id"])
        print("🪪 EID:         ", persona["eid"])
        print("🪪 MRN:         ", persona["mrn"])
    else:
        print("❌ Failed to retrieve patient profile.")
        if error:
            print(error)

if __name__ == "__main__":
    main()
