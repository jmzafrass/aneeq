"""Fetch Instapract video meeting records for a given email and print key fields."""
import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests


EMAIL = None  # Provide an email string to scope results, or leave None to experiment
APP_ID = "APPANEE0XZ"
COOKIE = (
    "INGRESSCOOKIE=1750849878.147.446.531707|935afc565a31b1d799bebfaef2086db9; "
    "PHPSESSID=1a485b2b896503fcd1e60385d54c67cb; "
    "PHPSESSID=71af77edd00af3157ea78199b8bb7474"
)
BASE_URL = "https://prod-saas-api.instapract.ae/web/api/video/get-meeting-by-email"
OUTPUT_JSON = Path("instapract_meetings.json")
OUTPUT_MIN_JSON = Path("instapract_meetings_min.json")


DATE_FORMATS: Iterable[str] = ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y")


def fetch_meetings(email: Optional[str]) -> Dict[str, Any]:
    headers = {
        "Appid": APP_ID,
        "Cookie": COOKIE,
        "Content-Type": "application/json",
    }
    params = {"email": email} if email else {}
    response = requests.get(BASE_URL, params=params, headers=headers, timeout=60)

    if response.status_code == 400 and not email:
        raise RuntimeError(
            "Endpoint requires an email. Provide EMAIL or use --email CLI flag."
        )

    response.raise_for_status()
    return response.json()


def parse_meeting_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def extract_meeting_fields(meeting: Dict[str, Any]) -> Dict[str, Any]:
    question_groups: List[Dict[str, Any]] = (
        meeting.get("pre_call", {}) or {}
    ).get("questionType", []) or []
    question_type_names = [g.get("name") for g in question_groups if g.get("name")]

    return {
        "id": meeting.get("id"),
        "email": meeting.get("email"),
        "patient_name": meeting.get("patient_name"),
        "practitioner_name": meeting.get("practitioner_name"),
        "date": meeting.get("date"),
        "time": meeting.get("time"),
        "status": meeting.get("status"),
        "payment_status": meeting.get("payment_status"),
        "question_type_names": question_type_names,
        "quiz_result": meeting.get("quiz_result"),
        "medication_name": meeting.get("medication_name"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Instapract meeting details")
    parser.add_argument("--email", help="Patient email to query")
    args = parser.parse_args()

    email = args.email if args.email is not None else EMAIL

    try:
        payload = fetch_meetings(email)
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2))
    print(f"Saved full payload to {OUTPUT_JSON}")

    meetings = payload.get("data")
    if not isinstance(meetings, list):
        print("No meeting list in response; raw keys:", payload.keys())
        return

    today = date.today()
    upcoming = []
    for meeting in meetings:
        meeting_date = parse_meeting_date(meeting.get("date"))
        if meeting_date is None:
            continue
        if meeting_date >= today:
            upcoming.append(meeting)

    if not upcoming:
        print("No meetings found from today onwards.")
        OUTPUT_MIN_JSON.write_text("[]\n")
        return

    minimal = [extract_meeting_fields(meeting) for meeting in upcoming]
    OUTPUT_MIN_JSON.write_text(json.dumps(minimal, indent=2))
    print(f"Saved reduced payload to {OUTPUT_MIN_JSON}")

    for idx, meeting in enumerate(minimal, start=1):
        print(f"\nMeeting {idx}:")
        print(json.dumps(meeting, indent=2))


if __name__ == "__main__":
    main()
