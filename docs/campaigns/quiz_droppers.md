# Quiz Droppers Campaign

**Segment Key:** `quiz_droppers`

## Purpose

Target users who completed a quiz on the Instapract platform but never made a purchase. These are warm leads who showed interest but didn't convert.

## Definition

A user is a **Quiz Dropper** if:
- They have a record in the `instapract` table (completed a quiz)
- They have NOT made a purchase (verified via 3-layer detection)
- They are NOT unsubscribed
- They are NOT a test user

## Data Source

**Primary Table:** `instapract` (Table ID: `tbleLSKMeFP1LF5hT`)

Key fields:
| Field | Field ID | Description |
|-------|----------|-------------|
| Email | `fldUGXOufJC3DcQQ4` | Quiz email |
| Phone Number | `fldaZXw7eXhsXh6U2` | Quiz phone (may have .0 suffix) |
| Name | `fldJvVPfluHfFUb8K` | User's first name |
| Product Link | `fldVOL5uAZ2yL8gQW` | Link to recommended product |
| Date | `fldNTmRbMKgUQHKwz` | Quiz completion date |
| never_ordered | `fldcMtcI9xvZ5vt76` | Lookup from User table |

## Converter Detection (3-Layer)

1. **Lookup field:** Check `never_ordered` from linked User record
   - If `never_ordered = false` → is converter → EXCLUDE
   - If `never_ordered = true` → not converter → continue to layer 2
   - If no User link → continue to layer 2

2. **Direct matching:** Check email/phone against:
   - Mamo Transactions (status=captured)
   - WooCommerce orders (status=completed/processing)

3. **Antoine customers:** Check `is_customer_antoine` in User table
   - If true → legacy converter → EXCLUDE

## Email Campaign

**Template ID:** `d-29a008d0f0f14bec9b320185096ba547`

**Dynamic Variables:**
| Variable | Source | Example |
|----------|--------|---------|
| `cta_url` | Product Link field | `https://aneeq.co/product/hair-loss-treatment/` |

**Note:** Each quiz dropper gets a personalized CTA based on their quiz result (the product recommended to them).

## WhatsApp Campaign

**CSV Format:**
```csv
Phone,fname,cta_url
971501234567,Ahmed,https://aneeq.co/product/hair-loss-treatment/
```

**File Output:** `data/csv/gupshup/gupshup_quiz_droppers_YYYYMMDD_HHMMSS.csv`

## Commands

```bash
# Preview
python3 scripts/segmentation/campaign_manager.py --segment quiz_droppers --dry-run

# Execute both channels
python3 scripts/segmentation/campaign_manager.py --segment quiz_droppers --execute

# WhatsApp CSV only
python3 scripts/segmentation/campaign_manager.py --segment quiz_droppers --csv-only

# Email only
python3 scripts/segmentation/campaign_manager.py --segment quiz_droppers --email-only --execute

# Test with limit
python3 scripts/segmentation/campaign_manager.py --segment quiz_droppers --execute --limit 10
```

## Standalone Script

For more control, use the dedicated script:

```bash
# Audit mode (funnel metrics)
python3 scripts/segmentation/quiz_droppers.py --audit

# Execute with date filter
python3 scripts/segmentation/quiz_droppers.py --execute --since 2025-12-01
```

## Expected Volume

Based on 2026-01-20 run:
- **Total quiz records:** ~3,500+
- **After exclusions:** ~1,780 droppers
- **Exclusion breakdown:**
  - Test emails: ~50
  - No phone: ~200
  - Converters: ~1,200
  - Unsubscribed: ~100
  - Duplicates: ~200

## Deduplication

Records are deduplicated by:
1. **Email** - Keep most recent quiz by Date field
2. **Phone** - Keep most recent quiz by Date field

This ensures each person only receives one message even if they took multiple quizzes.
