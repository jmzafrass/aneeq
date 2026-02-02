# Campaign Operations

This folder contains documentation for all marketing campaigns run via the Campaign Manager.

## Quick Start

```bash
cd /Users/juanmanuelzafra/Desktop/projects/instapract
source .venv/bin/activate

# List available segments
python3 scripts/segmentation/campaign_manager.py --list

# Run all campaigns (dry run first)
python3 scripts/segmentation/campaign_manager.py --all --dry-run

# Execute all campaigns
python3 scripts/segmentation/campaign_manager.py --all --execute
```

## Available Campaigns

| Campaign | Segment Key | Documentation |
|----------|-------------|---------------|
| Quiz Droppers | `quiz_droppers` | [quiz_droppers.md](quiz_droppers.md) |
| Dormant Customers | `dormant` | [dormant_customers.md](dormant_customers.md) |
| Active Customers | `active` | [active_customers.md](active_customers.md) |

## Channels

### Email (SendGrid)
- Sends via SendGrid dynamic templates
- Uses ASM unsubscribe group: `229902`
- From: `care@aneeq.co`

### WhatsApp (Gupshup)
- Generates CSV files to `data/csv/gupshup/`
- Format: `Phone,fname,cta_url`
- Upload manually to Gupshup portal after generation

## Main Script

**Location:** `scripts/segmentation/campaign_manager.py`

### Command Options

| Flag | Description |
|------|-------------|
| `--list` | Show available segments |
| `--segment X` | Run specific segment (quiz_droppers, dormant, active) |
| `--all` | Run all segments |
| `--dry-run` | Preview only, no execution |
| `--execute` | Actually send emails / generate CSVs |
| `--csv-only` | Only generate WhatsApp CSVs |
| `--email-only` | Only send emails |
| `--limit N` | Limit to N records (for testing) |

### Common Commands

```bash
# Preview all segments
python3 scripts/segmentation/campaign_manager.py --all --dry-run

# Execute all (Email + WhatsApp CSV)
python3 scripts/segmentation/campaign_manager.py --all --execute

# Quiz droppers - WhatsApp only
python3 scripts/segmentation/campaign_manager.py --segment quiz_droppers --csv-only

# Active customers - Email only
python3 scripts/segmentation/campaign_manager.py --segment active --email-only --execute

# Test with 5 records
python3 scripts/segmentation/campaign_manager.py --segment dormant --execute --limit 5
```

## Weekly Workflow

1. **Preview campaigns:**
   ```bash
   python3 scripts/segmentation/campaign_manager.py --all --dry-run
   ```

2. **Review record counts** - Verify numbers look reasonable

3. **Execute campaigns:**
   ```bash
   python3 scripts/segmentation/campaign_manager.py --all --execute
   ```

4. **Upload WhatsApp CSVs** to Gupshup portal

5. **Monitor SendGrid** for delivery issues

## File Locations

| What | Where |
|------|-------|
| Campaign Manager Script | `scripts/segmentation/campaign_manager.py` |
| Helper Functions | `scripts/segmentation/helpers.py` |
| Quiz Droppers Logic | `scripts/segmentation/quiz_droppers.py` |
| Output CSVs | `data/csv/gupshup/` |
| Slash Command | `.claude/commands/segment.md` |

## Exclusion Logic

All campaigns exclude:
1. **Unsubscribed users** - `unsubscribed_whattsapp` or `unsubscribed_email` = true
2. **Test emails** - @test.com, @example.com, @aneeq.co, etc.
3. **Invalid phones** - Empty or malformed phone numbers

Quiz Droppers additionally excludes:
- **Converters** - Users who made a purchase (via `never_ordered` lookup + direct Mamo/WooCommerce match)
- **Antoine customers** - Legacy customers (`is_customer_antoine` = true)
