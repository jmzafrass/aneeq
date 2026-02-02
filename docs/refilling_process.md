# Monthly Refilling Process

**Last Updated:** 2025-12-31
**Purpose:** Document the monthly process for generating subscription refill records from MamoPay and WooCommerce into Airtable.

---

## Overview

Each month, we need to:
1. Fetch active subscribers from MamoPay and WooCommerce with next payment dates in the target month
2. Create/update records in the **Subscriptions** table (staging table)
3. Create **Magenta** records for pharmacy operations

### System Architecture

```
MamoPay API ──────┐
                  ├──► Subscriptions Table ──► Magenta Table (Pharmacy)
WooCommerce API ──┘         │                        │
                            │                        │
                            └───► User Table ◄───────┘
                                (Central Customer Data)
```

---

## Prerequisites

### API Credentials

All credentials are loaded from the `.env` file at the project root.

| Service | Env Variable |
|---------|-------------|
| Airtable | `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID` |
| MamoPay | `MAMO_API_KEY` |
| WooCommerce | `WC_CONSUMER_KEY`, `WC_CONSUMER_SECRET` |

### Airtable Table IDs

| Table | ID |
|-------|-----|
| Subscriptions | `tblf0AONAdsaBwo8P` |
| Magenta | `tbl5MDz6ZRUosdsEQ` |
| User | `tblMtIskMF3X3nKWC` |
| Mamo Transactions | `tbl7WfjTqWMnsqpbs` |

---

## Step-by-Step Process

### Step 1: Clear Existing Subscriptions (Optional)

If starting fresh for the month, clear the Subscriptions table:

```python
import os
import requests
import time
from dotenv import load_dotenv
load_dotenv()

BASE_ID = os.getenv('AIRTABLE_BASE_ID')
TOKEN = os.getenv('AIRTABLE_TOKEN')
SUBSCRIPTIONS_TABLE = 'tblf0AONAdsaBwo8P'

headers = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json'
}

# Get all records
url = f'https://api.airtable.com/v0/{BASE_ID}/{SUBSCRIPTIONS_TABLE}'
params = {'fields[]': ['id']}

records = []
offset = None
while True:
    if offset:
        params['offset'] = offset
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    records.extend(data.get('records', []))
    offset = data.get('offset')
    if not offset:
        break

# Delete in batches of 10
for i in range(0, len(records), 10):
    batch = [r['id'] for r in records[i:i+10]]
    params = '&'.join([f'records[]={rid}' for rid in batch])
    requests.delete(f'{url}?{params}', headers=headers)
    time.sleep(0.2)
```

### Step 2: Fetch MamoPay Subscribers

```python
import requests

MAMO_API_KEY = os.getenv('MAMO_API_KEY')
MAMO_BASE_URL = os.getenv('MAMO_BASE_URL')
MAMO_HEADERS = {
    'accept': 'application/json',
    'Authorization': f'Bearer {MAMO_API_KEY}',
}

# Get all subscription IDs from payment links
url = f'{MAMO_BASE_URL}/links'
page = 1
subscription_ids = set()

while True:
    response = requests.get(url, headers=MAMO_HEADERS, params={'page': page, 'per_page': 100})
    data = response.json()
    batch = data.get('data', [])
    if not batch:
        break

    for item in batch:
        subscription = item.get('subscription')
        if subscription and isinstance(subscription, dict):
            sub_id = subscription.get('identifier')
            if sub_id:
                subscription_ids.add(sub_id)

    meta = data.get('pagination_meta', {})
    if page >= meta.get('total_pages', 1):
        break
    page += 1

# Fetch subscribers for each subscription
mamo_subscribers = []
for sid in subscription_ids:
    url = f'{MAMO_BASE_URL}/subscriptions/{sid}/subscribers'
    response = requests.get(url, headers=MAMO_HEADERS, params={'per_page': 100})
    if response.status_code == 200:
        batch = response.json()
        if isinstance(batch, list):
            for sub in batch:
                sub['subscription_id'] = sid
                mamo_subscribers.append(sub)

# Filter for active and target month (e.g., January 2026)
TARGET_MONTH = '2026-01'  # Change this each month
active_mamo = [s for s in mamo_subscribers if s.get('status', '').lower() == 'active']
jan_mamo = [s for s in active_mamo if s.get('next_payment_date', '').startswith(TARGET_MONTH)]
```

**MamoPay Data Structure:**
```json
{
  "id": "MPB-SUBSCRIBER-893CC4FCE6",
  "status": "Active",
  "customer": {
    "id": "CUS-BD27FBFF3B",
    "name": "Customer Name",
    "email": "customer@email.com"
  },
  "next_payment_date": "2026-01-12",
  "subscription_id": "MPB-SUB-0CB8E3E953"
}
```

### Step 3: Fetch WooCommerce Subscribers

