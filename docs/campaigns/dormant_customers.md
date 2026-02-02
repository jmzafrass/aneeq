# Dormant Customers Campaign

**Segment Key:** `dormant`

## Purpose

Re-engage customers who haven't ordered in 90+ days. These are past customers who may have churned or forgotten about the service.

## Definition

A user is **Dormant** if:
- They are in the Airtable view "Dormant>90days" from User table
- They are NOT unsubscribed (WhatsApp or Email)

## Data Source

**Table:** `User` (Table ID: `tblMtIskMF3X3nKWC`)

**View:** `Dormant>90days` (pre-filtered by Airtable)

The view already filters for:
- Has made at least one order
- Last order was 90+ days ago
- Is not marked as churned/inactive

Key fields:
| Field | Field ID | Description |
|-------|----------|-------------|
| user_email | `fld3IN0zaJPycb4X5` | Customer email |
| phone_standarised | `fldQbHze486XmjzT5` | Clean phone (971XXXXXXXXX) |
| billing_phone | `fldO88pZCa0JMxoQX` | Raw billing phone |
| first_name | `fldyVlRqXdfN73bCw` | Customer first name |
| unsubscribed_whattsapp | `fld1fKWPanTaLyK55` | WhatsApp opt-out |
| unsubscribed_email | `fldXXX` | Email opt-out |

## Email Campaign

**Template ID:** `d-baa3779d21314c15a8b271c063d2d378`

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

**File Output:** `data/csv/gupshup/gupshup_dormant_YYYYMMDD_HHMMSS.csv`

## Commands

```bash
# Preview
python3 scripts/segmentation/campaign_manager.py --segment dormant --dry-run

# Execute both channels
python3 scripts/segmentation/campaign_manager.py --segment dormant --execute

# WhatsApp CSV only
python3 scripts/segmentation/campaign_manager.py --segment dormant --csv-only

# Email only
python3 scripts/segmentation/campaign_manager.py --segment dormant --email-only --execute

# Test with limit
python3 scripts/segmentation/campaign_manager.py --segment dormant --execute --limit 10
```

## Expected Volume

Based on 2026-01-20 run:
- **Total in view:** ~300+
- **After unsubscribe filter:** ~283

## Phone Number Handling

The script checks multiple phone fields:
1. `phone_standarised` (preferred - already normalized)
2. `billing_phone` (fallback - needs normalization)

All phones are normalized to `971XXXXXXXXX` format for UAE numbers.

## Notes

- The Airtable view handles the 90-day calculation automatically
- No converter detection needed (these are all past customers by definition)
- Simple segment - just fetch view + exclude unsubscribes
