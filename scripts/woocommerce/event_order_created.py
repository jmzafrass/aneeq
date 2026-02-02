import os
import requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# Gupshup webhook endpoint and authorization
url = os.getenv("GUPSHUP_URL")
headers = {
    "Authorization": os.getenv("GUPSHUP_AUTH"),
    "Content-Type": "application/json"
}

# Payload using your user data and event configuration
payload = {
    "event": "order_created",
    "event_time": datetime.utcnow().isoformat() + "Z",
    "user": {
        "id": "salman-rak@hotmail.com",
        "phone": "971529331332",
        "email": "salman-rak@hotmail.com",
        "fname": "Salem",
        "first_order": "true"
    }
}

# Send the POST request
response = requests.post(url, headers=headers, json=payload)

# Debugging output
print("📦 Payload sent:", payload)
print("✅ Status Code:", response.status_code)
print("📨 Response Text:", response.text)
print("📋 Response Headers:", response.headers)