```python
from requests.auth import HTTPBasicAuth
from dateutil.parser import isoparse
from datetime import timezone, timedelta

WC_BASE_URL = os.getenv('WC_BASE_URL') + '/subscriptions'
WC_CONSUMER_KEY = os.getenv('WC_CONSUMER_KEY')
WC_CONSUMER_SECRET = os.getenv('WC_CONSUMER_SECRET')
DUBAI_OFFSET = timedelta(hours=4)

page = 1
woo_subs = []

while True:
    response = requests.get(
        WC_BASE_URL,
        auth=HTTPBasicAuth(WC_CONSUMER_KEY, WC_CONSUMER_SECRET),
        params={'per_page': 100, 'page': page, 'status': 'active'}
    )
    batch = response.json()
    if not batch:
        break
    woo_subs.extend(batch)
    page += 1

# Filter for target month (convert UTC to Dubai time)
TARGET_YEAR = 2026
TARGET_MONTH_NUM = 1  # January

jan_woo = []
for sub in woo_subs:
    next_payment = sub.get('next_payment_date_gmt', '')
    if next_payment:
        dt = isoparse(next_payment)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_dubai = dt + DUBAI_OFFSET
        if dt_dubai.year == TARGET_YEAR and dt_dubai.month == TARGET_MONTH_NUM:
            sub['_next_payment_dubai'] = dt_dubai.strftime('%Y-%m-%d')
            jan_woo.append(sub)
```

**WooCommerce Data Structure:**
```json
{
  "id": 12345,
  "status": "active",
  "billing": {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "phone": "+971501234567"
  },
  "next_payment_date_gmt": "2026-01-15T00:00:00"
}
```

### Step 4: Fetch User Data for Matching

```python
USER_TABLE = 'tblMtIskMF3X3nKWC'

url = f'https://api.airtable.com/v0/{BASE_ID}/{USER_TABLE}'
params = {
    'fields[]': ['user_email', 'billing_first_name', 'billing_last_name', 'billing_phone']
}

users = []
offset = None
while True:
    if offset:
        params['offset'] = offset
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    users.extend(data.get('records', []))
    offset = data.get('offset')
    if not offset:
        break

# Build email -> user data mapping
user_data = {}
for u in users:
    fields = u.get('fields', {})
    email = fields.get('user_email', '').lower().strip()
    if email:
        user_data[email] = {
            'record_id': u['id'],
            'first_name': fields.get('billing_first_name', ''),
            'last_name': fields.get('billing_last_name', ''),
            'phone': fields.get('billing_phone', '')
        }
```

### Step 5: Combine and Deduplicate

MamoPay takes priority over WooCommerce (same customer may exist in both):

```python
combined = {}

# MamoPay first (primary source)
for sub in jan_mamo:
    customer = sub.get('customer', {})
    email = customer.get('email', '').lower().strip()
    if email and email not in combined:
        user = user_data.get(email, {})
        combined[email] = {
            'id': sub.get('id', ''),  # MPB-SUBSCRIBER-xxx
            'customer_email': email,
            'customer_name': customer.get('name', ''),
            'next_payment_date': sub.get('next_payment_date', ''),
            'status': sub.get('status', 'Active'),
            'trigger_by': 'MAMO',
            'user_record_id': user.get('record_id'),
            'phone': user.get('phone', ''),
            'first_name': user.get('first_name', ''),
            'last_name': user.get('last_name', '')
        }

# WooCommerce (only emails not in MamoPay)
for sub in jan_woo:
    billing = sub.get('billing', {})
    email = billing.get('email', '').lower().strip()
    if email and email not in combined:
        user = user_data.get(email, {})
        combined[email] = {
            'id': str(sub.get('id', '')),
            'customer_email': email,
            'customer_name': f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip(),
            'next_payment_date': sub.get('_next_payment_dubai', ''),
            'status': sub.get('status', 'active'),
            'trigger_by': 'WOO',
            'user_record_id': user.get('record_id'),
            'phone': billing.get('phone', '') or user.get('phone', ''),
            'first_name': billing.get('first_name', '') or user.get('first_name', ''),
            'last_name': billing.get('last_name', '') or user.get('last_name', '')
        }
```

### Step 6: Create Subscriptions Records

```python
SUBSCRIPTIONS_TABLE = 'tblf0AONAdsaBwo8P'

records_to_create = []
for email, sub in combined.items():
    fields = {
        'id': sub['id'],
        'customer_email': sub['customer_email'],
        'customer_name': sub['customer_name'],
        'next_payment_date': sub['next_payment_date'],
        'status': sub['status'],
        'Trigger by': sub['trigger_by']
    }
    if sub['user_record_id']:
        fields['User'] = [sub['user_record_id']]

    records_to_create.append({'fields': fields})

# Batch create (10 records at a time)
url = f'https://api.airtable.com/v0/{BASE_ID}/{SUBSCRIPTIONS_TABLE}'
for i in range(0, len(records_to_create), 10):
    batch = records_to_create[i:i+10]
    response = requests.post(url, headers=headers, json={'records': batch})
    time.sleep(0.2)  # Rate limiting
```

### Step 7: Create Magenta Records

