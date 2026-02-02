import requests
import csv
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("MAMO_API_KEY")
BASE_URL = "https://business.mamopay.com/manage_api/v1/links"

HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

def fetch_all_links(per_page=100):
    all_links = []
    page = 1

    while True:
        resp = requests.get(
            BASE_URL,
            headers=HEADERS,
            params={"page": page, "per_page": per_page}
        )
        resp.raise_for_status()
        payload = resp.json()

        batch = payload.get("data", [])
        if not batch:
            break
        all_links.extend(batch)

        meta = payload.get("pagination_meta", {})
        if page >= meta.get("total_pages", page):
            break
        page += 1

    return all_links

def parse_datetime(val):
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d-%H-%M-%S").isoformat()
    except ValueError:
        return val

def flatten_link(link):
    out = {}
    for k, v in link.items():
        if k == "created_at":
            out[k] = parse_datetime(v)
        elif isinstance(v, dict):
            for subk, subv in v.items():
                out[f"{k}_{subk}"] = subv
        else:
            out[k] = v
    return out

def export_csv(records, path="mamo_payment_links_export.csv"):
    if not records:
        print("⚠️ No links to write.")
        return
    cols = sorted({col for rec in records for col in rec.keys()})
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(records)
    print(f"✅ Exported {len(records)} links to {path}")

if __name__ == "__main__":
    links = fetch_all_links()
    print(f"✅ Fetched {len(links)} payment links in total.")

    cleaned = [flatten_link(l) for l in links]
    export_csv(cleaned)
