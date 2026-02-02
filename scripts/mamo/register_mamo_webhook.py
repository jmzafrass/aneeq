import os
import sys
import json
import uuid
import argparse
from typing import List, Optional

import requests
from dotenv import load_dotenv
load_dotenv()


HARDCODED_API_KEY = os.getenv("MAMO_API_KEY")


def env(key: str, required: bool = True, default: Optional[str] = None) -> str:
    val = os.getenv(key, default)
    if required and not val:
        print(f"Missing required environment variable: {key}", file=sys.stderr)
        sys.exit(2)
    return val or ""


def build_headers(api_key: str, idempotency_key: Optional[str] = None) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def load_key_from_file() -> Optional[str]:
    """Load API key from a local file if present.
    File path can be overridden with MAMO_API_KEY_FILE; defaults to mamo_api_key.txt.
    """
    path = os.getenv("MAMO_API_KEY_FILE", "mamo_api_key.txt")
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                key = fh.read().strip()
                return key or None
    except Exception:
        return None
    return None


def create_webhook(base_url: str, api_key: str, url: str, events: List[str], secret: Optional[str], description: Optional[str]) -> dict:
    payload = {
        "url": url,
        # NOTE: Mamo API expects "enabled_events" field for webhook event subscriptions
        "enabled_events": events,
    }
    if secret:
        payload["secret"] = secret
    if description:
        payload["description"] = description

    idem = str(uuid.uuid4())
    resp = requests.post(
        f"{base_url.rstrip('/')}/webhooks",
        headers=build_headers(api_key, idem),
        data=json.dumps(payload),
        timeout=30,
    )
    try:
        data = resp.json()
    except Exception:
        data = {"text": resp.text}
    if not resp.ok:
        raise SystemExit(f"Create webhook failed: {resp.status_code} {data}")
    return data


def list_webhooks(base_url: str, api_key: str) -> dict:
    resp = requests.get(
        f"{base_url.rstrip('/')}/webhooks",
        headers=build_headers(api_key),
        timeout=30,
    )
    try:
        data = resp.json()
    except Exception:
        data = {"text": resp.text}
    if not resp.ok:
        raise SystemExit(f"List webhooks failed: {resp.status_code} {data}")
    return data


def delete_webhook(base_url: str, api_key: str, webhook_id: str) -> dict:
    resp = requests.delete(
        f"{base_url.rstrip('/')}/webhooks/{webhook_id}",
        headers=build_headers(api_key),
        timeout=30,
    )
    if resp.status_code == 204:
        return {"deleted": True}
    try:
        data = resp.json()
    except Exception:
        data = {"text": resp.text}
    if not resp.ok:
        raise SystemExit(f"Delete webhook failed: {resp.status_code} {data}")
    return data


def ping(url: str, event: str = "subscription_payment.succeeded") -> dict:
    # Sends a sample payload to your endpoint to validate delivery.
    payload = {
        "id": str(uuid.uuid4()),
        "type": event,
        "created": uuid.uuid1().time,  # not exact unix time, just a placeholder
        "data": {
            "object": {
                "subscription_id": "sub_test_123",
                "payment_id": "pay_test_123",
                "status": "succeeded" if event.endswith("succeeded") else "failed",
                "amount": {"value": 1000, "currency": "AED"},
            }
        },
        "livemode": False,
    }
    resp = requests.post(url, json=payload, timeout=15)
    return {
        "status": resp.status_code,
        "ok": resp.ok,
        "text": (resp.text[:500] if resp.text else ""),
    }


def main():
    parser = argparse.ArgumentParser(description="Mamo Webhooks helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Create a webhook")
    p_create.add_argument("--url", required=True, help="Target webhook URL")
    p_create.add_argument("--events", nargs="+", required=True, help="Event types to subscribe to")
    p_create.add_argument("--secret", help="Optional signing secret")
    p_create.add_argument("--description", help="Optional description")

    p_list = sub.add_parser("list", help="List webhooks")

    p_delete = sub.add_parser("delete", help="Delete a webhook")
    p_delete.add_argument("--id", required=True, help="Webhook ID")

    p_ping = sub.add_parser("ping", help="Send a test payload to a URL")
    p_ping.add_argument("--url", required=True, help="Target webhook URL to test")
    p_ping.add_argument("--event", default="subscription_payment.succeeded", help="Event type to send in test payload")

    parser.add_argument(
        "--base",
        default=os.getenv("MAMO_API_BASE", ""),
        help="Mamo API base URL (e.g., https://api.mamo.co/v1). Can also use MAMO_API_BASE env",
    )
    parser.add_argument(
        "--key",
        default=os.getenv("MAMO_API_KEY", ""),
        help="Mamo API key (Bearer). Can also use MAMO_API_KEY env",
    )

    args = parser.parse_args()

    if args.cmd in {"create", "list", "delete"}:
        # Resolve base and key with sensible defaults and guard against mix-ups.
        default_base = os.getenv("MAMO_DEFAULT_BASE", "https://business.mamopay.com/manage_api/v1")
        base = args.base or os.getenv("MAMO_API_BASE", "")
        key = args.key or os.getenv("MAMO_API_KEY", "")

        # If the provided base looks like a secret key (starts with sk_),
        # treat it as the API key and fall back to default base URL.
        if base and base.lower().startswith(("sk_", "sk-")):
            if not key:
                key = base
            base = default_base
            print(
                "Note: The value provided for --base/MAMO_API_BASE looks like an API key. "
                "Using it as MAMO_API_KEY and defaulting base to https://business.mamopay.com/manage_api/v1",
                file=sys.stderr,
            )

        # Final fallbacks
        base = base or default_base
        if not key:
            # Try loading from local file as a convenience for local runs
            key = load_key_from_file() or ""
        if not key:
            # Use hardcoded fallback as directed
            key = HARDCODED_API_KEY

        if args.cmd == "create":
            result = create_webhook(base, key, args.url, args.events, args.secret, args.description)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.cmd == "list":
            result = list_webhooks(base, key)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.cmd == "delete":
            result = delete_webhook(base, key, args.id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.cmd == "ping":
        result = ping(args.url, args.event)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
