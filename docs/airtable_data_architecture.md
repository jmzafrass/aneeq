# Airtable Data Architecture Documentation

**Base ID:** `appykWziIu3ZogEa1`
**Last Updated:** 2026-01-20

---

## Table of Contents
1. [Overview](#overview)
2. [Table Relationships](#table-relationships)
3. [Tables](#tables)
   - [User](#user-table)
   - [woocommerce_orders](#woocommerce_orders-table)
   - [Mamo Transactions](#mamo-transactions-table)
   - [Pharmacy Operations (Magenta)](#pharmacy-operations-table)
   - [Subscriptions](#subscriptions-table)
   - [instapract (Quiz Completions)](#instapract-table-quiz-completions)
   - [Product](#product-table)
   - [Orders Line Items](#orders-line-items-table)
4. [Key Field Mappings](#key-field-mappings)
5. [Data Sources](#data-sources)
6. [Common Data Issues](#common-data-issues)

---

## Overview

This Airtable base manages e-commerce data from multiple sources:
- **WooCommerce** - Main e-commerce platform (orders, customers, products)
- **Mamo** - Payment processor for direct payments and subscriptions
- **Amazon** - Marketplace orders (limited customer data)

---

## Table Relationships

```
┌─────────────────┐       ┌─────────────────────┐       ┌─────────────────┐
│      User       │◄──────│  woocommerce_orders │──────►│ Mamo Transactions│
│                 │       │                     │       │                 │
│ source_user_id  │       │ customer_id         │       │ User (link)     │
│ (PK)            │       │ User (link)         │       │ order_id (link) │
└────────┬────────┘       └──────────┬──────────┘       └─────────────────┘
         │                           │
         │                           │
         │                ┌──────────▼──────────┐       ┌─────────────────┐
         │                │  Orders Line Items  │──────►│     Product     │
         │                │                     │       │                 │
         │                │ order_id (link)     │       │ ID              │
         └────────────────│ Product (link)      │       │ ID_Key          │
         │                └─────────────────────┘       └─────────────────┘
         │
         │
         ▼
┌─────────────────────────┐
│  Pharmacy Operations    │
│      (Magenta)          │
│                         │
│  User (link)            │
│  Status, Invoice #      │
└─────────────────────────┘
```

### Relationship Summary

| From Table | To Table | Link Field | Relationship |
|------------|----------|------------|--------------|
| User | woocommerce_orders | Orders | 1:Many |
| User | Mamo Transactions | Mamo Transactions | 1:Many |
| woocommerce_orders | User | User | Many:1 |
| woocommerce_orders | Mamo Transactions | Mamo Transactions | 1:1 |
| woocommerce_orders | Orders Line Items | Last Update Items | 1:Many |
| Orders Line Items | woocommerce_orders | order_id | Many:1 |
| Orders Line Items | Product | ID_Key | Many:1 |
| Mamo Transactions | User | User | Many:1 |
| Mamo Transactions | woocommerce_orders | order_id | Many:1 |
| Mamo Transactions | Product | Product | Many:1 |
| Pharmacy Operations | User | User | Many:1 |
| User | Pharmacy Operations | Magenta | 1:Many |

---

## Tables

### User Table
**Table ID:** `tblMtIskMF3X3nKWC`
**Primary Field:** `source_user_id`
**Total Fields:** 100

Users/customers from WooCommerce and Mamo payments.

#### Core Identity Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **source_user_id** | `fldwh65yZcAppfpeu` | singleLineText | **PRIMARY KEY** - WooCommerce customer ID (numeric) or `mamo_` prefix for Mamo-only users |
| **user_email** | `fld3IN0zaJPycb4X5` | singleLineText | User's email address |
| **user_login** | `fldisd11bZH45Yw3c` | singleLineText | WooCommerce username |
| **first_name** | `fldn8nTNdVNUlbT6O` | singleLineText | First name |
| **last_name** | `fldX8i6zn9WtsqsHO` | singleLineText | Last name |
| **nickname** | `fldxuB5KnPkGuyBGx` | singleLineText | Display nickname |
| **display_name** | `fldzabI5gExF54rNP` | singleLineText | Display name |
| **name** | `fldo6mNOxipof1Fg4` | singleLineText | Full name |
| **user_nicename** | `fldP2nK7ON066krxo` | singleLineText | URL-friendly name |
| **role** | `fldrm8QJSS86p5aVH` | singleLineText | WooCommerce role (subscriber, customer, etc.) |
| **paying_customer** | `fldFkJKEe8xBeZZMb` | singleLineText | "true" or "false" |

#### Phone Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **billing_phone** | `fldO88pZCa0JMxoQX` | singleLineText | Primary billing phone |
| **shipping_phone** | `fldNDceBCcYbCAAm5` | singleLineText | Shipping phone |
| **phone_number** | `fldn3hg0UEs0U55Ix` | singleLineText | Alternative phone field |
| **phone_standarised** | `fldQbHze486XmjzT5` | formula | Normalized UAE phone (971XXXXXXXXX) |
| **cleaned_phone** | `fldqoWvyMd836Rq2g` | formula | Phone with special chars removed |
| **phone_validation_status** | `fldKWARls7XI2TrUj` | formula | Valid UAE / Plausible International / Invalid |

#### Billing Address Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **billing_first_name** | `fldM54lw4WG4bL8cr` | singleLineText | Billing first name |
| **billing_last_name** | `fldP3pKVBPmdqxlaD` | singleLineText | Billing last name |
| **billing_email** | `fldlD5NZP9NmQ9c2u` | singleLineText | Billing email |
| **billing_company** | `fldd9wlP799yRxDc4` | singleLineText | Billing company |
| **billing_address_1** | `fldgEXSoFRdHWf0j9` | singleLineText | Billing address line 1 |
| **billing_address_2** | `fldMHXeiLeIf6silK` | singleLineText | Billing address line 2 |
| **billing_city** | `fldetNcLrkd4jhrXU` | singleLineText | Billing city |
| **billing_state** | `fldMde2uqlRX5UY3r` | singleLineText | Billing state |
| **billing_postcode** | `fldkG50DhGuHCUDyx` | singleLineText | Billing postal code |
| **billing_country** | `fldDrUm9HaEjCkf8F` | singleLineText | Billing country |

#### Shipping Address Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **shipping_first_name** | `fldUEh3b2ERfV3XzU` | singleLineText | Shipping first name |
| **shipping_last_name** | `fldjYBkPZLWHrrwYU` | singleLineText | Shipping last name |
| **shipping_company** | `fldjwW0sB1aERRq4D` | singleLineText | Shipping company |
| **shipping_address_1** | `fldnt6QVlKT02cun0` | singleLineText | Shipping address line 1 |
| **shipping_address_2** | `fldyab8OpSX6IIV1Z` | singleLineText | Shipping address line 2 |
| **shipping_city** | `fldncMaCSCotlD2f1` | singleLineText | Shipping city |
| **shipping_state** | `fldekYFPoohYz4oar` | singleLineText | Shipping state |
| **shipping_postcode** | `fldb7A0GL5Ucp1NdN` | singleLineText | Shipping postal code |
| **shipping_country** | `fldx4G3qE4NZkf7QH` | singleLineText | Shipping country |

#### ID & Document Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **emirates** | `fldytSaATdqJjd8hM` | singleLineText | Emirates ID |
| **gender** | `fldax6sXtOHL2Qfwp` | singleLineText | Gender |
| **documentType** | `fld4WGbrg0rkXd5OJ` | singleLineText | Document type |
| **passport** | `fldtAbMWC6ZUXmFvY` | singleLineText | Passport number |
| **dob** | `fld3iEpIHKCD9KSFf` | singleLineText | Date of birth |
| **city** | `fldDJklIulQI1Gzpx` | singleLineText | City |
| **emirates_front_file** | `fldIEdM4fC3wGLBkM` | singleLineText | Emirates ID front image URL |
| **emirates_back_file** | `fldoLErcZWl7XHPBZ` | singleLineText | Emirates ID back image URL |
| **passport_file** | `fldeinbZJSK7hX6yq` | singleLineText | Passport image URL |
| **id_proof** | `fldE0bCjhe67iVByw` | singleLineText | ID proof image URL |
| **id_proof_back** | `fldnKzmKPCMeURLp7` | singleLineText | ID proof back image URL |

#### Date & Timestamp Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **user_registered** | `fld2JrA7EzhXVH7qr` | date | Registration date |
| **date_created** | `fldZNB8dHq5eLbNnc` | dateTime | Creation timestamp |
| **date_modified** | `fldf7gjXdQI8GXUtJ` | dateTime | Last modification |
| **last_update** | `fldT2wd8WXoU3KjyZ` | singleLineText | Last update timestamp |
| **Created** | `fldvrvcBLQSE2R8hK` | createdTime | Airtable creation time |

#### Order Tracking Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **Never_ordered** | `fldB3BYCTZasHBcKJ` | formula | TRUE if no completed orders or captured Mamo payments |
| **First Order Date** | `fldkkXuj9C2hA5QkP` | formula | Date of first order |
| **Last Order Date** | `fld0SoJXyydfMgWgE` | formula | Date of last order |
| **Days Since Last Order** | `fld8AwezO9d8xE3cp` | formula | Days since last order |
| **First Order Completed (Order)** | `fldeTnLSTQzuwZsWA` | lookup | First completed order |
| **Last Order Completed (Order)** | `fldB72Ek86oX63U4X` | lookup | Last completed order |
| **First Mamo Captured (Mamo)** | `fldApaSgDr8Mg9msE` | lookup | First captured Mamo payment |
| **Last Mamo Captured (Mamo)** | `fld8WuGWiUwJYcc9M` | lookup | Last captured Mamo payment |
| **status (from Orders)** | `fldpE4EpOnnUG21Do` | lookup | Order statuses |
| **status (from Mamo Transactions)** | `fld3aR9VVbDLWTv1T` | lookup | Mamo payment statuses |

#### Subscription & Marketing Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **unsubscribed_whattsapp** | `fldvXeoKS4ZqNO3le` | checkbox | WhatsApp opt-out |
| **is_customer_antoine** | `fldu86wDs1tRVo0sL` | checkbox | Legacy Antoine customer |
| **Test** | `fldvNDlkW1jWUmPbx` | checkbox | Test user flag |
| **Notes** | `fldUI0Ast5c8I6gr0` | multilineText | Internal notes |

#### Linked Fields

| Field Name | Field ID | Links To | Description |
|------------|----------|----------|-------------|
| **Orders** | `fldnFCVobgdDPwh5I` | woocommerce_orders | All orders for this user |
| **Mamo Transactions** | `fld2i5kHgaPcPvc8I` | Mamo Transactions | All Mamo payments |
| **Magenta** | `fldVzNVxFLd8j18Pq` | Pharmacy Operations | All pharmacy records |
| **Subscriptions** | `fldvthlnDaKqDjOgN` | Subscriptions | User subscriptions |
| **Abandon Card** | `fldLDMJz3Hjp8ZjzK` | Abandon Cart | Abandoned carts |
| **adhoc_campaign_aneeq** | `fldVSKQLSBJ6YeFZ4` | instapract | Quiz records |
| **Campaign** | `fldTwtDcAnoUDAydL` | Campaign | Marketing campaigns |
| **campaigns** | `fldrA3BPWYfec2bFi` | campaigns | Campaign links |

#### Lookup Fields from Pharmacy Operations (Magenta)

These lookups show the **LATEST** record from Pharmacy Operations (Magenta) table:

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **MRN (from Magenta)** | `fldzxPYjI5r5MEqF2` | lookup | Medical Record Number |
| **RX # (from Magenta)** | `fldVpPuArmIuJIzkJ` | lookup | Prescription number |
| **Invoice Number (from Magenta)** | `fld2EEswPGgnNZkfz` | lookup | Pharmacy invoice number |
| **Invoice Attachment (from Magenta)** | `flde0ec9iuCbzgnDn` | lookup | Invoice file |
| **Created (from Magenta)** | `fldUdS8mrcx18tq2B` | lookup | Creation date |
| **Pharmacy (from Magenta)** | `flde7HMkKPu46LAxM` | lookup | Pharmacy name |

> **Known Issue:** These lookups use a "show latest" filter, meaning if the pharmacy hasn't updated the current month's record yet, they will display PREVIOUS month's data. See [Invoice Correlation Issue](#invoice-correlation-issue).

#### Lookup Fields from instapract (Quiz)

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **quiz_url (from adhoc_campaign_aneeq)** | `fldZGV1nuqTjG1IX2` | lookup | Quiz URL from quiz record |
| **Category** | `fldE5ZribP5kuBFHR` | lookup | Product category |

#### WooCommerce Metadata Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **user_pass** | `fldvAeeW7PZUsy6Jv` | singleLineText | Encrypted password |
| **wc_last_active** | `fldBT2LE9xI37q440` | singleLineText | Last WooCommerce activity |
| **wc_money_spent_wp** | `fldM3sntOe3vRPmWo` | singleLineText | Total money spent |
| **session_tokens** | `fld5JTYVotJhK30CA` | singleLineText | Session tokens |
| **wp__stripe_customer_id** | `fldVI5IzsJsz9vLpG` | singleLineText | Stripe customer ID |
| **_woocommerce_tracks_anon_id** | `fldZczA257YqYS4R7` | singleLineText | WooCommerce tracking ID |
| **_woocommerce_persistent_cart_1** | `fldwBlm0idWS1M5wl` | singleLineText | Persistent cart data |
| **_wcs_subscription_ids_cache** | `fldPDreBgzqYoajA9` | singleLineText | Subscription IDs cache |

#### WooCommerce Attribution Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **_wc_order_attribution_source_type** | `fld6oEMa0eE4n6vPw` | singleLineText | Attribution source type |
| **_wc_order_attribution_utm_source** | `fldggXsYvdcXoCkxj` | singleLineText | UTM source |
| **_wc_order_attribution_utm_medium** | `fldM4MUBfAqResyyJ` | singleLineText | UTM medium |
| **_wc_order_attribution_session_entry** | `fld3Uxva6ZH6baPvB` | singleLineText | Session entry page |
| **_wc_order_attribution_session_start_time** | `fldyHSLG0QFJ2z6Rg` | date | Session start time |
| **_wc_order_attribution_session_pages** | `fldoIbGcaSMtnbKfs` | singleLineText | Pages visited |
| **_wc_order_attribution_session_count** | `fldjLbcWVeZ5zQPHi` | singleLineText | Session count |
| **_wc_order_attribution_user_agent** | `fldvX8FfHFuWJBV80` | singleLineText | User agent |
| **_wc_order_attribution_device_type** | `fldwZfhR3blH0ZyQQ` | singleLineText | Device type |
| **_wc_order_attribution_referrer** | `fldrd9IkYPezqXy1L` | singleLineText | Referrer URL |

#### Source User ID Patterns

| Pattern | Source | Example |
|---------|--------|---------|
| Numeric | WooCommerce customer | `5416` |
| `mamo_email@...` | Mamo payment (email known) | `mamo_john@example.com` |
| `mamo_PAY-XXXXX` | Mamo payment (no email) | `mamo_PAY-A49E742137` |
| Email address | Legacy import | `john@example.com` |

---

### woocommerce_orders Table
**Table ID:** `tblWByCCtBE1dR6ox`
**Primary Field:** `id`

Orders from WooCommerce store.

#### Key Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **id** | `fldbdS5WfvMJAm5AI` | singleLineText | **PRIMARY KEY** - WooCommerce order ID |
| **status** | `fldZfvzEEa2oRdb5y` | singleLineText | Order status (processing, completed, cancelled, etc.) |
| **customer_id** | `fldlyg2960NjEXheb` | singleLineText | WooCommerce customer ID (links to User.source_user_id) |
| **total** | `fldZnMG67iGY0hgdX` | currency (AED) | Order total |
| **discount_total** | `fld6jUH6LQ3cSzDoV` | currency (AED) | Discount amount |
| **shipping_total** | `fldMD0HzbsJd4YIz5` | currency (AED) | Shipping cost |
| **date_created** | `fldKhyUfv7kYpkkZ2` | dateTime | Order creation date |
| **date_paid** | `fldolqFipmKhZwwyt` | dateTime | Payment date |
| **payment method** | `fldxEWv5LfmTcyGjz` | singleLineText | Payment method (stripe, mamo, etc.) |
| **transaction_id** | `fldhxOEskUTOAzGif` | singleLineText | Payment transaction ID |
| **created_via** | `fldIbTpYZsvmrooI0` | singleLineText | Order source (checkout, admin, rest-api) |
| **coupon code** | `fldVTJgmIfLbL5EBi` | singleLineText | Applied coupon |

#### Linked Fields

| Field Name | Field ID | Links To | Description |
|------------|----------|----------|-------------|
| **User** | `fldj7AynjIIiliovr` | User | Customer record |
| **Mamo Transactions** | `fldfkZqVlHjvI0vnZ` | Mamo Transactions | Associated Mamo payment |
| **Last Update Items** | `fldypqfGQvG54tNrO` | Orders Line Items | Line items in order |
| **Campaign** | `fldX4wESEcJ7y3dHD` | Campaigns | Marketing campaign |

#### Billing/Shipping Fields

| Field Name | Field ID | Type |
|------------|----------|------|
| First Name (Billing) | `fldHnfaUQARHgVlax` | singleLineText |
| Last Name (Billing) | `fldVLKdM7hw2knJSq` | singleLineText |
| Email (Billing) | `fldqDCHwVNmjdayge` | singleLineText |
| Phone (Billing) | `fldxB8Cy9z0g32my7` | singleLineText |
| Address 1&2 (Billing) | `fldN2WPFC7NeLzMEF` | singleLineText |
| City (Billing) | `fldkrLSNpdaoHVyZy` | singleLineText |
| State Code (Billing) | `fldpzVL8egin5gfs3` | singleLineText |

#### Order Statuses

| Status | Description |
|--------|-------------|
| `pending` | Awaiting payment |
| `processing` | Payment received, awaiting fulfillment |
| `on-hold` | Awaiting action |
| `completed` | Fulfilled |
| `cancelled` | Cancelled |
| `refunded` | Refunded |
| `failed` | Payment failed |
| `checkout-draft` | Abandoned checkout |

---

### Mamo Transactions Table
**Table ID:** `tbl7WfjTqWMnsqpbs`
**Primary Field:** `id`

Payment transactions from Mamo payment processor. Includes one-time payments, subscription renewals, and refill management.

#### Core Payment Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **id** | `fldwbSlqNfYXUL41Q` | singleLineText | **PRIMARY KEY** - Mamo payment ID |
| **status** | `fldacLZI184Xd4td9` | singleSelect | captured, failed, card_verified |
| **amount** | `fldQFjDlQWux5532M` | currency (AED) | Payment amount |
| **created_date** | `fldJclTUpbyib70Lc` | dateTime | Transaction date |
| **Created** | `fldE7wXRNBXJNYukR` | createdTime | Record creation timestamp |
| **Last Modified** | `fldh25fU6D3VIfrOq` | lastModifiedTime | Last update timestamp |
| **payment_link_id** | `fldoCJv8JQuSL6cx1` | singleLineText | Payment link identifier |
| **payment_link_url** | `fldMtBHm0mlwy15Nb` | singleLineText | Full payment link URL |
| **payment_title** | `fldlTSGcUcYR9pmeZ` | singleLineText | Payment link title |
| **payment_name** | `fldE9DE9wNN8Hn6BX` | singleLineText | Payment name |
| **description** | `fldMalrhJ1PkIaJjV` | singleLineText | Payment description |
| **external_id** | `fldTcJBEqB2xRsgDT` | singleLineText | External reference ID |

#### Customer Details Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **customer_details_name** | `fldozBSsIqZYDjRBX` | singleLineText | Customer name from payment form |
| **customer_details_email** | `fldWKyOVxd9ct64UK` | singleLineText | Customer email from payment form |
| **customer_details_phone_number** | `fldiZJDe7fOTIfyES` | singleLineText | Customer phone from payment form |
| **customer_details_comment** | `fldwWjwPjouUUYnMn` | multilineText | Customer comment |
| **custom_data_origin_url** | `fldpKaBpTpPCqyLKL` | singleLineText | Origin URL of payment |

#### Subscription Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **subscription_id** | `fld56ErheAy9ZEAEw` | singleLineText | Mamo subscription ID |
| **subscription_identifier** | `fldK8Y1BwoJfsPWpT` | singleLineText | Subscription identifier |
| **subscription_frequency** | `fld2vPBFDNx5X119j` | singleLineText | Frequency (monthly, etc.) |
| **subscription_frequency_interval** | `fldnKOkZKro37NdEz` | singleLineText | Interval value |
| **next_payment_date** | `fldthZh8Edn8G6pC8` | date | Next billing date |
| **is_subscription** | `fldDP1zWoSherJ71X` | formula | Whether this is a subscription payment |
| **billing_cycle** | `fldPbQHeca83T6K9x` | formula | Billing cycle calculation |
| **plan_length_months** | `fld0wfhAg8tvDlizA` | formula | Plan duration in months |

#### Transaction Type & Classification

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **Type** | `fldrnolhRqikz9yrG` | singleSelect | New Sub, One Time, Sub Renewal, Come Back |
| **Source** | `fldRLXysrBpqhjrUe` | singleSelect | WhatsApp, Amazon |
| **Payment Type** | `fld9Z19A390Nr13iC` | singleSelect | Mamo, WooCommerce |

#### Refill Management Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **Refill Date** | `fld0rL3errEyxOlAT` | number | Refill day of month |
| **Refill Status** | `fldPP6VJhIMp9Rfu1` | singleSelect | Paid, On Hold, Postponed, Cancelled, Early Refill |
| **Reason for churn** | `fldmi8WknmhiK0CFI` | singleSelect | Side Effects, Pricing, No Answer, Enough Supply, Moving to alternatives |
| **Notes and remarks** | `fldw1yADy7A6ivOEv` | multilineText | Refill notes |
| **Dr Rx** | `fldsUG2TpXPjiDr8I` | checkbox | Doctor prescription received |
| **Doctor** | `fldvQ0IYszfgrJsMi` | singleSelect | Dr Nameer, Dr Taleb, Dr Baraa, Dr Waqar, Dr Ranjith |
| **Sales Conversion** | `fldyc5qfVmyTaArWp` | checkbox | Converted to sale |

#### Refund Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **refund_amount** | `fldvpbeJ2ujmHo79y` | currency (AED) | Refund amount |
| **refund_status** | `fldhZDekZhLRlKzHw` | singleLineText | Refund status |

#### Error Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **error_code** | `fldI7ATTpiVxBkp0e` | singleLineText | Error code if failed |
| **error_message** | `fldaRW7oupiAFVpme` | singleLineText | Error message if failed |

#### Discount & Shipping Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **discount_total** | `fldolevjYfv5kDu4j` | singleLineText | Total discount |
| **discount_mamolink** | `flduKTjcPHQHyCCy7` | number | Discount on Mamo link |
| **delivery_mamolink** | `fldRz57m7nzYgrXWz` | number | Delivery charge on Mamo link |
| **discount_woocommerce** | `fldlX9THgVXFBjIeJ` | lookup | Discount from WooCommerce order |
| **woocommerce_shipping_total** | `fldki6PtoxeWAh0Bm` | lookup | Shipping from WooCommerce order |

#### Linked Fields

| Field Name | Field ID | Links To | Description |
|------------|----------|----------|-------------|
| **User** | `fldleBVUl3VYSlCRD` | User | Customer record |
| **Order_id** | `fld2OtWesPmiHgLmi` | woocommerce_orders | Associated WooCommerce order |
| **Product** | `fldCU9cqESTej8Hfb` | Product | Product purchased |
| **Campaign** | `fldXwSzfE1r0edqMa` | Campaign | Marketing campaign |

#### Lookup Fields from User

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **user_phone** | `fldQqMws16bmneEhr` | lookup | Phone from User |
| **client_manual_control (from User)** | `fldRXPYe504RegeWi` | lookup | Manual control flag |
| **First Order Date (from User)** | `fldfcvZGxVOtlEzaG` | lookup | User's first order date |
| **Last Order Date (from User)** | `fldFe3y9E4G75gGtA` | lookup | User's last order date |
| **Days Since Last Order (from User)** | `fldeiEfXdmGNFMeuA` | lookup | Days since last order |
| **Orders (from User)** | `fld4io1QcjGXhziR3` | lookup | All user orders |
| **Order Count (from User)** | `fld8gx0eUQSQaL7wV` | formula | Total order count |
| **User (from Order_id)** | `flds2M6THnsTS4SRK` | lookup | User via order link |
| **created_via_woocommerce** | `fldMHb3l680H96xYz` | lookup | Order creation method |

#### Lookup Fields from Product

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **product_id** | `fldbLkYiZnmxJAtgm` | lookup | Product ID |
| **Product Category** | `fldudF6mH5H0PMyVz` | lookup | Product category |
| **Product Display Name** | `fldy1W9zJTxqMOKqF` | lookup | Display name |
| **display_name (from Product)** | `fldj3Dr9SLdahCH09` | lookup | Product display name |
| **is_subscription (from Product)** | `fldR8A5KLql0kwtxe` | lookup | Is subscription product |
| **Subscription (from Product)** | `fldMgvoW6OnbVzaPs` | lookup | Subscription flag |
| **Sub_interval from product** | `fldcmZuTuKWTGKvtx` | lookup | Subscription interval |

#### Lookup Fields from Pharmacy (Magenta)

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **Invoice Attachment** | `fld8bvInAWxf0n9Cg` | lookup | Invoice file |
| **Invoice Number** | `fld2pzOujm2bK4iR9` | lookup | Invoice number |
| **RX #** | `fld7i2pd77CgI0rbc` | lookup | Prescription number |
| **MRN** | `fldrlw9nyTfhu9YRs` | lookup | Medical record number |
| **Pharmacy** | `fldlrQrrpWdzjmebe` | lookup | Pharmacy name |
| **Created date check** | `fld9nyixln7DgvJIU` | lookup | Magenta creation date |

#### Computed/Helper Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **link_key** | `fldvYG7JbkNxTTtLS` | formula | Link key for matching |
| **Month Order** | `fldLEhNQwxy3bw5aL` | formula | Month of order |
| **day** | `fldaHlboRpHhgOvPX` | formula | Day extraction |
| **Name_dashboard** | `fldWNDlJnhHADJKyt` | lookup | Dashboard display name |
| **types** | `fldKiYrTB8lZtyeQX` | checkbox | Type flag |
| **User copy** | `fldACAtBYLY9tC0li` | singleLineText | User copy field |
| **First Order Date** | `fldVeK7gyYq1ZZ3yY` | lookup | First order date |
| **Last Order Date** | `fld2eJsLehITJdcWY` | lookup | Last order date |

#### Status Values

| Status | Description |
|--------|-------------|
| `captured` | Payment successful |
| `failed` | Payment failed |
| `card_verified` | Card verification only |

#### Transaction Types

| Type | Description |
|------|-------------|
| New Sub | New subscription |
| One Time | One-time purchase |
| Sub Renewal | Subscription renewal |
| Come Back | Returning customer |

#### Refill Status Values

| Status | Description |
|--------|-------------|
| Paid | Refill paid |
| On Hold | Refill on hold |
| Postponed | Refill postponed |
| Cancelled | Refill cancelled |
| Early Refill | Early refill requested |

---

### Pharmacy Operations Table
**Table ID:** `tbl5MDz6ZRUosdsEQ`
**Primary Field:** `ID` (Formula: Sequential # + Status + Patient Name)
**Airtable Table Name:** `Magenta`

Tracks prescription fulfillment for POM (Prescription Only Medicine) products. Records are created monthly via the refilling process for active subscribers.

#### Key Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **ID** | `fldMK64X09I15D0Eu` | formula | Sequential # + Status + Patient Name |
| **Sequential Number** | `fldT8TG6FjTvbGD9N` | autoNumber | Auto-incrementing ID |
| **User** | `fldvN6axkYcNLCsyD` | link | Links to User table |
| **Status** | `fldQVkqiFV95jKLhF` | singleSelect | Workflow status (see below) |
| **Type of delivery** | `fld9dMmy3mMLQQdKM` | singleSelect | Refill / New Order |
| **Refill** | `fldFNXs5hbJIC7WCJ` | singleSelect | Yes / No |
| **Trigger by** | `fldNw5tfyBu2fWDPH` | singleSelect | MAMO / WOO |
| **Invoice Number** | `fldWvyOyfFNS2415I` | singleLineText | Pharmacy invoice # |
| **Invoice Attachment** | `fldWk9rvJaAFwfRvl` | attachment | Scanned invoice PDF |
| **Pharmacy** | `fldwCKkYvzRnDqnrD` | singleSelect | Magenta / Revitalife |
| **Date** | `fldFVZNGXfLRLNMAz` | date | Refill/order date |
| **Refill Status** | `fldJbzwoZWvxD9Xoh` | singleSelect | Payment status |
| **Reason** | `fld4NBTU5rH1CbgBp` | singleSelect | Cancellation reason |
| **email_input** | `fldXAzw7qF4qR34A6` | singleLineText | Email for refill process |

#### Patient Information Fields (AI Extracted)

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **Patient Name** | `flddJ9e67308f8gay` | AI Text | Extracted from RX attachment |
| **MRN** | `fldzF1knoHzGTVoBr` | AI Text | Medical Record Number |
| **Product** | `fldB3owGtSuFfWtUq` | AI Text | Prescription product |
| **Email** | `fld5hyokxBePDdX5d` | AI Text | Customer email |
| **Phone Number** | `fldRKVrkBP0ET11Nn` | AI Text | Customer phone |
| **RX #** | `fldMx6Lh9FbWbMC1q` | singleLineText | Prescription number |
| **RX Attachment** | `fldijtS9MMwEDr87Q` | attachment | Prescription file |

#### Status Workflow

```
✅ RX Received → 🧪 In Compounding → 🧴 Ready for Dispatch → 🚚 Out for Delivery → 📦 Delivered
                                                                      ↓
                                                            1st Delivery Attempt
```

| Status | Description |
|--------|-------------|
| ✅ RX Received | Prescription received from doctor |
| 🧪 In Compounding | Pharmacy preparing medication |
| 🧴 Ready for Dispatch | Ready for courier pickup |
| 🚚 Out for Delivery | With delivery courier |
| 1st Delivery Attempt | First delivery attempted |
| 📦 Delivered | Successfully delivered |

#### TAT (Turnaround Time) Timestamps

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **rx_received_at** | (varies) | dateTime | When RX was received |
| **compounding_started_at** | (varies) | dateTime | When compounding started |
| **ready_for_dispatch_at** | (varies) | dateTime | When ready for dispatch |
| **out_for_delivery_at** | (varies) | dateTime | When handed to courier |
| **first_delivery_attempt_at** | (varies) | dateTime | First delivery attempt |
| **delivered_at** | (varies) | dateTime | Successful delivery time |

#### Linked Fields

| Field Name | Field ID | Links To | Description |
|------------|----------|----------|-------------|
| **User** | `fldvN6axkYcNLCsyD` | User | Customer record |

---

### Subscriptions Table
**Table ID:** `tblf0AONAdsaBwo8P`
**Primary Field:** `id`

Tracks active subscriptions from both MamoPay and WooCommerce. Created monthly via refilling process.

#### Key Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **id** | (auto) | singleLineText | MamoPay subscriber ID or WooCommerce subscription ID |
| **customer_email** | (varies) | singleLineText | Subscriber email |
| **customer_name** | (varies) | singleLineText | Subscriber name |
| **next_payment_date** | (varies) | date | Next billing date |
| **status** | (varies) | singleLineText | active, cancelled, etc. |
| **Trigger by** | (varies) | singleSelect | MAMO / WOO |
| **User** | (varies) | link | Links to User table |

---

### instapract Table (Quiz Completions)
**Table ID:** `tbleLSKMeFP1LF5hT`
**Primary Field:** `Patient Name`

Quiz completions from the Instapract platform. Used for lead generation and quiz dropper campaigns.

#### Core Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **Patient Name** | `fldnABTluU4tDGXxP` | multilineText | **PRIMARY KEY** - Patient's full name |
| **first_name** | `fldkfgPaUuq3NIE54` | formula | Extracted first name |
| **Email** | `fldUGXOufJC3DcQQ4` | multilineText | Quiz email address |
| **Phone Number** | `fldaZXw7eXhsXh6U2` | number | Phone (may have .0 suffix) |
| **phone_number** | `fldEHmZ1H0Fs7bHtk` | formula | Cleaned phone number |
| **MRN** | `fldlPbG3v4w9vZwXs` | multilineText | Medical Record Number |
| **Date** | `fld1M4lIVfay2egTe` | date | Quiz completion date |
| **Created** | `fldcOtpjCxpBjuWtw` | createdTime | Record creation timestamp |
| **Last Modified** | `fldxBrcQMN5Xzvs4s` | lastModifiedTime | Last update timestamp |

#### Quiz Information

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **Quiz Type** | `fldbIx5eT5cdVNFAb` | singleSelect | Hair Loss, Sexual Health, Beard growth |
| **Quiz Result** | `fldMb7Piat1fhwVGG` | singleSelect | critical, moderate, severe, Mild ED, Severe ED |
| **quiz_url** | `fldPaE7lkO2WhQCAB` | singleSelect | URL slug (critical-hair-loss/, moderate-ed/, etc.) |
| **Product Link** | `fld4p9oRBupl4LoMD` | formula | Full product recommendation URL |
| **Calculation** | `flddcsCxHuJUF3oMg` | formula | Quiz score calculation |

#### Quiz Types

| Type | Description |
|------|-------------|
| Hair Loss | Hair loss assessment quiz |
| Sexual Health | ED/sexual health quiz |
| Beard growth | Beard growth quiz |

#### Quiz Results

| Result | Quiz Type | Description |
|--------|-----------|-------------|
| critical | Hair Loss | Critical hair loss stage |
| severe | Hair Loss | Severe hair loss |
| moderate | Hair Loss | Moderate hair loss |
| Mild ED | Sexual Health | Mild erectile dysfunction |
| Severe ED | Sexual Health | Severe erectile dysfunction |

#### Lead Management Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **Status** | `fldK2XsMLFSpZEkzq` | singleSelect | New, Contacted – Interested, Contacted – Thinking, Contacted – Not Interested, No Answer |
| **Sub Status** | `fldz9P9OuwC1B01Zy` | singleSelect | Busy, Call back later, Pricing, Travelling, Cut the call |
| **Owner** | `fldDlm0NBqfinrBSc` | singleCollaborator | Assigned sales rep |
| **Last Contact Date** | `fldJ3VSQz0v26CGvW` | date | Last contact attempt |
| **Lost Reason** | `fld6yISR5E5DZzluz` | singleLineText | Why lead was lost |
| **Notes** | `fldI4I1MeG9sSWQO2` | singleLineText | Sales notes |
| **Doctor Name** | `fldkmRqQ4BsOfHoZH` | singleLineText | Assigned doctor |

#### Tags & Source

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **Tags** | `fldE0gJEJ1FzXIixc` | multipleSelects | Pricing, Already using another treatment, Afraid of side effects, etc. |
| **Source** | `fldaQvoI0E2rQVubS` | singleSelect | Insta, Facebook, Organic, Tiktok, Google |

#### Linked Fields & Lookups

| Field Name | Field ID | Links To | Description |
|------------|----------|----------|-------------|
| **User** | `fldbmCoeaaDUFizi3` | User | Linked customer record |
| **never_ordered** | `fldcMtcI9xvZ5vt76` | lookup | From User - TRUE if no orders |
| **client_manual_control (from User)** | `fldGlfVQ0OBlTcQxB` | lookup | Manual control flag |
| **unsubscribed_whattsapp (from User)** | `fld1fKWPanTaLyK55` | lookup | WhatsApp opt-out status |

#### Automation Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **date_trigger** | `fld9dWWysOJ88JZLr` | dateTime | Automation trigger timestamp |
| **Hours Since Date Trigger** | `fldYmsF3PHNPQqKo2` | formula | Hours elapsed since trigger |
| **Is Noon?** | `fldqUZHHEHvMVBaGf` | formula | Check if current time is noon |
| **whatsapp_click** | `fldDNalH9kMpQSWeq` | formula | WhatsApp click tracking |
| **Quiz Conversion Status** | `fldAqdU18F6O6x2qe` | formula | Conversion status calculation |

---

### Product Table
**Table ID:** `tblsU18ZUEMiirxJl`
**Primary Field:** `Name`

Products from WooCommerce catalog.

#### Key Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **Name** | `fldYMqR5cL2pK8wXz` | singleLineText | **PRIMARY KEY** - Product name |
| **ID** | `fld9Xp2kL5mYqR8wz` | number | WooCommerce product ID |
| **ID_Key** | `fldFPe6NstD8K82jf` | formula | Lookup key for matching (uses product ID) |
| **display_name** | `fldWx5kL2pY9qR8mz` | singleLineText | Display name for UI |
| **sku** | `fldKp2x5L9mYwR8qz` | singleLineText | Product SKU |
| **price** | `fld5Lp2kY9mXwR8qz` | currency (AED) | Product price |
| **Category** | `fldMp2x5L9kYwR8qz` | singleSelect | Product category |
| **Subscription** | `fldNp2x5L9mYkR8qz` | checkbox | Is subscription product |

#### Product Categories

| Category | Description |
|----------|-------------|
| POM BG | Prescription - Blood Glucose |
| POM HL | Prescription - Hair Loss |
| OTC HL | Over-the-counter - Hair Loss |
| OTC SK | Over-the-counter - Skin |
| POM SH | Prescription - Sexual Health |
| OTC SH | Over-the-counter - Sexual Health |

#### Linked Fields

| Field Name | Links To | Description |
|------------|----------|-------------|
| Orders Line Items | Orders Line Items | Line items containing this product |
| Mamo Transactions | Mamo Transactions | Mamo payments for this product |

---

### Orders Line Items Table
**Table ID:** `tblWhfPh6YPk43Wf6`
**Primary Field:** `Name`

Individual line items within orders.

#### Key Fields

| Field Name | Field ID | Type | Description |
|------------|----------|------|-------------|
| **Name** | `fldRp2x5L9mYwK8qz` | singleLineText | **PRIMARY KEY** - Auto-generated name |
| **Product** | `fld4RDdD2NIQMISsj` | singleLineText | Product name/description |
| **quantity** | `fldSp2x5L9mYwR8qz` | number | Quantity ordered |
| **total** | `fldTp2x5L9mYwR8qz` | currency (AED) | Line item total |
| **subtotal** | `fldUp2x5L9mYwR8qz` | currency (AED) | Line item subtotal |

#### Linked Fields

| Field Name | Field ID | Links To | Description |
|------------|----------|----------|-------------|
| **order_id** | `fldsoghSFgGcUY72f` | woocommerce_orders | Parent order |
| **ID_Key** | `fldFPe6NstD8K82jf` | Product | Product record (via ID lookup) |

---

## Key Field Mappings

### WooCommerce to Airtable

| WooCommerce Field | Airtable Table | Airtable Field |
|-------------------|----------------|----------------|
| order.id | woocommerce_orders | id |
| order.customer_id | woocommerce_orders | customer_id |
| order.customer_id | User | source_user_id |
| order.status | woocommerce_orders | status |
| order.total | woocommerce_orders | total |
| customer.id | User | source_user_id |
| customer.email | User | user_email |
| product.id | Product | ID |
| line_item.product_id | Orders Line Items | ID_Key (link) |

### Mamo to Airtable

| Mamo Field | Airtable Table | Airtable Field |
|------------|----------------|----------------|
| payment.id | Mamo Transactions | id |
| payment.status | Mamo Transactions | status |
| payment.amount | Mamo Transactions | amount |
| sender.email | Mamo Transactions | senderEmail |
| sender.name | Mamo Transactions | senderName |
| sender.mobile | Mamo Transactions | senderMobile |

---

## Data Sources

### WooCommerce API
- **Base URL:** `https://aneeq.co/wp-json/wc/v3/`
- **Authentication:** HTTP Basic Auth
- **Endpoints:**
  - `/orders` - Order data
  - `/customers` - Customer data
  - `/products` - Product catalog

### Mamo API
- Webhook-based data ingestion
- Payment link integrations

---

## Common Data Issues

### 1. Duplicate Users
**Problem:** Same email with multiple User records
**Cause:** Multiple import sources, legacy data
**Solution:** Keep record with numeric source_user_id (WooCommerce), merge Mamo transactions, delete duplicates

### 2. Missing User Links on Mamo Transactions
**Problem:** Mamo transaction without User link
**Resolution Path:**
1. Check if Order linked → get customer_id → find User by source_user_id
2. Match by senderEmail → find User by user_email
3. Match by senderMobile → find User by phone
4. Create new User with `mamo_` prefix

### 3. Amazon Orders
**Problem:** Amazon doesn't share real customer data
**Indicators:**
- Source = "Amazon"
- customer_details_* = "amazon"
- Cannot link to real User records

### 4. Order Status Sync
**Problem:** Airtable status doesn't match WooCommerce
**Solution:** Periodic sync using WooCommerce API to update status field

### 5. Invoice Correlation Issue
**Problem:** Mamo Transactions show wrong Invoice Number from Pharmacy Operations

**Root Cause:**
The User table has lookup fields from Pharmacy Operations (Magenta) with a **"show latest"** filter. When Mamo Transactions display these via the User link, they show the most recent Pharmacy Operations record—not the one matching the current payment.

**Data Flow (Problematic):**
```
Mamo Transaction → User → Pharmacy Operations (latest) → Invoice Number
                                    ↓
                    Shows WRONG invoice if current month not yet updated
```

**Affected Fields on User table:**
- `Magenta` (fldVzNVxFLd8j18Pq) - Link field
- `MRN (from Magenta)` (fldzxPYjI5r5MEqF2) - Lookup
- `RX # (from Magenta)` (fldVpPuArmIuJIzkJ) - Lookup
- `Invoice Number (from Magenta)` (fld2EEswPGgnNZkfz) - Lookup
- `Created (from Magenta)` (fldUdS8mrcx18tq2B) - Lookup

**Scenario:**
1. Customer has February Pharmacy Operations record with Invoice #FEB-001
2. March refilling process runs, creates Mamo payment
3. Pharmacy hasn't updated March Pharmacy Operations record yet
4. Mamo Transaction displays Invoice #FEB-001 (wrong - previous month)

**Note:** This is a data architecture limitation in Airtable's lookup behavior, not a bug. The lookup always shows the "latest" linked record, regardless of which Mamo Transaction is being viewed.

---

## API Credentials

All credentials are stored in the `.env` file at the project root (gitignored).

| Variable | Service |
|----------|---------|
| `AIRTABLE_TOKEN` | Airtable API |
| `AIRTABLE_BASE_ID` | Airtable Base |
| `WC_CONSUMER_KEY` | WooCommerce |
| `WC_CONSUMER_SECRET` | WooCommerce |
| `MAMO_API_KEY` | MamoPay |
| `SENDGRID_API_KEY` | SendGrid |

---

## Table IDs Quick Reference

| Table Name | Table ID | Primary Key |
|------------|----------|-------------|
| woocommerce_orders | `tblWByCCtBE1dR6ox` | id (order ID) |
| User | `tblMtIskMF3X3nKWC` | source_user_id |
| Mamo Transactions | `tbl7WfjTqWMnsqpbs` | id (payment ID) |
| Pharmacy Operations (Magenta) | `tbl5MDz6ZRUosdsEQ` | ID (formula) |
| Subscriptions | `tblf0AONAdsaBwo8P` | id |
| instapract | `tbleLSKMeFP1LF5hT` | Patient Name (quiz completions) |
| Product | `tblsU18ZUEMiirxJl` | Name |
| Orders Line Items | `tblWhfPh6YPk43Wf6` | Name |
