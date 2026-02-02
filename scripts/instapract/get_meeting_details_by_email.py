import csv
import json
import sys
import argparse
from pathlib import Path
from urllib.parse import quote

import requests


# --- Config ---------------------------------------------------------------
# Default email can be overridden via --email CLI flag
DEFAULT_EMAIL = "jamiliano15@gmail.com"

# Reuse production headers style from get_patient_profile.py
APP_ID = "APPANEE0XZ"

# Provide your current PHPSESSID here or via --cookie
DEFAULT_COOKIE = "PHPSESSID=dc8e8b14f9e2d2b580e33765e34eb92c"

BASE_URL = "https://prod-saas-api.instapract.ae"
ENDPOINT = "/web/api/video/get-meeting-by-email"


def save_json(data, path: str):
    Path(path).write_text(json.dumps(data, indent=4))


def fetch_meetings(email: str, cookie: str) -> dict:
    """Call the meeting-by-email endpoint and return parsed JSON."""
    headers = {
        "APPID": APP_ID,
        "Content-Type": "application/json",
        "Cookie": cookie,
    }
    url = f"{BASE_URL}{ENDPOINT}?email={quote(email)}"
    resp = requests.get(url, headers=headers, timeout=60)
    try:
        payload = resp.json()
    except requests.JSONDecodeError:
        payload = {"success": False, "status_code": resp.status_code, "raw": resp.text}
    return {
        "status_code": resp.status_code,
        "ok": resp.status_code == 200,
        "payload": payload,
    }


def collect_dynamic_fields(meetings: list[dict]) -> tuple[list[str], list[str]]:
    """
    Inspect meetings and derive:
      - top-level scalar keys across all meetings (excluding nested dict/list)
      - dynamic pre_call question labels (flattened from questionType[].questions[].label)
    Returns (scalar_keys, question_labels)
    """
    scalar_keys: set[str] = set()
    question_labels: set[str] = set()

    for m in meetings:
        # Top-level scalars
        for k, v in (m or {}).items():
            if isinstance(v, (dict, list)):
                continue
            scalar_keys.add(k)

        # Pre-call questions
        pre_call = (m or {}).get("pre_call", {}) or {}
        groups = pre_call.get("questionType", []) or []
        for g in groups:
            for q in g.get("questions", []) or []:
                label = q.get("label")
                if label:
                    question_labels.add(label)

    # Provide a sensible order with a few preferred fields first if present
    preferred = ["date", "patient_name", "email", "quiz_result"]
    ordered_scalar = [k for k in preferred if k in scalar_keys] + sorted(scalar_keys - set(preferred))
    ordered_questions = sorted(question_labels)
    return ordered_scalar, ordered_questions


def build_rows(meetings: list[dict], scalar_fields: list[str], question_labels: list[str]) -> list[dict]:
    rows: list[dict] = []
    for m in meetings:
        row = {k: m.get(k, "") for k in scalar_fields}

        # Add pre_call answers, using label as column name
        answers: dict[str, str] = {}
        pre_call = (m or {}).get("pre_call", {}) or {}
        groups = pre_call.get("questionType", []) or []
        for g in groups:
            for q in g.get("questions", []) or []:
                label = q.get("label")
                answer = q.get("answer", "")
                if label:
                    answers[label] = answer

        for label in question_labels:
            row[label] = answers.get(label, "")

        rows.append(row)
    return rows


def write_csv(rows: list[dict], headers: list[str], path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Export meeting details by email to CSV")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Email to query")
    parser.add_argument("--cookie", default=DEFAULT_COOKIE, help="Cookie header value (e.g., PHPSESSID=...)")
    parser.add_argument("--out", default="meetings_by_email.csv", help="Output CSV file path")
    parser.add_argument("--save-json", action="store_true", help="Also save full JSON response next to CSV")
    args = parser.parse_args()

    result = fetch_meetings(args.email, args.cookie)
    payload = result.get("payload", {})

    if not result.get("ok"):
        print("❌ Request failed:", result.get("status_code"))
        print(payload)
        sys.exit(1)

    # Some APIs wrap in { success, data }
    data = payload.get("data") if isinstance(payload, dict) else None
    meetings = data if isinstance(data, list) else payload if isinstance(payload, list) else []

    if args.save_json:
        json_path = Path(args.out).with_suffix("")
        json_file = f"{json_path}_full.json"
        save_json(payload, json_file)
        print(f"🗂️  Saved full JSON → {json_file}")

    if not meetings:
        print(f"ℹ️  No meetings found for {args.email}")
        # Still create an empty CSV with a minimal header for consistency
        headers = ["date", "patient_name", "email", "quiz_result"]
        write_csv([], headers, args.out)
        print(f"✨ Wrote 0 rows → {args.out}")
        return

    scalar_fields, question_labels = collect_dynamic_fields(meetings)
    headers = scalar_fields + question_labels
    rows = build_rows(meetings, scalar_fields, question_labels)
    write_csv(rows, headers, args.out)
    print(f"✨ Wrote {len(rows)} rows → {args.out}")


if __name__ == "__main__":
    main()