```python
MAGENTA_TABLE = 'tbl5MDz6ZRUosdsEQ'

# Only create for subscribers with User link
with_user = [s for s in combined.values() if s.get('user_record_id')]

records_to_create = []
for sub in with_user:
    fields = {
        'User': [sub['user_record_id']],
        'Status': '✅ RX Received',
        'Trigger by': sub['trigger_by'],
        'Type of delivery': 'Refill',
        'Refill ': 'Yes',  # Note: field has trailing space
        'Date': sub.get('next_payment_date', ''),
        'email_input': sub.get('customer_email', '')
    }
    records_to_create.append({'fields': fields})

# Batch create
url = f'https://api.airtable.com/v0/{BASE_ID}/{MAGENTA_TABLE}'
for i in range(0, len(records_to_create), 10):
    batch = records_to_create[i:i+10]
    response = requests.post(url, headers=headers, json={'records': batch})
    time.sleep(0.2)
```

---

## Magenta Record Fields

| Field | Field ID | Type | Value |
|-------|----------|------|-------|
| User | `fldvN6axkYcNLCsyD` | Link | User record ID |
| Status | `fldQVkqiFV95jKLhF` | Single Select | `✅ RX Received` |
| Trigger by | `fldNw5tfyBu2fWDPH` | Single Select | `MAMO` or `WOO` |
| Type of delivery | `fld9dMmy3mMLQQdKM` | Single Select | `Refill` |
| Refill  | `fldFNXs5hbJIC7WCJ` | Single Select | `Yes` |
| Date | `fldFVZNGXfLRLNMAz` | Date | Next payment date |
| email_input | `fldXAzw7qF4qR34A6` | Multiline Text | Customer email |

### Status Options
- `✅ RX Received` - Initial status for new refills
- `🧪 In Compounding`
- `🧴 Ready for Dispatch`
- `🚚 Out for Delivery`
- `📦 Delivered`
- `1st Delivery Attempt`

---

## Subscriptions Record Fields

| Field | Field ID | Type | Description |
|-------|----------|------|-------------|
| id | `fldwg72hsdvBaU4GG` | Single Line Text | Primary - MamoPay: `MPB-SUBSCRIBER-xxx`, WooCommerce: numeric ID |
| customer_email | `fldBVULPCKGUL208L` | Single Line Text | Customer email |
| customer_name | `fldqH0CCCNALKCiDQ` | Single Line Text | Customer name |
| next_payment_date | `fldC2kdMobD7b41jK` | Date | Next payment date |
| status | `fldyakMGqTF5xE1Qj` | Single Line Text | `Active` or `active` |
| Trigger by | `fld747nF9tu4slHu7` | Single Select | `MAMO` or `WOO` |
| User | `fldqDRiuwLPbnUX3j` | Link | Link to User table |

---

## Expected Results (January 2026 Example)

| Metric | Count |
|--------|-------|
| MamoPay active subscribers | 143 |
| MamoPay January 2026 | 113 → 104 unique emails |
| WooCommerce active | 325 |
| WooCommerce January 2026 | 123 → 117 unique (not in MamoPay) |
| **Total Subscriptions** | **221** |
| **Total Magenta records** | **219** (2 without User link excluded) |

---

## Troubleshooting

### Common Issues

1. **Duplicate records**: If running multiple times, clear the Subscriptions table first or check for existing records by email before creating.

2. **Missing User links**: Some emails from MamoPay/WooCommerce may not exist in the User table. These subscribers won't get Magenta records created.

3. **Field name case sensitivity**: Airtable field names are case-sensitive. `Type of delivery` (lowercase d) is different from `Type of Delivery`.

4. **Rate limiting**: Airtable allows 5 requests per second. Add `time.sleep(0.2)` between batch operations.

5. **Dubai timezone**: WooCommerce stores dates in UTC. Add 4 hours for Dubai time when filtering by month.

### Verification Queries

Check Subscriptions:
```python
params = {
    'filterByFormula': "AND(YEAR({next_payment_date})=2026, MONTH({next_payment_date})=1)",
    'fields[]': ['customer_email', 'Trigger by']
}
```

Check Magenta:
```python
params = {
    'filterByFormula': "AND({Status}='✅ RX Received', OR({Trigger by}='MAMO', {Trigger by}='WOO'))",
    'fields[]': ['Status', 'Trigger by', 'Date', 'email_input']
}
```

---

## Script Location

Existing scripts that can be referenced:
- `scripts/mamo/get_mamo_next_month_subscribers.py` - MamoPay subscriber fetch
- `scripts/woocommerce/get_woocommerce_subscription.py` - WooCommerce subscription fetch

---

## Monthly Checklist

- [ ] Update `TARGET_MONTH` variable (e.g., `2026-02` for February)
- [ ] Clear Subscriptions table (optional, if starting fresh)
- [ ] Run MamoPay fetch
- [ ] Run WooCommerce fetch
- [ ] Combine and deduplicate by email
- [ ] Create Subscriptions records
- [ ] Create Magenta records
- [ ] Verify counts match expected
- [ ] Notify pharmacy team that new refills are ready
