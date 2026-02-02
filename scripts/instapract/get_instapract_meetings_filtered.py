"""Fetch Instapract meetings for one or more patients with date filtering."""
import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests

APP_ID = "APPANEE0XZ"
COOKIE = (
    "INGRESSCOOKIE=1750849878.147.446.531707|935afc565a31b1d799bebfaef2086db9; "
    "PHPSESSID=1a485b2b896503fcd1e60385d54c67cb; "
    "PHPSESSID=71af77edd00af3157ea78199b8bb7474"
)

PATIENT_URL = "https://prod-saas-api.instapract.ae/web/api/patient/pat-view"
MEETINGS_URL = "https://prod-saas-api.instapract.ae/web/api/video/get-meeting-by-email"

DATE_FORMATS: Sequence[str] = ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y")
TIME_FORMATS: Sequence[str] = ("%I:%M %p", "%H:%M")

HEADERS = {
    "APPID": APP_ID,
    "Content-Type": "application/json",
    "Cookie": COOKIE,
}


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_meeting_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_meeting_datetime(raw_date: Optional[str], raw_time: Optional[str]) -> Optional[datetime]:
    meeting_date = parse_meeting_date(raw_date)
    if meeting_date is None:
        return None

    if not raw_time:
        return datetime.combine(meeting_date, datetime.min.time(), tzinfo=timezone.utc)

    for fmt in TIME_FORMATS:
        try:
            parsed_time = datetime.strptime(raw_time, fmt).time()
            return datetime.combine(meeting_date, parsed_time)
        except ValueError:
            continue

    return datetime.combine(meeting_date, datetime.min.time())


def fetch_patient(email: str) -> Optional[Dict[str, Any]]:
    payload = {"email": email}
    response = requests.post(PATIENT_URL, headers=HEADERS, json=payload, timeout=60)
    if not response.ok:
        print(f"❌ Failed to fetch patient profile for {email}: {response.status_code}")
        return None
    body = response.json()
    if not body.get("success"):
        print(f"❌ API did not return success for {email}: {body.get('msg')}")
        return None
    return body.get("data")


def fetch_meetings(email: str) -> List[Dict[str, Any]]:
    response = requests.get(MEETINGS_URL, params={"email": email}, headers=HEADERS, timeout=60)
    if not response.ok:
        print(f"❌ Failed to fetch meetings for {email}: {response.status_code}")
        return []
    body = response.json()
    data = body.get("data")
    if isinstance(data, list):
        return data
    return []


def question_type_names(meeting: Dict[str, Any]) -> List[str]:
    groups: Iterable[Dict[str, Any]] = (
        meeting.get("pre_call", {}) or {}
    ).get("questionType", []) or []
    return [g.get("name") for g in groups if g.get("name")]


def load_emails(args: argparse.Namespace) -> List[str]:
    emails: List[str] = []
    if args.email:
        emails.extend(args.email)
    if args.emails_file:
        path = Path(args.emails_file)
        if not path.is_file():
            raise FileNotFoundError(f"Emails file not found: {path}")
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                emails.append(line)
    return sorted(set(emails))


def build_rows(email: str, patient: Optional[Dict[str, Any]], meetings: List[Dict[str, Any]], cutoff: date) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    patient_info = patient or {}
    patient_profile = patient_info.get("PatientProfile") or {}

    for meeting in meetings:
        meeting_date = parse_meeting_date(meeting.get("date"))
        if meeting_date is None or meeting_date < cutoff:
            continue

        meeting_dt = parse_meeting_datetime(meeting.get("date"), meeting.get("time"))
        rows.append(
            {
                "patient_email": email,
                "patient_id": patient_profile.get("id"),
                "patient_name": meeting.get("patient_name") or patient_profile.get("display_name"),
                "practitioner_name": meeting.get("practitioner_name"),
                "date": meeting.get("date"),
                "time": meeting.get("time"),
                "status": meeting.get("status"),
                "payment_status": meeting.get("payment_status"),
                "quiz_result": meeting.get("quiz_result"),
                "medication_name": meeting.get("medication_name"),
                "question_type_names": ", ".join(question_type_names(meeting)),
                "meeting_id": meeting.get("id"),
                "meeting_datetime_iso": meeting_dt.isoformat() if meeting_dt else "",
            }
        )
    return rows


def write_output(rows: List[Dict[str, Any]], args: argparse.Namespace) -> None:
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(rows, indent=2))
        print(f"💾 Saved JSON → {args.output_json}")
    if args.output_csv:
        fieldnames = list(rows[0].keys()) if rows else [
            "patient_email",
            "meeting_id",
            "date",
            "time",
            "status",
            "quiz_result",
        ]
        with open(args.output_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"💾 Saved CSV → {args.output_csv}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Instapract meetings for patients with date filtering")
    parser.add_argument("--email", action="append", help="Patient email (can be repeated)")
    parser.add_argument("--emails-file", help="Path to file containing patient emails (one per line)")
    parser.add_argument("--from-date", dest="from_date", help="Only include meetings on/after this date (YYYY-MM-DD)")
    parser.add_argument("--output-json", help="Write filtered meetings to JSON file")
    parser.add_argument("--output-csv", help="Write filtered meetings to CSV file")
    args = parser.parse_args()

    emails = load_emails(args)
    if not emails:
        print("❌ Provide at least one email via --email or --emails-file")
        return

    if args.from_date:
        cutoff_date = parse_iso_date(args.from_date)
    else:
        cutoff_date = date.today()

    print(f"Fetching meetings for {len(emails)} patient(s) from {cutoff_date.isoformat()} onwards…")

    all_rows: List[Dict[str, Any]] = []
    for email in emails:
        print(f"→ {email}")
        patient = fetch_patient(email)
        meetings = fetch_meetings(email)
        rows = build_rows(email, patient, meetings, cutoff_date)
        print(f"   Meetings fetched: {len(meetings)} | kept after filter: {len(rows)}")
        all_rows.extend(rows)

    if not all_rows:
        print("No meetings matched the date filter.")
        return

    write_output(all_rows, args)

    print(f"✅ Total meetings kept: {len(all_rows)}")


if __name__ == "__main__":
    main()
