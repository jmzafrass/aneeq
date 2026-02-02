# Operations Report: Missing Customer in November Payment List

**Date:** October 31, 2025  
**Issue:** Customer ahmadalattar123@gmail.com was not appearing in November payment reports  
**Status:** RESOLVED

---

## Executive Summary

Customer **Ahmad AlAttar** (ahmadalattar123@gmail.com, Customer ID: 4121) was missing from the November 2025 payment list due to a **timezone handling issue** in the subscription filtering script. The customer's payment is scheduled for **October 31, 2025 at 20:26 UTC**, which translates to **November 1, 2025 at 00:26 Dubai time** (12:26 AM).

**Root Cause:** The old script filtered payments using strict UTC dates (Nov 1 00:00 UTC onwards), which excluded payments scheduled for late October 31 UTC that actually occur on November 1 in Dubai timezone.

**Impact:** 1 customer was missing from November payment reports  
**Resolution:** Updated script to use Dubai timezone perspective (UTC+4)

---

## Technical Details

### Customer Information
- **Name:** Ahmad AlAttar
- **Email:** ahmadalattar123@gmail.com
- **Customer ID:** 4121
- **Subscription ID:** 11086
- **Product:** Ultimate Revival - 1 month plan
- **Amount:** 659.00 AED
- **Status:** Active

### Payment Schedule
- **Last Payment:** September 30, 2025 at 20:26 UTC
- **Next Payment (UTC):** October 31, 2025 at 20:26:52 UTC
- **Next Payment (Dubai):** November 1, 2025 at 00:26:52 GST (12:26 AM)

---

## The Problem Explained

### Old Script Behavior (INCORRECT)

```
Date Filter (UTC): November 1, 00:00:00 → December 1, 00:00:00

Timeline:
Oct 31, 20:00 UTC  ──────────┬──────────  Nov 1, 00:00 UTC
                             │
                        Customer's
                     Payment (20:26 UTC)
                             ↓
                         EXCLUDED ❌
                    (Falls in October UTC)
```

**The Issue:** The script only looked at UTC dates. Since the payment was scheduled for October 31 in UTC, it was excluded from the November list.

**But in reality:** This payment happens at 12:26 AM on November 1 in Dubai time, so it SHOULD be in the November list!

---

### New Script Behavior (CORRECT)

```
Date Filter (UTC): October 31, 20:00:00 → November 30, 20:00:00
(Represents Nov 1, 00:00 Dubai → Dec 1, 00:00 Dubai)

Timeline:
Oct 31, 20:00 UTC  ──────────┬──────────  Nov 1, 00:00 UTC
                             │
                        Customer's
                     Payment (20:26 UTC)
                             ↓
                         INCLUDED ✅
         (Falls on November 1 in Dubai time)
```

**The Fix:** The script now adjusts the date range by 4 hours (Dubai's UTC offset) to capture payments that occur in November from Dubai's perspective.

---

## The Critical Window

Payments scheduled between **October 31, 20:00-23:59 UTC** actually occur on **November 1, 00:00-03:59 Dubai time**.

```
UTC Time Zone          Dubai Time Zone (UTC+4)
─────────────────     ─────────────────────────
Oct 31, 20:00  ───→   Nov  1, 00:00  ◄── Midnight Nov 1
Oct 31, 21:00  ───→   Nov  1, 01:00
Oct 31, 22:00  ───→   Nov  1, 02:00
Oct 31, 23:00  ───→   Nov  1, 03:00
Oct 31, 23:59  ───→   Nov  1, 03:59
Nov  1, 00:00  ───→   Nov  1, 04:00
```

**Ahmad AlAttar's payment:**
- UTC: Oct 31, 20:26:52
- Dubai: Nov 1, 00:26:52 (26 minutes after midnight on November 1)

---

## Impact Assessment

### Subscriptions Affected
- **Total November subscriptions (new count):** 94
- **Total November subscriptions (old count):** 93
- **Difference:** 1 subscription

### Only Customer in Critical Window
- **ahmadalattar123@gmail.com** was the ONLY customer with a payment in the critical window (Oct 31 20:00-23:59 UTC)
- All other November payments fall clearly within Nov 1-30 UTC

### Why This Matters
1. **Revenue Tracking:** Payment was being counted in wrong month for Dubai-based reporting
2. **Customer Communication:** November payment reminders were not being sent
3. **Inventory/Fulfillment:** Product shipping schedules could be affected
4. **Financial Reports:** Monthly revenue reports showed incorrect numbers

---

## Resolution

### Code Changes Made
File: `get_woocommerce_subscription.py`

1. **Added Dubai timezone offset constant:**
   ```python
   DUBAI_OFFSET = timedelta(hours=4)
   ```

2. **Created timezone-aware date filtering:**
   ```python
   def month_bounds_dubai_perspective(year, month):
       # Subtract 4 hours to capture Dubai timezone perspective
       start_dubai = datetime(year, month, 1, tzinfo=timezone.utc) - DUBAI_OFFSET
       end_dubai = datetime(year, month + 1, 1, tzinfo=timezone.utc) - DUBAI_OFFSET
       return start_dubai, end_dubai
   ```

3. **Added Dubai time column to output CSV:**
   - New column: `next_payment_date_dubai`
   - Shows the actual local time when payment will occur

### Verification
- Script re-run on October 31, 2025
- Customer ahmadalattar123@gmail.com now appears in output
- CSV file: `subscriptions_mamopay_reconciliation.csv`

---

## Recommendations

### Immediate Actions
1. ✅ Update payment processing systems to use Dubai timezone perspective
2. ✅ Re-generate November payment reports with corrected script
3. ⚠️ Review historical reports to identify if other months were affected
4. ⚠️ Send payment reminder to Ahmad AlAttar for Nov 1 payment (due in ~9 hours)

### Long-term Improvements
1. **Standardize on local timezone:** All payment scheduling should consider Dubai local time
2. **Add timezone validation:** Include timezone info in all date fields
3. **Documentation:** Document timezone handling in all payment-related systems
4. **Monitoring:** Set up alerts for payments in the "critical window" (late day UTC)
5. **Testing:** Add timezone edge cases to automated tests

### Questions to Consider
- Are there other scripts/systems with similar timezone issues?
- Should we adjust Mamo webhook handling for timezone?
- Do we need to retroactively fix October reports?
- Should we notify customers about timezone-based schedule changes?

---

## Contact

For questions about this issue, please contact:
- **Technical Lead:** [Your Name]
- **Date of Report:** October 31, 2025
- **Script Location:** `/Users/juanmanuelzafra/Desktop/instapract/get_woocommerce_subscription.py`

---

## Appendix: Timeline of Investigation

1. **Initial Report:** Customer 4121 expected to appear in November list
2. **First Check:** Customer not found in Mamo API subscription data
3. **Second Check:** Customer found in WooCommerce with active subscription
4. **Discovery:** Payment scheduled for Oct 31 20:26 UTC
5. **Realization:** This is Nov 1 00:26 in Dubai time - timezone issue!
6. **Resolution:** Updated script to handle Dubai timezone perspective
7. **Verification:** Customer now appears in corrected November list

