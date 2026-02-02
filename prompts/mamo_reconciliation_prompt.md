# MAMO POM Reconciliation - Claude Opus 4.5 Prompt

## Task

Perform a two-way reconciliation between **December 2025 MAMO POM payments** and **December 2025 Pharmacy Operations records** to identify:
1. Which payments have matching Pharmacy Ops with Invoice Numbers
2. Which payments have matching Pharmacy Ops but NO Invoice Number
3. Which payments have NO matching Pharmacy Ops
4. Which Pharmacy Ops have NO matching MAMO payment

## Data Files Provided

1. **users.json** - User table from Airtable
2. **pharmacy_operations.json** - Pharmacy Operations (Magenta) table, December 2025
3. **mamo_transactions.json** - MAMO Transactions table, December 2025, status=captured
4. **airtable_data_architecture.md** - Schema documentation
5. **AIRTABLE_SCHEMA_DOCUMENTATION.md** - Additional schema docs
6. **refilling_process.md** - Process documentation

## Filtering Rules

### MAMO Payments (Set A)
- `status` = "captured"
- `created_date` in December 2025
- `Product Category` must contain one of: "POM SH", "POM HL", "POM BG"
- Exclude records where `Product Category` is empty

### Pharmacy Operations (Set B)
- `Date` in December 2025
- Include ALL records (we'll flag invoice status)

## Matching Logic

Match a Pharmacy Ops record to a MAMO payment using ANY of these methods (parallel matching):

1. **User Record ID match**: Pharmacy Ops `User` field links to same User record as MAMO `User` field
2. **Email match**: Look up the User record linked to Pharmacy Ops, get `user_email`, match to MAMO `senderEmail`
3. **Phone match**: Look up the User record linked to Pharmacy Ops, get `billing_phone`, match to MAMO `senderMobile`

### Phone Normalization
Remove: `+`, spaces, `-`, `(`, `)`
Remove leading `971` or `0`

### Email Normalization
Lowercase and trim whitespace

## Output Categories

| Status | Description |
|--------|-------------|
| `MATCHED_WITH_INVOICE` | Payment matched to Pharmacy Ops that HAS Invoice Number |
| `MATCHED_NO_INVOICE` | Payment matched to Pharmacy Ops but Invoice Number is EMPTY |
| `PAYMENT_NO_MATCH` | MAMO payment with no matching Pharmacy Ops |
| `PHARMACY_NO_PAYMENT` | Pharmacy Ops with no matching MAMO payment |

## Expected Output

### Summary Report
```
DECEMBER 2025 MAMO POM RECONCILIATION
=====================================

DATA SUMMARY:
  MAMO POM payments: XXX (POM HL: X, POM SH: X, POM BG: X)
  Pharmacy Ops records: XXX
  Pharmacy Ops with Invoice: XXX
  Pharmacy Ops without Invoice: XXX

RECONCILIATION RESULTS:
  MATCHED_WITH_INVOICE:   XXX (AED XX,XXX.XX)
  MATCHED_NO_INVOICE:     XXX (Pharmacy needs to add invoice)
  PAYMENT_NO_MATCH:       XXX (AED XX,XXX.XX - No Pharmacy record)
  PHARMACY_NO_PAYMENT:    XXX (Pharmacy record with no MAMO payment)

Match Rate: XX.X%
```

### Detailed CSV Output

| Column | Description |
|--------|-------------|
| status | MATCHED_WITH_INVOICE / MATCHED_NO_INVOICE / PAYMENT_NO_MATCH / PHARMACY_NO_PAYMENT |
| mamo_payment_id | MAMO id field |
| payment_date | MAMO created_date |
| amount | MAMO amount |
| customer_email | MAMO senderEmail or User user_email |
| customer_name | MAMO senderName |
| product_category | MAMO Product Category |
| invoice_number | Pharmacy Ops Invoice Number |
| pharmacy_status | Pharmacy Ops Status |
| pharmacy_date | Pharmacy Ops Date |
| match_method | user_id / email / phone / none |
| user_record_id | Airtable User record ID |

## Key Questions to Answer

1. How many MAMO POM payments have matching invoices?
2. How many MAMO POM payments are missing invoices (pharmacy needs to update)?
3. How many MAMO POM payments have NO Pharmacy Ops record at all?
4. How many Pharmacy Ops records have no MAMO payment (likely WooCommerce customers)?
5. What is the total AED amount of matched vs unmatched payments?

## Important Notes

- The `Trigger by` field on Pharmacy Ops is EMPTY for December 2025 data, so don't filter by it
- Some Pharmacy Ops records have no User link - try to match these by email_input field directly
- Phone numbers in MAMO typically have +971 prefix, User table may not
- A Pharmacy Ops without MAMO payment is likely a WooCommerce customer (paid via website, not MAMO subscription)
