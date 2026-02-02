# Active Customers Campaign

**Segment Key:** `active`

## Purpose

Engage current active customers with updates, promotions, or retention messaging. These are your best customers who are actively using the service.

## Definition

A user is **Active** if ANY of these conditions are met:
- They have an active subscription (status='active' in Subscriptions table)
- They placed an order in the last 30 days (status=completed/processing)

AND:
- They are NOT unsubscribed (WhatsApp or Email)

## Data Sources

### 1. Active Subscriptions

**Table:** `Subscriptions` (Table ID: `tblf0AONAdsaBwo8P`)

**Filter:** `status = 'active'`

Key fields:
| Field | Field ID | Description |
|-------|----------|-------------|
| User | link field | Link to User table |
| status | `fldXXX` | Subscription status |

### 2. Recent Orders (Last 30 Days)

**Table:** `woocommerce_orders` (Table ID: `tblWByCCtBE1dR6ox`)

**Filter:**
- `status` IN ('completed', 'processing')
- `date_created` >= 30 days ago

Key fields:
| Field | Field ID | Description |
|-------|----------|-------------|
| customer_id | `fldXXX` | WooCommerce customer ID |
| billing_email | `fldqDCHwVNmjdayge` | Customer email |
| billing_phone | `fldxB8Cy9z0g32my7` | Customer phone |
| billing_first_name | `fldXXX` | Customer first name |
| date_created | `fldXXX` | Order date |
| status | `fldXXX` | Order status |

## Combination Logic

```
Active Customers = (Active Subscribers) UNION (Orders Last 30 Days)
                   - Unsubscribed Users
                   - Deduplicated by email
```

The script:
1. Fetches all active subscriptions → gets linked User records
2. Fetches all orders from last 30 days
3. Builds User lookup for phone/name enrichment
4. Combines both sources, deduplicates by email
5. Excludes unsubscribed users

## Email Campaign

**Template ID:** `d-2b48f06507c642ccaf929177d9ce6b3f`

**CTA URL:** `https://aneeq.co/` (static - homepage)

**Dynamic Variables:**
| Variable | Source | Example |
|----------|--------|---------|
| `cta_url` | Static | `https://aneeq.co/` |

## WhatsApp Campaign

**CSV Format:**
```csv
Phone,fname,cta_url
971501234567,Ahmed,https://aneeq.co/
```

**File Output:** `data/csv/gupshup/gupshup_active_YYYYMMDD_HHMMSS.csv`

## Commands

```bash
# Preview
python3 scripts/segmentation/campaign_manager.py --segment active --dry-run

# Execute both channels
python3 scripts/segmentation/campaign_manager.py --segment active --execute

# WhatsApp CSV only
python3 scripts/segmentation/campaign_manager.py --segment active --csv-only

# Email only
python3 scripts/segmentation/campaign_manager.py --segment active --email-only --execute

# Test with limit
python3 scripts/segmentation/campaign_manager.py --segment active --execute --limit 10
```

## Expected Volume

Based on 2026-01-20 run:
- **Active subscriptions:** ~250
- **Orders last 30 days:** ~150
- **Combined (deduplicated):** ~333
- **Email coverage:** 100%
- **Phone coverage:** 100%

## Phone Number Enrichment

Since orders may not have complete phone data, the script:
1. First checks order's `billing_phone`
2. Falls back to User table's `phone_standarised`
3. Falls back to User table's `billing_phone`

This ensures maximum phone coverage for WhatsApp campaigns.

## Name Handling

First name is extracted from:
1. Order's `billing_first_name`
2. User table's `first_name`
3. Defaults to "there" if not found

## Notes

- This is a "positive" segment - rewarding active customers
- No converter detection needed (they ARE converters)
- Good for loyalty programs, new feature announcements, exclusive offers
- Run weekly to catch new active customers
