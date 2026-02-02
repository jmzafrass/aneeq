"""
Dormant Journey Middleware Service
Receives webhooks from Airtable when users enter "Dormant>90days" view
Validates, deduplicates, and sends to Gupshup with correct template
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Dormant Journey Service", version="1.0.0")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Gupshup
GUPSHUP_URL = os.getenv("GUPSHUP_URL")
GUPSHUP_AUTH = os.getenv("GUPSHUP_AUTH")

# Airtable
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_USER_TABLE_ID = os.getenv("AIRTABLE_USER_TABLE_ID", "tblMtIskMF3X3nKWC")

# Deduplication: don't send to same user within X days
DEDUP_DAYS = int(os.getenv("DEDUP_DAYS", "30"))

# Generic event name (single event for all POM customers)
GUPSHUP_EVENT_NAME = os.getenv("GUPSHUP_EVENT_NAME", "dormant_bundle")


# =============================================================================
# MODELS
# =============================================================================

class AirtableWebhook(BaseModel):
    """Payload from Airtable automation webhook"""
    record_id: str
    user_email: str
    phone: str
    fname: Optional[str] = ""
    segment: str  # hair_loss, beard_growth, intimate_health
    last_dormant_send: Optional[str] = None  # ISO date if previously sent


class SendResult(BaseModel):
    success: bool
    message: str
    event_sent: Optional[str] = None
    gupshup_response: Optional[str] = None

# =============================================================================
# HELPERS
# =============================================================================

def get_dubai_time() -> str:
    """Get current time in Dubai timezone (UTC+4) as ISO string"""
    dubai_tz = timezone(timedelta(hours=4))
    return datetime.now(dubai_tz).replace(microsecond=0).isoformat()


def get_dubai_date() -> str:
    """Get current date in Dubai timezone (UTC+4) as YYYY-MM-DD for Airtable"""
    dubai_tz = timezone(timedelta(hours=4))
    return datetime.now(dubai_tz).strftime('%Y-%m-%d')


def normalize_phone(phone: str) -> str:
    """Normalize phone number - remove non-digits, ensure no leading zeros issues"""
    if not phone:
        return ""
    # Remove all non-digit characters
    digits = ''.join(c for c in str(phone) if c.isdigit())
    return digits


def should_skip_dedup(last_send: Optional[str]) -> bool:
    """Check if we should skip due to recent send (deduplication)"""
    if not last_send:
        return False

    try:
        last_send_date = datetime.fromisoformat(last_send.replace('Z', '+00:00'))
        days_since = (datetime.now(timezone.utc) - last_send_date).days
        return days_since < DEDUP_DAYS
    except (ValueError, TypeError):
        return False


def update_airtable_sent(record_id: str, event_name: str) -> bool:
    """Update Airtable record with sent timestamp"""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_USER_TABLE_ID}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "fields": {
            "Last Dormant Send": get_dubai_date(),
            "Last Dormant Event": event_name
        }
    }

    try:
        resp = requests.patch(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info(f"Updated Airtable record {record_id} with send timestamp")
            return True
        else:
            logger.error(f"Failed to update Airtable: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Error updating Airtable: {e}")
        return False


def send_to_gupshup(phone: str, fname: str, event_name: str, user_email: str) -> dict:
    """Send event to Gupshup"""
    headers = {
        "Authorization": GUPSHUP_AUTH,
        "Content-Type": "application/json"
    }

    payload = {
        "event": event_name,
        "user": {
            "id": user_email,
            "phone": normalize_phone(phone),
            "email": user_email,
            "fname": fname or ""
        },
        "properties": {}
    }

    logger.info(f"Sending to Gupshup: event={event_name}, phone={phone}, email={user_email}")

    try:
        resp = requests.post(GUPSHUP_URL, headers=headers, json=payload, timeout=10)
        return {
            "success": resp.status_code in [200, 201, 202],
            "status_code": resp.status_code,
            "response": resp.text
        }
    except Exception as e:
        logger.error(f"Gupshup request failed: {e}")
        return {
            "success": False,
            "status_code": 0,
            "response": str(e)
        }

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "dormant-journey", "version": "1.0.0"}


@app.post("/webhook/dormant", response_model=SendResult)
async def handle_dormant_webhook(payload: AirtableWebhook, background_tasks: BackgroundTasks):
    """
    Handle incoming webhook from Airtable automation.
    Validates, checks dedup, sends to Gupshup, updates Airtable.
    """
    logger.info(f"Received webhook: record={payload.record_id}, email={payload.user_email}, segment={payload.segment}")

    # Validation 1: Must have phone number
    if not payload.phone:
        logger.info(f"Skipping - no phone number for {payload.user_email}")
        return SendResult(
            success=False,
            message="No phone number provided"
        )

    # Validation 2: Deduplication check
    if should_skip_dedup(payload.last_dormant_send):
        logger.info(f"Skipping - already sent within {DEDUP_DAYS} days: {payload.user_email}")
        return SendResult(
            success=False,
            message=f"Already sent within {DEDUP_DAYS} days. Last send: {payload.last_dormant_send}"
        )

    # Use generic event name for all POM customers
    event_name = GUPSHUP_EVENT_NAME

    # Send to Gupshup
    result = send_to_gupshup(
        phone=payload.phone,
        fname=payload.fname,
        event_name=event_name,
        user_email=payload.user_email
    )

    if result["success"]:
        # Update Airtable in background
        background_tasks.add_task(update_airtable_sent, payload.record_id, event_name)

        logger.info(f"Successfully sent {event_name} to {payload.phone}")
        return SendResult(
            success=True,
            message="Event sent successfully",
            event_sent=event_name,
            gupshup_response=result["response"]
        )
    else:
        logger.error(f"Failed to send to Gupshup: {result}")
        return SendResult(
            success=False,
            message=f"Gupshup send failed: {result['response']}",
            event_sent=event_name
        )


@app.post("/test/send")
async def test_send(phone: str, fname: str = "Test"):
    """Test endpoint to manually trigger a send (for debugging)"""
    result = send_to_gupshup(
        phone=phone,
        fname=fname,
        event_name=GUPSHUP_EVENT_NAME,
        user_email="test@test.com"
    )

    return {
        "event": GUPSHUP_EVENT_NAME,
        "phone": phone,
        "result": result
    }
