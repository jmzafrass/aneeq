# Airtable Schema Documentation

**Base ID:** `appykWziIu3ZogEa1`
**Generated:** 2025-12-31
**Token:** See `.env` → `AIRTABLE_TOKEN`

---

## Table of Contents

1. [Overview & Relationships](#overview--relationships)
2. [Table: Subscriptions (Middle Table)](#table-subscriptions-middle-table)
3. [Table: Magenta (Pharmacy/Ops Tracking)](#table-magenta-pharmacyops-tracking)
4. [Table: Mamo Transactions (Payment Log)](#table-mamo-transactions-payment-log)
5. [Table: User (Central Customer Data)](#table-user-central-customer-data)
6. [Picklist Reference](#picklist-reference)

---

## Overview & Relationships

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INSTAPRACT AIRTABLE SYSTEM                            │
└─────────────────────────────────────────────────────────────────────────────────┘

                         ┌──────────────────────────┐
                         │          User            │
                         │   (tblMtIskMF3X3nKWC)    │
                         │                          │
                         │   Central Customer Data  │
                         │   - Contact Info         │
                         │   - Billing/Shipping     │
                         │   - ID Documents         │
                         └────────────┬─────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
        ▼                             ▼                             ▼
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│   Subscriptions   │     │ Mamo Transactions │     │ woocommerce_      │
│ (tblf0AONAdsaBwo8P)│     │ (tbl7WfjTqWMnsqpbs)│     │ orders            │
│                   │     │                   │     │ (tblWByCCtBE1dR6ox)│
│  Middle/Import    │     │   Payment Log     │     │                   │
│  Table            │     │                   │     │  WooCommerce      │
│                   │     │                   │     │  Orders Sync      │
└─────────┬─────────┘     └───────────────────┘     └───────────────────┘
          │
          │ Creates records in
          ▼
┌───────────────────┐
│      Magenta      │
│ (tbl5MDz6ZRUosdsEQ)│
│                   │
│  Pharmacy/Ops     │
│  Final Interface  │
└───────────────────┘
```

### Data Flow

1. **MamoPay API** → Subscriptions (Middle Table) - Monthly import of active subscribers
2. **WooCommerce** → Subscriptions (Middle Table) - Order/subscription data import
3. **Subscriptions** → **Magenta** - Creates pharmacy tracking records
4. **All Tables** ↔ **User** - Central customer data linkage
5. **MamoPay Webhooks** → **Mamo Transactions** - Payment events logging

---

## Table: Subscriptions (Middle Table)

**Table ID:** `tblf0AONAdsaBwo8P`
**Primary Field:** `id` (fldwg72hsdvBaU4GG)
**Purpose:** Import staging table for subscription data from MamoPay and WooCommerce

### All Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| `id` | `fldwg72hsdvBaU4GG` | singleLineText | **PRIMARY** - Subscription ID (WooCommerce: numeric, MamoPay: "MPB-SUBSCRIBER-xxx") |
| `status` | `fldyakMGqTF5xE1Qj` | singleLineText | Subscription status (e.g., "active", "Active") |
| `customer_id` | `fldu5QMu53XNPMiu6` | singleLineText | Customer ID from source system |
| `customer_name` | `fldqH0CCCNALKCiDQ` | singleLineText | Customer full name |
| `customer_email` | `fldBVULPCKGUL208L` | singleLineText | Customer email address |
| `next_payment_date` | `fldC2kdMobD7b41jK` | date | Next scheduled payment date (format: l) |
| `User` | `fldqDRiuwLPbnUX3j` | multipleRecordLinks | **LINK** → User table (tblMtIskMF3X3nKWC) |
| `Trigger by` | `fld747nF9tu4slHu7` | singleSelect | Source trigger - see [Picklist: Trigger by](#trigger-by) |
| `Magenta` | `fld21t7ccpBz2A6ib` | multipleRecordLinks | **LINK** → Magenta table (tbl5MDz6ZRUosdsEQ) |
| `Created` | `fldnlPOh0k92QYDI8` | createdTime | Record creation timestamp |
| `already_paid` | `fldKO9r1OVjHqfWge` | singleLineText | Payment date if already paid |

### Lookup Fields (from User)

| Field Name | Field ID | Source Field ID |
|------------|----------|-----------------|
| `billing_phone (from User)` | `fldIIaGw6WLsWRsgv` | fldO88pZCa0JMxoQX |
| `billing_first_name (from User)` | `fld4xnHS8NQ87WnDi` | fldM54lw4WG4bL8cr |
| `billing_last_name (from User)` | `fld66QWeuaGWd4eBh` | fldP3pKVBPmdqxlaD |
| `billing_company (from User)` | `fldeG6UcjXU0zQQj5` | fldd9wlP799yRxDc4 |
| `billing_address_1 (from User)` | `fldkdEU2BOJ2JNNqY` | fldgEXSoFRdHWf0j9 |
| `billing_address_2 (from User)` | `fldw4NqXC2yoxCtJ2` | fldMHXeiLeIf6silK |
| `billing_city (from User)` | `fldZMkEroiPSMTaRx` | fldetNcLrkd4jhrXU |
| `billing_postcode (from User)` | `fldY9B81TvVxsfsLS` | fldkG50DhGuHCUDyx |
| `billing_country (from User)` | `fldhosmiIt3dd6Kqy` | fldDrUm9HaEjCkf8F |
| `billing_state (from User)` | `fld7O6I34xOcoM4HM` | fldMde2uqlRX5UY3r |
| `billing_email (from User)` | `fldqbfHeUJiGlsRlA` | fldlD5NZP9NmQ9c2u |
| `Date (from Magenta)` | `fldh6l9gsSjXnIy4R` | fldFVZNGXfLRLNMAz |

---

## Table: Magenta (Pharmacy/Ops Tracking)

**Table ID:** `tbl5MDz6ZRUosdsEQ`
**Primary Field:** `ID` (fldMK64X09I15D0Eu) - Formula field
**Purpose:** Final operational interface for pharmacy team to track orders, refills, and deliveries

### All Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| `ID` | `fldMK64X09I15D0Eu` | formula | **PRIMARY** - Auto-generated: `{Sequential Number} - {Status} - {Patient Name}` |
| `Patient Name` | `flddJ9e67308f8gay` | aiText | Patient name (AI auto-populated) |
| `MRN` | `fldzF1knoHzGTVoBr` | aiText | Medical Record Number (AI auto-populated) |
| `Product` | `fldB3owGtSuFfWtUq` | aiText | Product ordered (AI auto-populated) |
| `Quantity` | `fldQNtwKzJLbzsRby` | multilineText | Order quantity description |
| `email_input` | `fldXAzw7qF4qR34A6` | multilineText | Email input field |
| `Email` | `fld5hyokxBePDdX5d` | aiText | Customer email (AI auto-populated) |
| `Phone Number` | `fldRKVrkBP0ET11Nn` | aiText | Customer phone (AI auto-populated) |
| `RX #` | `fldMx6Lh9FbWbMC1q` | singleLineText | Prescription number |
| `Date` | `fldFVZNGXfLRLNMAz` | date | Order date (format: l) |
| `Status` | `fldQVkqiFV95jKLhF` | singleSelect | Order status - see [Picklist: Magenta Status](#magenta-status) |
| `Date Delivered` | `fld3yEH4mFdiDtwl6` | dateTime | Delivery completion (timezone: Asia/Dubai) |
| `Emirate` | `fld2w2DeAMMXo1B7s` | singleLineText | UAE Emirate |
| `Refill` | `fldFNXs5hbJIC7WCJ` | singleSelect | Is this a refill? - see [Picklist: Refill (Yes/No)](#refill-yesno) |
| `Receiver` | `fldB4UyLWRkdixXMs` | singleSelect | Who received - see [Picklist: Receiver](#receiver) |
| `Remarks` | `fld1wGmdAfWUUo043` | singleLineText | Notes/remarks |
| `RX Attachment` | `fldijtS9MMwEDr87Q` | multipleAttachments | Prescription file attachments |
| `Sequential Number` | `fldT8TG6FjTvbGD9N` | autoNumber | Auto-incrementing ID |
| `User` | `fldvN6axkYcNLCsyD` | multipleRecordLinks | **LINK** → User table (prefersSingleRecordLink: true) |
| `cleaned_phone` | `fldHTYrJkJ7fJ6tVf` | formula | Phone with special chars removed |
| `standard_phone` | `fld54QfjQLv0riC19` | formula | Standardized phone number (971xxxxxxxxx) |
| `Invoice Number` | `fldWvyOyfFNS2415I` | singleLineText | Invoice number |
| `Invoice Attachment` | `fldWk9rvJaAFwfRvl` | multipleAttachments | Invoice file attachments |
| `Type of delivery` | `fld9dMmy3mMLQQdKM` | singleSelect | Delivery type - see [Picklist: Type of Delivery](#type-of-delivery) |
| `Subscriptions` | `fldjIJU9FHFAdCY30` | multipleRecordLinks | **LINK** → Subscriptions table |
| `Pharmacy` | `fldwCKkYvzRnDqnrD` | singleSelect | Pharmacy assignment - see [Picklist: Pharmacy](#pharmacy) |
| `Refill Status` | `fldJbzwoZWvxD9Xoh` | singleSelect | Refill processing status - see [Picklist: Refill Status](#refill-status) |
| `Reason` | `fld4NBTU5rH1CbgBp` | singleSelect | Cancellation reason - see [Picklist: Reason for Churn](#reason-for-churn) |
| `Order Status` | `fldk2WYT69RzxR34M` | singleSelect | Current order state - see [Picklist: Order Status](#order-status) |
| `Created` | `fldI0qjyo5Hp7TEkX` | createdTime | Record creation timestamp |
| `Last Modified` | `fldh4BHKvqoqotLt1` | lastModifiedTime | Last modification timestamp |

### Timestamp Fields (TAT Tracking)

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| `order_created_at` | `fldRlCHYlqTsEyprM` | createdTime | Order creation time |
| `rx_received_at` | `fldRv5G0ap9uezlFV` | dateTime | RX received timestamp |
| `compounding_started_at` | `fldcyDOhpum8hDZYr` | dateTime | Compounding start time |
| `ready_for_dispatch_at` | `fldniIdtYMvWGJ6is` | dateTime | Ready for dispatch time |
| `out_for_delivery_at` | `fldY1QljQwfQUFAib` | dateTime | Out for delivery time |
| `first_delivery_attempt_at` | `fldFxeWeBJxxnQRil` | dateTime | First delivery attempt time |
| `delivered_at` | `fldanjb3SYtP03PkG` | dateTime | Delivery completion time |
| `status_last_changed_at` | `fldpfzXGOoBuGSrlh` | dateTime | Last status change time |

### TAT Formula Fields

| Field Name | Field ID | Description |
|------------|----------|-------------|
| `tat_created_to_delivered_days` | `fldCMiy7RCscUlCC4` | Total days: creation → delivery |
| `tat_rx_received_to_compounding_hrs` | `fldjxPeXMzR6d7rvI` | Hours: RX received → compounding |
| `tat_compounding_to_ready_dispatch_hrs` | `fldJZy9CIfTgtdyLU` | Hours: compounding → ready |
| `tat_ready_dispatch_to_out_for_delivery_hrs` | `fldZC9f3gQzcy08ga` | Hours: ready → out for delivery |
| `tat_out_for_delivery_to_first_attempt_hrs` | `fldPrdGoJzBNRUOd6` | Hours: out → first attempt |
| `tat_first_attempt_to_delivered_hrs` | `fldZuF9mN4XmqyHOM` | Hours: first attempt → delivered |
| `tat_rx_received_to_delivered_hrs` | `fldFnFEIqaLWEA12D` | Total hours: RX → delivered |
| `tat_ready_dispatch_to_delivered_hrs` | `fldyEtDQtbLEhZBQ3` | Hours: ready → delivered |

### Lookup Fields (from Subscriptions)

| Field Name | Field ID | Source Field |
|------------|----------|--------------|
| `next_payment_date (from Subscriptions)` | `fldQVmtFAXz6ctD2W` | fldC2kdMobD7b41jK |
| `next_payment_date (from Subscriptions)` | `fldlDrGaCwptczHXg` | (duplicate lookup) |
| `billing_phone (from User) (from Subscriptions)` | `fld0pi2sjtobHNX2b` | fldIIaGw6WLsWRsgv |
| `customer_email (from Subscriptions)` | `fldkDt5fFoskSkoQY` | fldBVULPCKGUL208L |
| `billing_email (from User) (from Subscriptions)` | `fldPrKRARnZ5aZLzv` | fldqbfHeUJiGlsRlA |
| `customer_name (from Subscriptions)` | `fldRIIOrj6F1Fh2vu` | fldqH0CCCNALKCiDQ |
| `Billing_address` | `fld5Kr8MaPWtogham` | (from User via Subscriptions) |
| `Billing City` | `fldCRRYiGNNECGjxS` | (from User via Subscriptions) |
| `billing_address_2 (from User)` | `fld6FC1Fvfuw9ndm8` | (from User via Subscriptions) |
| `Status_subscription` | `flds2qbexYVwpGiOG` | fldyakMGqTF5xE1Qj |
| `Trigger by (from Subscriptions)` | `fld0ZZ04zcSR8RRwZ` | fld747nF9tu4slHu7 |
| `already_paid (from Subscriptions)` | `fldueb72LNWOnLzE5` | fldKO9r1OVjHqfWge |

### Lookup Fields (Shipping Address from User)

| Field Name | Field ID |
|------------|----------|
| `Shipping_address_1` | `fldtOOpjemiUzl7hp` |
| `shipping_address_2` | `fldmu4SGxMwVmzj93` |
| `shipping_city` | `fldunU3S66CJjBdow` |
| `shipping_country` | `fldrQTpU3cqBtukrH` |
| `shipping_postcode` | `fldSEMIwqvKcL95XU` |
| `shipping_state` | `fldWtsEtg3J8RYTaR` |

---

## Table: Mamo Transactions (Payment Log)

**Table ID:** `tbl7WfjTqWMnsqpbs`
**Primary Field:** `id` (fldwbSlqNfYXUL41Q)
**Purpose:** Log of all MamoPay payment transactions

### All Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| `id` | `fldwbSlqNfYXUL41Q` | singleLineText | **PRIMARY** - Payment ID (e.g., "PAY-1E9B3C25E2") |
| `customer_details_email` | `fldWKyOVxd9ct64UK` | singleLineText | Customer email from payment |
| `customer_details_phone_number` | `fldiZJDe7fOTIfyES` | singleLineText | Customer phone from payment |
| `customer_details_name` | `fldozBSsIqZYDjRBX` | singleLineText | Customer name from payment |
| `customer_details_comment` | `fldwWjwPjouUUYnMn` | multilineText | Customer notes/comments |
| `created_date` | `fldJclTUpbyib70Lc` | dateTime | Transaction timestamp (timezone: Asia/Dubai) |
| `custom_data_origin_url` | `fldpKaBpTpPCqyLKL` | singleLineText | Origin URL of payment |
| `error_code` | `fldI7ATTpiVxBkp0e` | singleLineText | Error code if failed |
| `error_message` | `fldaRW7oupiAFVpme` | singleLineText | Error message if failed |
| `Order_id` | `fld2OtWesPmiHgLmi` | multipleRecordLinks | **LINK** → woocommerce_orders (prefersSingleRecordLink: true) |
| `next_payment_date` | `fldthZh8Edn8G6pC8` | date | Next scheduled payment date |
| `payment_link_id` | `fldoCJv8JQuSL6cx1` | singleLineText | MamoPay payment link ID |
| `payment_link_url` | `fldMtBHm0mlwy15Nb` | singleLineText | Payment URL |
| `refund_amount` | `fldvpbeJ2ujmHo79y` | currency | Refund amount (precision: 2) |
| `refund_status` | `fldhZDekZhLRlKzHw` | singleLineText | Refund status |
| `status` | `fldacLZI184Xd4td9` | singleSelect | Payment status - see [Picklist: Transaction Status](#transaction-status) |
| `subscription_id` | `fld56ErheAy9ZEAEw` | singleLineText | MamoPay subscription ID (e.g., "MPB-SUB-xxx") |
| `Created` | `fldE7wXRNBXJNYukR` | createdTime | Record creation timestamp |
| `User` | `fldleBVUl3VYSlCRD` | multipleRecordLinks | **LINK** → User table (prefersSingleRecordLink: true) |
| `external_id` | `fldTcJBEqB2xRsgDT` | singleLineText | External reference ID |
| `subscription_frequency` | `fld2vPBFDNx5X119j` | singleLineText | Subscription frequency (e.g., "month") |
| `subscription_frequency_interval` | `fldnKOkZKro37NdEz` | singleLineText | Frequency interval (e.g., "1") |
| `subscription_identifier` | `fldK8Y1BwoJfsPWpT` | singleLineText | Subscription identifier |
| `description` | `fldMalrhJ1PkIaJjV` | singleLineText | Payment description |
| `amount` | `fldQFjDlQWux5532M` | currency | Payment amount (precision: 2) |
| `Product` | `fldCU9cqESTej8Hfb` | multipleRecordLinks | **LINK** → Products table (tblsU18ZUEMiirxJl) |
| `Campaign` | `fldXwSzfE1r0edqMa` | multipleRecordLinks | **LINK** → Campaign table (tblrB2ZQs1wJvY2Ku) |
| `Type` | `fldrnolhRqikz9yrG` | singleSelect | Transaction type - see [Picklist: Transaction Type](#transaction-type) |
| `Source` | `fldRLXysrBpqhjrUe` | singleSelect | Transaction source - see [Picklist: Transaction Source](#transaction-source) |
| `Refill Date` | `fld0rL3errEyxOlAT` | number | Refill date tracking |
| `Refill Status` | `fldPP6VJhIMp9Rfu1` | singleSelect | Refill status - see [Picklist: Refill Status](#refill-status) |
| `Reason for churn` | `fldmi8WknmhiK0CFI` | singleSelect | Churn reason - see [Picklist: Reason for Churn](#reason-for-churn) |
| `Notes and remarks` | `fldw1yADy7A6ivOEv` | multilineText | Notes |
| `Dr Rx` | `fldsUG2TpXPjiDr8I` | checkbox | Doctor prescription required (icon: check, color: greenBright) |
| `discount_total` | `fldolevjYfv5kDu4j` | singleLineText | Discount amount |
| `discount_mamolink` | `flduKTjcPHQHyCCy7` | number | Discount from Mamo link |
| `delivery_mamolink` | `fldRz57m7nzYgrXWz` | number | Delivery fee from Mamo link |
| `payment_title` | `fldlTSGcUcYR9pmeZ` | singleLineText | Payment title |
| `payment_name` | `fldE9DE9wNN8Hn6BX` | singleLineText | Payment name |
| `User copy` | `fldACAtBYLY9tC0li` | singleLineText | Copy of User field |
| `types` | `fldKiYrTB8lZtyeQX` | checkbox | Types flag (icon: check, color: greenBright) |
| `Payment Tyoe` | `fld9Z19A390Nr13iC` | singleSelect | Payment type - see [Picklist: Payment Type](#payment-type) |
| `Doctor` | `fldvQ0IYszfgrJsMi` | singleSelect | Assigned doctor - see [Picklist: Doctor](#doctor) |
| `Last Modified` | `fldh25fU6D3VIfrOq` | lastModifiedTime | Last modification timestamp |
| `Last Modified 2` | `fld6oHvG44PlZgvOp` | lastModifiedTime | Secondary modification timestamp |

### Formula Fields

| Field Name | Field ID | Formula | Result Type |
|------------|----------|---------|-------------|
| `is_subscription` | `fldDP1zWoSherJ71X` | `IF({fld2vPBFDNx5X119j}="","No","Yes")` | singleSelect |
| `billing_cycle` | `fldPbQHeca83T6K9x` | `IF({fldDP1zWoSherJ71X}="No","—",CONCATENATE({fldnKOkZKro37NdEz},"×",{fld2vPBFDNx5X119j}))` | singleLineText |
| `plan_length_months` | `fld0wfhAg8tvDlizA` | Calculates plan length in months | number |
| `link_key` | `fldvYG7JbkNxTTtLS` | `LOWER(REGEX_REPLACE({fldlTSGcUcYR9pmeZ},"[^A-Za-z0-9]+",""))` | singleLineText |
| `Month Order` | `fldLEhNQwxy3bw5aL` | `DATETIME_FORMAT({fldJclTUpbyib70Lc}, 'MMMM')` | singleLineText |
| `day` | `fldaHlboRpHhgOvPX` | `DATETIME_FORMAT({fldJclTUpbyib70Lc}, 'dddd')` | singleLineText |
| `Order Count (from User)` | `fld8gx0eUQSQaL7wV` | Counts orders from comma-separated list | number |

### Lookup Fields

| Field Name | Field ID | Source |
|------------|----------|--------|
| `user_phone` | `fldQqMws16bmneEhr` | User.cleaned_phone |
| `client_manual_control (from User)` | `fldRXPYe504RegeWi` | User.is_customer_antoine |
| `product_id` | `fldbLkYiZnmxJAtgm` | Order.ID_Key |
| `Product Display Name` | `fldy1W9zJTxqMOKqF` | Product.display_name |
| `is_subscription (from Product)` | `fldR8A5KLql0kwtxe` | Product.is_subscription |
| `display_name (from Product)` | `fldj3Dr9SLdahCH09` | Product.display_name |
| `Subscription (from Product)` | `fldMgvoW6OnbVzaPs` | Product.subscription |
| `Name_dashboard` | `fldWNDlJnhHADJKyt` | Product.display_name |
| `Product Category` | `fldudF6mH5H0PMyVz` | Product.category |
| `discount_woocommerce` | `fldlX9THgVXFBjIeJ` | Order.discount_total |
| `woocommerce_shipping_total` | `fldki6PtoxeWAh0Bm` | Order.shipping_total |
| `Invoice Attachment` | `fld8bvInAWxf0n9Cg` | User.Invoice Attachment (from Magenta) |
| `Invoice Number` | `fld2pzOujm2bK4iR9` | User.Invoice Number (from Magenta) |
| `RX #` | `fld7i2pd77CgI0rbc` | User.RX # (from Magenta) |
| `MRN` | `fldrlw9nyTfhu9YRs` | User.MRN (from Magenta) |
| `Created date check` | `fld9nyixln7DgvJIU` | User.Created (from Magenta) |
| `Pharmacy` | `fldlrQrrpWdzjmebe` | User.Pharmacy (from Magenta) |
| `Sub_interval from product` | `fldcmZuTuKWTGKvtx` | Product.sub_interval |
| `First Order Date` | `fldVeK7gyYq1ZZ3yY` | User.First Order Completed (Order) |
| `Last Order Date` | `fld2eJsLehITJdcWY` | User.Last Order Completed (Order) |
| `First Order Date (from User)` | `fldfcvZGxVOtlEzaG` | User.First Order Date |
| `Last Order Date (from User)` | `fldFe3y9E4G75gGtA` | User.Last Order Date |
| `User (from Order_id)` | `flds2M6THnsTS4SRK` | Order.User |
| `created_via_woocommerce` | `fldMHb3l680H96xYz` | Order.created_via |
| `Days Since Last Order (from User)` | `fldeiEfXdmGNFMeuA` | User.Days Since Last Order |
| `Orders (from User)` | `fld4io1QcjGXhziR3` | User.Orders |

---

## Table: User (Central Customer Data)

**Table ID:** `tblMtIskMF3X3nKWC`
**Primary Field:** `source_user_id` (fldwh65yZcAppfpeu)
**Purpose:** Central customer/user data repository

### Core Identity Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| `source_user_id` | `fldwh65yZcAppfpeu` | singleLineText | **PRIMARY** - User ID from source system |
| `user_login` | `fldisd11bZH45Yw3c` | singleLineText | Login username |
| `user_email` | `fld3IN0zaJPycb4X5` | singleLineText | User email |
| `nickname` | `fldxuB5KnPkGuyBGx` | singleLineText | Nickname |
| `first_name` | `fldn8nTNdVNUlbT6O` | singleLineText | First name |
| `last_name` | `fldX8i6zn9WtsqsHO` | singleLineText | Last name |
| `display_name` | `fldzabI5gExF54rNP` | singleLineText | Display name |
| `name` | `fldo6mNOxipof1Fg4` | singleLineText | Full name |
| `gender` | `fldax6sXtOHL2Qfwp` | singleLineText | Gender |
| `dob` | `fld3iEpIHKCD9KSFf` | singleLineText | Date of birth |

### Contact Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| `billing_phone` | `fldO88pZCa0JMxoQX` | singleLineText | Billing phone |
| `shipping_phone` | `fldNDceBCcYbCAAm5` | singleLineText | Shipping phone |
| `phone_number` | `fldn3hg0UEs0U55Ix` | singleLineText | General phone |
| `billing_email` | `fldlD5NZP9NmQ9c2u` | singleLineText | Billing email |

### Billing Address Fields

| Field Name | Field ID | Type |
|------------|----------|------|
| `billing_first_name` | `fldM54lw4WG4bL8cr` | singleLineText |
| `billing_last_name` | `fldP3pKVBPmdqxlaD` | singleLineText |
| `billing_company` | `fldd9wlP799yRxDc4` | singleLineText |
| `billing_address_1` | `fldgEXSoFRdHWf0j9` | singleLineText |
| `billing_address_2` | `fldMHXeiLeIf6silK` | singleLineText |
| `billing_city` | `fldetNcLrkd4jhrXU` | singleLineText |
| `billing_postcode` | `fldkG50DhGuHCUDyx` | singleLineText |
| `billing_country` | `fldDrUm9HaEjCkf8F` | singleLineText |
| `billing_state` | `fldMde2uqlRX5UY3r` | singleLineText |

### Shipping Address Fields

| Field Name | Field ID | Type |
|------------|----------|------|
| `shipping_first_name` | `fldUEh3b2ERfV3XzU` | singleLineText |
| `shipping_last_name` | `fldjYBkPZLWHrrwYU` | singleLineText |
| `shipping_company` | `fldjwW0sB1aERRq4D` | singleLineText |
| `shipping_address_1` | `fldnt6QVlKT02cun0` | singleLineText |
| `shipping_address_2` | `fldyab8OpSX6IIV1Z` | singleLineText |
| `shipping_city` | `fldncMaCSCotlD2f1` | singleLineText |
| `shipping_postcode` | `fldb7A0GL5Ucp1NdN` | singleLineText |
| `shipping_country` | `fldx4G3qE4NZkf7QH` | singleLineText |
| `shipping_state` | `fldekYFPoohYz4oar` | singleLineText |

### ID Document Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| `documentType` | `fld4WGbrg0rkXd5OJ` | singleLineText | Type of ID document |
| `passport` | `fldtAbMWC6ZUXmFvY` | singleLineText | Passport number |
| `emirates` | `fldytSaATdqJjd8hM` | singleLineText | Emirates ID |
| `emirates_front_file` | `fldIEdM4fC3wGLBkM` | singleLineText | Emirates ID front image URL |
| `emirates_back_file` | `fldoLErcZWl7XHPBZ` | singleLineText | Emirates ID back image URL |
| `passport_file` | `fldeinbZJSK7hX6yq` | singleLineText | Passport image URL |
| `id_proof` | `fldE0bCjhe67iVByw` | singleLineText | ID proof front |
| `id_proof_back` | `fldnKzmKPCMeURLp7` | singleLineText | ID proof back |
| `city` | `fldDJklIulQI1Gzpx` | singleLineText | City |

### WooCommerce Fields

| Field Name | Field ID | Type |
|------------|----------|------|
| `user_pass` | `fldvAeeW7PZUsy6Jv` | singleLineText |
| `user_nicename` | `fldP2nK7ON066krxo` | singleLineText |
| `user_registered` | `fld2JrA7EzhXVH7qr` | date |
| `role` | `fldrm8QJSS86p5aVH` | singleLineText |
| `paying_customer` | `fldFkJKEe8xBeZZMb` | singleLineText |
| `wc_last_active` | `fldBT2LE9xI37q440` | singleLineText |
| `wc_money_spent_wp` | `fldM3sntOe3vRPmWo` | singleLineText |
| `last_update` | `fldT2wd8WXoU3KjyZ` | singleLineText |
| `session_tokens` | `fld5JTYVotJhK30CA` | singleLineText |
| `_woocommerce_tracks_anon_id` | `fldZczA257YqYS4R7` | singleLineText |
| `_woocommerce_persistent_cart_1` | `fldwBlm0idWS1M5wl` | singleLineText |
| `_wcs_subscription_ids_cache` | `fldPDreBgzqYoajA9` | singleLineText |
| `wp__stripe_customer_id` | `fldVI5IzsJsz9vLpG` | singleLineText |

### Attribution Fields

| Field Name | Field ID | Type |
|------------|----------|------|
| `_wc_order_attribution_source_type` | `fld6oEMa0eE4n6vPw` | singleLineText |
| `_wc_order_attribution_utm_source` | `fldggXsYvdcXoCkxj` | singleLineText |
| `_wc_order_attribution_utm_medium` | `fldM4MUBfAqResyyJ` | singleLineText |
| `_wc_order_attribution_session_entry` | `fld3Uxva6ZH6baPvB` | singleLineText |
| `_wc_order_attribution_session_start_time` | `fldyHSLG0QFJ2z6Rg` | date |
| `_wc_order_attribution_session_pages` | `fldoIbGcaSMtnbKfs` | singleLineText |
| `_wc_order_attribution_session_count` | `fldjLbcWVeZ5zQPHi` | singleLineText |
| `_wc_order_attribution_user_agent` | `fldvX8FfHFuWJBV80` | singleLineText |
| `_wc_order_attribution_device_type` | `fldwZfhR3blH0ZyQQ` | singleLineText |
| `_wc_order_attribution_referrer` | `fldrd9IkYPezqXy1L` | singleLineText |

### Link Fields

| Field Name | Field ID | Linked Table | Description |
|------------|----------|--------------|-------------|
| `Orders` | `fldnFCVobgdDPwh5I` | tblWByCCtBE1dR6ox | WooCommerce orders |
| `Mamo Transactions` | `fld2i5kHgaPcPvc8I` | tbl7WfjTqWMnsqpbs | MamoPay transactions |
| `Magenta` | `fldVzNVxFLd8j18Pq` | tbl5MDz6ZRUosdsEQ | Pharmacy/Ops records |
| `Subscriptions` | `fldvthlnDaKqDjOgN` | tblf0AONAdsaBwo8P | Subscription records |
| `Abandon Card` | `fldLDMJz3Hjp8ZjzK` | tbloXcWI9IUoPJYUt | Abandoned cart records |
| `adhoc_campaign_aneeq` | `fldVSKQLSBJ6YeFZ4` | tbleLSKMeFP1LF5hT | Adhoc campaigns |
| `Campaign` | `fldTwtDcAnoUDAydL` | tblrB2ZQs1wJvY2Ku | Campaigns |
| `campaigns` | `fldrA3BPWYfec2bFi` | tbl1RH01pn68EE8qh` | Campaigns (alternate) |

### Formula Fields

| Field Name | Field ID | Description | Result Type |
|------------|----------|-------------|-------------|
| `Never_ordered` | `fldB3BYCTZasHBcKJ` | TRUE if never ordered | checkbox |
| `phone_standarised` | `fldQbHze486XmjzT5` | Standardized phone (971xxxxxxxxx) | number |
| `cleaned_phone` | `fldqoWvyMd836Rq2g` | Phone with special chars removed | singleLineText |
| `phone_validation_status` | `fldKWARls7XI2TrUj` | Phone validation result | singleSelect |
| `First Order Date` | `fldkkXuj9C2hA5QkP` | Earliest order date | dateTime |
| `Last Order Date` | `fld0SoJXyydfMgWgE` | Most recent order date | dateTime |
| `Days Since Last Order` | `fld8AwezO9d8xE3cp` | Days since last order | number |

### Checkbox Fields

| Field Name | Field ID | Description |
|------------|----------|-------------|
| `is_customer_antoine` | `fldu86wDs1tRVo0sL` | Manual control flag |
| `unsubscribed_whattsapp` | `fldvXeoKS4ZqNO3le` | WhatsApp unsubscribed |
| `Test` | `fldvNDlkW1jWUmPbx` | Test flag |

### Timestamp Fields

| Field Name | Field ID | Type |
|------------|----------|------|
| `date_created` | `fldZNB8dHq5eLbNnc` | dateTime |
| `date_modified` | `fldf7gjXdQI8GXUtJ` | dateTime |
| `Created` | `fldvrvcBLQSE2R8hK` | createdTime |

### Lookup Fields

| Field Name | Field ID | Source |
|------------|----------|--------|
| `status (from Orders)` | `fldpE4EpOnnUG21Do` | Orders.status |
| `status (from Mamo Transactions)` | `fld3aR9VVbDLWTv1T` | Mamo Transactions.status |
| `First Order Completed (Order)` | `fldeTnLSTQzuwZsWA` | Orders.date_created |
| `Last Order Completed (Order)` | `fldB72Ek86oX63U4X` | Orders.date_created |
| `First Mamo Captured (Mamo)` | `fldApaSgDr8Mg9msE` | Mamo Transactions.created_date |
| `Last Mamo Captured (Mamo)` | `fld8WuGWiUwJYcc9M` | Mamo Transactions.created_date |
| `MRN (from Magenta)` | `fldzxPYjI5r5MEqF2` | Magenta.MRN |
| `RX # (from Magenta)` | `fldVpPuArmIuJIzkJ` | Magenta.RX # |
| `Invoice Number (from Magenta)` | `fld2EEswPGgnNZkfz` | Magenta.Invoice Number |
| `Invoice Attachment (from Magenta)` | `flde0ec9iuCbzgnDn` | Magenta.Invoice Attachment |
| `Created (from Magenta)` | `fldUdS8mrcx18tq2B` | Magenta.Created |
| `Pharmacy (from Magenta)` | `flde7HMkKPu46LAxM` | Magenta.Pharmacy |
| `Category` | `fldE5ZribP5kuBFHR` | Orders.Category (from Product) |
| `Notes` | `fldUI0Ast5c8I6gr0` | multilineText field |

---

## Picklist Reference

### Trigger by
**Field ID:** `fld747nF9tu4slHu7`
**Table:** Subscriptions

| Value | Choice ID | Color |
|-------|-----------|-------|
| `MAMO` | (to be confirmed) | - |

---

### Magenta Status
**Field ID:** `fldQVkqiFV95jKLhF`
**Table:** Magenta

| Value | Choice ID | Color |
|-------|-----------|-------|
| ✅ RX Received | `sellQnk7V7YgoFBxd` | blueLight2 |
| 🧪 In Compounding | `seltP8ftIqcEKr62R` | cyanLight2 |
| 🧴 Ready for Dispatch | `selECNjxHzGVB7lNm` | tealLight2 |
| 🚚 Out for Delivery | `selKGYuYsoZt1liMh` | greenLight2 |
| 📦 Delivered | `seleZddHvLBjggZSY` | yellowLight2 |
| 1st Delivery Attempt | `selg5mivuK2JsUOnn` | orangeLight2 |

---

### Refill (Yes/No)
**Field ID:** `fldFNXs5hbJIC7WCJ`
**Table:** Magenta

| Value | Choice ID | Color |
|-------|-----------|-------|
| Yes | `selOHbCGocsak6dqx` | blueLight2 |
| No | `selAY8HxcyDgZsdyw` | cyanLight2 |

---

### Receiver
**Field ID:** `fldB4UyLWRkdixXMs`
**Table:** Magenta

| Value | Choice ID | Color |
|-------|-----------|-------|
| Patient Received | `selG94vMa95FYE4cF` | blueLight2 |
| Received by representative | `selqFBRPMsASH5su9` | cyanLight2 |

---

### Type of Delivery
**Field ID:** `fld9dMmy3mMLQQdKM`
**Table:** Magenta

| Value | Choice ID | Color |
|-------|-----------|-------|
| Refill | `selWGGminwEOs9DoM` | tealLight2 |
| New Order | `selYi6yd94tw9mBFl` | yellowLight2 |

---

### Pharmacy
**Field ID:** `fldwCKkYvzRnDqnrD`
**Table:** Magenta

| Value | Choice ID | Color |
|-------|-----------|-------|
| Magenta | `selRq4jUb7S836Pc2` | - |
| Revitalife | `selVLT7AmW5m9bPw3` | - |

---

### Refill Status
**Field ID:** `fldPP6VJhIMp9Rfu1` (Mamo Transactions), `fldJbzwoZWvxD9Xoh` (Magenta)
**Tables:** Mamo Transactions, Magenta

| Value | Choice ID | Color |
|-------|-----------|-------|
| Paid | `selzuvux9M3TMXWQk` | greenBright |
| On Hold | `sel1h5B5qg58LperM` | yellowBright |
| Postponed | `sel4BkQh5hDAK4EYz` | tealBright |
| Cancelled | `selTgOXs3HepFgM85` | redBright |
| Early Refill | `selMdPxwAb1NrjcHf` | greenLight2 |

---

### Reason for Churn
**Field ID:** `fldmi8WknmhiK0CFI` (Mamo Transactions), `fld4NBTU5rH1CbgBp` (Magenta)
**Tables:** Mamo Transactions, Magenta

| Value | Choice ID | Color |
|-------|-----------|-------|
| Side Effects | `selriGKz2UZNFMVCB` | blueLight2 |
| Pricing | `sel2FijesahAmZO3q` | cyanLight2 |
| No Answer | `seluQMmkW01Gm4n9E` | yellowLight2 |
| Enough Supply | `selfhUz9oCzZCAutT` | tealLight2 |
| Moving to another treatment / alternatives | `sel7mWVZ1hlpz8F6b` | redLight2 |
| Not Satisfied | `selqxsc07EJW0KFbd` | purpleLight1 |
| Personal / Moved out | `selRlAjHkzSwBwQeN` | grayLight1 |
| Travelling | `selzG7inUniNjEMUA` | greenLight2 |

---

### Transaction Status
**Field ID:** `fldacLZI184Xd4td9`
**Table:** Mamo Transactions

| Value | Choice ID | Color |
|-------|-----------|-------|
| captured | `selwrNIvSbss2mVNk` | blueLight2 |
| failed | `sel7Xx7VwYG8ksB3O` | cyanLight2 |
| card_verified | `selWGGvgRf7dD2bY9` | tealLight2 |

---

### Transaction Type
**Field ID:** `fldrnolhRqikz9yrG`
**Table:** Mamo Transactions

| Value | Choice ID | Color |
|-------|-----------|-------|
| New Sub | `selHS8UeRQMsgQzl0` | greenLight2 |
| One Time | `selEPZZeug1moZ3Qs` | blueLight2 |
| Sub Renewal | `selzklk0kp27Nq1Fn` | tealLight2 |
| Come Back | `selTDmbE6KYi90Qis` | greenLight2 |

---

### Transaction Source
**Field ID:** `fldRLXysrBpqhjrUe`
**Table:** Mamo Transactions

| Value | Choice ID | Color |
|-------|-----------|-------|
| WhatsApp | `selqAu4He6I7yHhZm` | blueLight2 |
| Amazon | `sel8TPK9YFRNM2v71` | cyanLight2 |

---

### Payment Type
**Field ID:** `fld9Z19A390Nr13iC`
**Table:** Mamo Transactions

| Value | Choice ID | Color |
|-------|-----------|-------|
| Mamo | `selCdF2zLwKXfRESO` | blueLight2 |
| WooCommerce | `selU0ncjWHTTFTLau` | cyanLight2 |

---

### Doctor
**Field ID:** `fldvQ0IYszfgrJsMi`
**Table:** Mamo Transactions

| Value | Choice ID | Color |
|-------|-----------|-------|
| Dr Nameer | `selTou5AzrPeYR44B` | blueLight2 |
| Dr Taleb | `seliAkzpmeMcMVMkx` | cyanLight2 |
| Dr Baraa | `sel4n4bZbRst4qkKB` | tealLight2 |
| Dr Waqar | `selOet9VmkOFI7cyw` | greenLight2 |
| Dr Ranjith | `selOUs0UtcBEjAt8U` | yellowLight2 |
| Dr Amanjot | `selwzjTf05v8wzuOf` | orangeLight2 |
| Dr Hessa | `selhvnvQEAmERvuDn` | redLight2 |
| Dr Tooba | `selWrcQNTSsMluQU7` | pinkLight2 |
| Proto Clinic | `selGrTB2aukYbNkwJ` | purpleLight2 |
| Canadian Medical Center | `selDNvIdHuPqb7AjL` | grayLight2 |

---

### Product Category
**Field ID:** `fldudF6mH5H0PMyVz` (Mamo Transactions), `fldE5ZribP5kuBFHR` (User)
**Tables:** Mamo Transactions, User (lookup)

| Value | Choice ID | Color | Description |
|-------|-----------|-------|-------------|
| POM BG | `selqOetfyNiTs78wg` | purpleLight2 | Prescription-Only Medicine - BG |
| POM HL | `selsJGhGwwu08RIrq` | blueLight1 | Prescription-Only Medicine - Hair Loss |
| OTC HL | `selK8fsJQZFjCKmtb` | cyanLight2 | Over-The-Counter - Hair Loss |
| OTC SK | `selSBojLKIXe1Hf0E` | greenLight2 | Over-The-Counter - Skin |
| POM SH | `selJYDtEoU73rfebw` | orangeLight1 | Prescription-Only Medicine - Sexual Health |
| OTC SH | `selccB6HYqzMSaJ17` | orangeLight2 | Over-The-Counter - Sexual Health |

---

### Phone Validation Status (Formula Result)
**Field ID:** `fldKWARls7XI2TrUj`
**Table:** User

| Value | Description |
|-------|-------------|
| ✅ Valid UAE | Valid 12-digit UAE number starting with 971 |
| ⚠️ Plausible International | Valid international format |
| ❌ Invalid Length | Invalid phone number length |

---

### Order Status
**Field ID:** `fldk2WYT69RzxR34M`
**Table:** Magenta

(Choices to be confirmed - field exists but choices not retrieved in schema)

---

## Additional Tables Referenced

| Table Name | Table ID | Purpose |
|------------|----------|---------|
| woocommerce_orders | `tblWByCCtBE1dR6ox` | WooCommerce orders sync |
| Products | `tblsU18ZUEMiirxJl` | Product catalog |
| Campaign | `tblrB2ZQs1wJvY2Ku` | Marketing campaigns |
| Order Items | `tblWhfPh6YPk43Wf6` | Order line items |
| Abandon Card | `tbloXcWI9IUoPJYUt` | Abandoned cart tracking |
| adhoc_campaign_aneeq | `tbleLSKMeFP1LF5hT` | Adhoc campaigns |
| campaigns | `tbl1RH01pn68EE8qh` | Campaigns (alternate) |

---

## Notes

1. **AI Text Fields**: Magenta uses aiText fields (Patient Name, MRN, Product, Email, Phone Number) that auto-populate but may show error states when dependencies are missing.

2. **Duplicate Picklists**: Some picklists (Refill Status, Reason for Churn) exist in both Mamo Transactions and Magenta tables with the same values.

3. **Mixed ID Formats**: The Subscriptions table accepts both numeric IDs (WooCommerce) and "MPB-SUBSCRIBER-xxx" IDs (MamoPay).

4. **Timezone**: Date/time fields use `Asia/Dubai` timezone where specified.

5. **Phone Standardization**: Multiple formula fields exist to clean and standardize phone numbers to `971xxxxxxxxx` format.
