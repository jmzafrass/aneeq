# Churn Prevention Journey - Brief

**Date:** January 28, 2026

---

## Objective

Prevent customer churn by reaching out **7 days before their subscription renewal is due**.

---

## Logic

```
Days Until Renewal = Subscription Cycle - Days Since Last Order
```

| Window | Condition | Action |
|--------|-----------|--------|
| **Churn Prevention** | 0-7 days until renewal | Send offer to encourage renewal |
| **Dormant** | Past renewal date | Reactivation journey |

---

## Example by Subscription Cycle

| Subscription | Cycle | Churn Prevention | Dormant |
|--------------|-------|------------------|---------|
| Monthly | 30 days | Day 23-29 | Day 30+ |
| Bi-monthly | 60 days | Day 53-59 | Day 60+ |
| Quarterly | 90 days | Day 83-89 | Day 90+ |

---

## Customer Distribution by Cycle

| Cycle | Customers | % |
|-------|-----------|---|
| Monthly (30d) | 1,032 | 75% |
| Bi-monthly (60d) | 143 | 10% |
| Quarterly (90d) | 115 | 8% |
| Other | ~100 | 7% |

---

## Offer

**Free Bundle (500 AED value)** - Skincare & hair products with next order

---

## Implementation

1. Link subscription cycle to User table (from Mamo)
2. Create formula: `Days Until Renewal`
3. Create Airtable view: "Churn Prevention" (Days Until Renewal 0-7)
4. Automation: When user enters view → Send WhatsApp via Gupshup
5. Existing Dormant journey handles users past renewal date

---

## Next Steps

- [ ] Confirm 7-day window is correct
- [ ] Confirm 500 AED bundle offer
- [ ] Marketing to draft WhatsApp message
- [ ] Tech to implement views and automation
