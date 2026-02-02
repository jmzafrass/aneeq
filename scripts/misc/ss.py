import os
import requests
from dotenv import load_dotenv
load_dotenv()

# Airtable API endpoint
url = "https://api.airtable.com/v0/appb6rkvAv2T3QZOr/Agents"

# Your Personal Access Token
headers = {
    "Authorization": f"Bearer {os.getenv('AIRTABLE_TOKEN')}",
}

# Query parameters
params = {
    "maxRecords": 2,
    "view": "SUPABASE"
}

def fetch_agents():
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()  # will raise an error for non-2xx responses
    return response.json()

if __name__ == "__main__":
    data = fetch_agents()
    print(data)
