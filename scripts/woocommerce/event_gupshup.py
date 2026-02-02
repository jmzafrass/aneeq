import os
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv()

# Gupshup webhook endpoint and authorization
url = os.getenv("GUPSHUP_URL")
headers = {
    "Authorization": os.getenv("GUPSHUP_AUTH"),
    "Content-Type": "application/json"
}

# Create timestamp in Dubai time (UTC+4) with offset
dubai_time = datetime.now(timezone(timedelta(hours=4)))
event_time = dubai_time.replace(microsecond=0).isoformat()  # Format: '2025-07-17T12:22:09+04:00'

# Payload using Dubai offset time
payload = {
    "event": "quiz_completed",
    "event_time": event_time,
    "user": {
        "id": "test_1",
        "phone": "34655860331",
        "email": "jmzafras@gmail.com",
        "fname": "Juanma"
    },
    "properties": {
        "quiz_type": "sexual_health",
        "quiz_url": "severe-ed/"
    }
}

# Send the POST request
response = requests.post(url, headers=headers, json=payload)

# Debugging output
print("📦 Payload sent:", payload)
print("✅ Status Code:", response.status_code)
print("📨 Response Text:", response.text)
print("📋 Response Headers:", response.headers)
