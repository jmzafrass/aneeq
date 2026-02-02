"""
Subscription Payment Reminder Service
Daily cron that sends email reminders 5 days before subscription payment
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
import urllib.parse
from contextlib import asynccontextmanager

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from requests.auth import HTTPBasicAuth
from fastapi import FastAPI
from pydantic import BaseModel
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, To
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# SCHEDULER SETUP
# =============================================================================

scheduler = BackgroundScheduler()

def scheduled_reminder_job():
    """Scheduled job that runs daily at 8 AM Dubai time"""
    logger.info("=== SCHEDULED CRON JOB STARTED ===")
    try:
        result = process_reminders()
        logger.info(f"=== CRON COMPLETE: {result.sent} sent, {result.skipped} skipped, {result.failed} failed ===")
    except Exception as e:
        logger.error(f"=== CRON FAILED: {e} ===")

@asynccontextmanager
async def lifespan(app):
    # Startup: schedule the daily job at 8 AM Dubai (4 AM UTC)
    scheduler.add_job(
        scheduled_reminder_job,
        CronTrigger(hour=4, minute=0, timezone="UTC"),  # 8 AM Dubai = 4 AM UTC
        id="daily_reminders",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started - Daily reminders scheduled for 8 AM Dubai (4 AM UTC)")
    yield
    # Shutdown
    scheduler.shutdown()
    logger.info("Scheduler stopped")

app = FastAPI(title="Subscription Reminders Service", version="1.0.0", lifespan=lifespan)

# =============================================================================
# CONFIGURATION
# =============================================================================

# WooCommerce
WC_BASE_URL = os.getenv("WC_BASE_URL", "https://aneeq.co/wp-json/wc/v3")
WC_CONSUMER_KEY = os.getenv("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.getenv("WC_CONSUMER_SECRET")

# MamoPay
MAMO_API_KEY = os.getenv("MAMO_API_KEY")
MAMO_BASE_URL = os.getenv("MAMO_BASE_URL", "https://business.mamopay.com/manage_api/v1")

# SendGrid
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_TEMPLATE_ID = os.getenv("SENDGRID_TEMPLATE_ID", "subscription_reminder_5days")
FROM_EMAIL = os.getenv("FROM_EMAIL", "care@aneeq.co")
FROM_NAME = os.getenv("FROM_NAME", "aneeq")

# Airtable
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_REMINDERS_TABLE_ID = os.getenv("AIRTABLE_REMINDERS_TABLE_ID", "tblMe3ow4QV7iys0J")

# Reminder settings
REMINDER_DAYS_BEFORE = int(os.getenv("REMINDER_DAYS_BEFORE", "5"))

# Dubai timezone
DUBAI_TZ = timezone(timedelta(hours=4))

# =============================================================================
# MODELS
# =============================================================================

class Subscriber(BaseModel):
    email: str
    name: str
    phone: Optional[str] = ""
    source: str  # WooCommerce or MamoPay
    subscription_id: str
    subscription_name: str
    amount: float
    currency: str
    next_payment_date: str  # YYYY-MM-DD
    frequency: Optional[str] = ""


class ReminderResult(BaseModel):
    total_found: int
    sent: int
    skipped: int
    failed: int
    details: List[Dict]

# =============================================================================
# HELPERS
# =============================================================================

def get_dubai_date() -> str:
    """Get current date in Dubai timezone as YYYY-MM-DD"""
    return datetime.now(DUBAI_TZ).strftime('%Y-%m-%d')


def get_target_date() -> str:
    """Get target payment date (today + REMINDER_DAYS_BEFORE)"""
    target = datetime.now(DUBAI_TZ) + timedelta(days=REMINDER_DAYS_BEFORE)
    return target.strftime('%Y-%m-%d')


def parse_date(date_str: str) -> Optional[str]:
    """Parse various date formats to YYYY-MM-DD"""
    if not date_str:
        return None

    # Try common formats
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.split('+')[0].split('.')[0] + 'Z' if 'Z' not in date_str else date_str, fmt.replace('Z', '') + 'Z' if 'Z' in fmt else fmt)
            return dt.strftime('%Y-%m-%d')
        except:
            pass

    # Last resort: take first 10 chars if it looks like a date
    if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-':
        return date_str[:10]

    return None

# =============================================================================
# DATA FETCHERS
# =============================================================================

def fetch_woocommerce_subscriptions(target_date: str) -> List[Subscriber]:
    """Fetch WooCommerce subscriptions with next payment on target date"""
    logger.info(f"Fetching WooCommerce subscriptions for {target_date}")

    subscribers = []
    page = 1

    while True:
        url = f"{WC_BASE_URL}/subscriptions"
        params = {
            'per_page': 100,
            'page': page,
            'status': 'active'
        }

        try:
            resp = requests.get(
                url,
                auth=HTTPBasicAuth(WC_CONSUMER_KEY, WC_CONSUMER_SECRET),
                params=params,
                timeout=30
            )
            resp.raise_for_status()
            batch = resp.json()

            if not batch:
                break

            for sub in batch:
                next_payment = parse_date(sub.get('next_payment_date_gmt', ''))

                if next_payment == target_date:
                    billing = sub.get('billing', {})
                    line_items = sub.get('line_items', [])
                    product_name = line_items[0].get('name', 'Subscription') if line_items else 'Subscription'

                    # Determine frequency from billing period
                    billing_period = sub.get('billing_period', 'month')
                    billing_interval = sub.get('billing_interval', '1')
                    frequency = f"Every {billing_interval} {billing_period}{'s' if int(billing_interval) > 1 else ''}"

                    subscribers.append(Subscriber(
                        email=billing.get('email', ''),
                        name=f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip(),
                        phone=billing.get('phone', ''),
                        source='WooCommerce',
                        subscription_id=str(sub.get('id', '')),
                        subscription_name=product_name,
                        amount=float(sub.get('total', 0)),
                        currency=sub.get('currency', 'AED'),
                        next_payment_date=next_payment,
                        frequency=frequency
                    ))

            page += 1

        except Exception as e:
            logger.error(f"WooCommerce fetch error: {e}")
            break

    logger.info(f"Found {len(subscribers)} WooCommerce subscriptions for {target_date}")
    return subscribers


def fetch_mamo_subscriptions(target_date: str) -> List[Subscriber]:
    """Fetch MamoPay subscriptions with next payment on target date"""
    logger.info(f"Fetching MamoPay subscriptions for {target_date}")

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {MAMO_API_KEY}",
    }

    subscribers = []

    try:
        # First get all subscription IDs from links
        page = 1
        subscription_ids = set()

        while True:
            url = f"{MAMO_BASE_URL}/links"
            resp = requests.get(url, headers=headers, params={"page": page, "per_page": 100}, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get('data', []):
                subscription = item.get('subscription')
                if subscription and isinstance(subscription, dict):
                    sub_id = subscription.get('identifier')
                    if sub_id:
                        subscription_ids.add(sub_id)

            if len(data.get('data', [])) < 100:
                break
            page += 1

        logger.info(f"Found {len(subscription_ids)} MamoPay subscription IDs")

        # Fetch subscribers for each subscription
        for sub_id in subscription_ids:
            try:
                url = f"{MAMO_BASE_URL}/subscriptions/{sub_id}/subscribers"
                resp = requests.get(url, headers=headers, params={"page": 1, "per_page": 100}, timeout=30)
                resp.raise_for_status()

                subs_data = resp.json()
                if isinstance(subs_data, list):
                    subs_list = subs_data
                else:
                    subs_list = subs_data.get('data', [])

                for sub in subs_list:
                    # Check if active
                    if not sub.get('active', sub.get('is_active', True)):
                        continue

                    # Get next payment date
                    next_payment_raw = (
                        sub.get('next_payment_at') or
                        sub.get('next_payment_date') or
                        sub.get('next_billing_at') or
                        ''
                    )
                    next_payment = parse_date(next_payment_raw)

                    if next_payment == target_date:
                        customer = sub.get('customer', {})

                        subscribers.append(Subscriber(
                            email=customer.get('email', sub.get('email', '')),
                            name=customer.get('name', sub.get('name', '')),
                            phone=customer.get('phone', sub.get('phone', '')),
                            source='MamoPay',
                            subscription_id=sub_id,
                            subscription_name=sub.get('subscription_name', sub.get('plan_name', 'Subscription')),
                            amount=float(sub.get('amount', sub.get('price', 0))),
                            currency=sub.get('currency', 'AED'),
                            next_payment_date=next_payment,
                            frequency=sub.get('frequency', '')
                        ))

            except Exception as e:
                logger.warning(f"Error fetching MamoPay subscription {sub_id}: {e}")
                continue

    except Exception as e:
        logger.error(f"MamoPay fetch error: {e}")

    logger.info(f"Found {len(subscribers)} MamoPay subscriptions for {target_date}")
    return subscribers

# =============================================================================
# DEDUPLICATION
# =============================================================================

def check_already_sent(email: str, next_payment_date: str) -> bool:
    """Check if reminder was already sent for this email + payment date"""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_REMINDERS_TABLE_ID}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}

    # Filter by email and next payment date
    params = {
        "filterByFormula": f"AND({{Email}}='{email}', {{Next Payment Date}}='{next_payment_date}', {{Status}}='Sent')"
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        records = resp.json().get('records', [])
        return len(records) > 0
    except Exception as e:
        logger.warning(f"Error checking dedup for {email}: {e}")
        return False

# =============================================================================
# EMAIL SENDER
# =============================================================================

def send_reminder_email(subscriber: Subscriber) -> bool:
    """Send reminder email via SendGrid"""
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)

        # Format payment date nicely
        payment_date_obj = datetime.strptime(subscriber.next_payment_date, '%Y-%m-%d')
        formatted_date = payment_date_obj.strftime('%B %d, %Y')

        message = Mail(
            from_email=(FROM_EMAIL, FROM_NAME),
            to_emails=subscriber.email
        )

        message.template_id = SENDGRID_TEMPLATE_ID

        # Build WhatsApp pre-filled message for SDR context
        first_name = subscriber.name.split()[0] if subscriber.name else "Customer"
        wa_message = (
            f"Hi, I'm {first_name}. "
            f"I received an email about my upcoming {subscriber.subscription_name} renewal "
            f"on {formatted_date} for {subscriber.currency} {subscriber.amount:,.2f}. "
            f"I'd like to discuss my subscription."
        )
        wa_url = f"https://wa.me/971558024041?text={urllib.parse.quote(wa_message)}"

        message.dynamic_template_data = {
            "first_name": first_name,
            "subscription_name": subscriber.subscription_name,
            "amount": f"{subscriber.currency} {subscriber.amount:,.2f}",
            "payment_date": formatted_date,
            "frequency": subscriber.frequency or "Recurring",
            "manage_url": wa_url
        }

        response = sg.send(message)

        if response.status_code in [200, 201, 202]:
            logger.info(f"Email sent to {subscriber.email}")
            return True
        else:
            logger.error(f"SendGrid error: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Email send error for {subscriber.email}: {e}")
        return False

# =============================================================================
# AIRTABLE LOGGING
# =============================================================================

def log_to_airtable(subscriber: Subscriber, status: str, error_msg: str = "") -> None:
    """Log reminder to Airtable"""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_REMINDERS_TABLE_ID}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "fields": {
            "Email": subscriber.email,
            "Name": subscriber.name,
            "Phone": subscriber.phone or "",
            "Source": subscriber.source,
            "Subscription ID": subscriber.subscription_id,
            "Subscription Name": subscriber.subscription_name,
            "Amount": subscriber.amount,
            "Next Payment Date": subscriber.next_payment_date,
            "Reminder Sent Date": get_dubai_date(),
            "Status": status,
            "Error Message": error_msg
        }
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Airtable log error: {resp.text}")
    except Exception as e:
        logger.warning(f"Airtable log error: {e}")

# =============================================================================
# MAIN PROCESS
# =============================================================================

def process_reminders() -> ReminderResult:
    """Main process: fetch subscriptions, send reminders, log results"""
    target_date = get_target_date()
    logger.info(f"Processing reminders for payment date: {target_date}")

    # Fetch from both sources
    woo_subs = fetch_woocommerce_subscriptions(target_date)
    mamo_subs = fetch_mamo_subscriptions(target_date)

    # Combine and dedupe by email (MamoPay priority if overlap)
    all_subscribers = {}

    for sub in woo_subs:
        if sub.email:
            all_subscribers[sub.email.lower()] = sub

    for sub in mamo_subs:
        if sub.email:
            all_subscribers[sub.email.lower()] = sub  # Override WooCommerce if exists

    subscribers = list(all_subscribers.values())
    logger.info(f"Total unique subscribers to process: {len(subscribers)}")

    # Process each subscriber
    sent = 0
    skipped = 0
    failed = 0
    details = []

    for sub in subscribers:
        # Check if already sent
        if check_already_sent(sub.email, sub.next_payment_date):
            logger.info(f"Skipping {sub.email} - already sent")
            skipped += 1
            details.append({"email": sub.email, "status": "skipped", "reason": "already_sent"})
            continue

        # Send email
        success = send_reminder_email(sub)

        if success:
            sent += 1
            log_to_airtable(sub, "Sent")
            details.append({"email": sub.email, "status": "sent"})
        else:
            failed += 1
            log_to_airtable(sub, "Failed", "Email send failed")
            details.append({"email": sub.email, "status": "failed"})

    result = ReminderResult(
        total_found=len(subscribers),
        sent=sent,
        skipped=skipped,
        failed=failed,
        details=details
    )

    logger.info(f"Reminders complete: {sent} sent, {skipped} skipped, {failed} failed")
    return result

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/")
def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "subscription-reminders",
        "version": "1.0.0",
        "reminder_days_before": REMINDER_DAYS_BEFORE
    }


@app.post("/cron/reminders", response_model=ReminderResult)
def run_reminders():
    """
    Run the reminder process.
    Call this endpoint daily via cron.
    """
    return process_reminders()


@app.get("/preview")
def preview_reminders():
    """Preview what would be sent without actually sending"""
    target_date = get_target_date()

    woo_subs = fetch_woocommerce_subscriptions(target_date)
    mamo_subs = fetch_mamo_subscriptions(target_date)

    # Dedupe
    all_subscribers = {}
    for sub in woo_subs:
        if sub.email:
            all_subscribers[sub.email.lower()] = sub
    for sub in mamo_subs:
        if sub.email:
            all_subscribers[sub.email.lower()] = sub

    subscribers = list(all_subscribers.values())

    return {
        "target_date": target_date,
        "woocommerce_count": len(woo_subs),
        "mamopay_count": len(mamo_subs),
        "total_unique": len(subscribers),
        "subscribers": [
            {
                "email": s.email,
                "name": s.name,
                "source": s.source,
                "subscription_name": s.subscription_name,
                "amount": f"{s.currency} {s.amount}",
                "payment_date": s.next_payment_date
            }
            for s in subscribers[:20]  # Limit preview
        ]
    }

