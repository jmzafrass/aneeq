#!/usr/bin/env python3 -u
"""
Execute quiz dropper email campaign - no confirmation required.
Run with: python3 -u scripts/email/run_campaign.py
"""

import sys
import os

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
import time
from collections import Counter
from dotenv import load_dotenv

from segmentation.quiz_droppers import (
    fetch_all_records,
    build_converter_sets,
    build_unsub_sets,
    filter_quiz_droppers,
    deduplicate_droppers,
    normalize_email,
    normalize_phone_for_matching,
    INSTAPRACT_TABLE,
    MAMO_TABLE,
    ORDERS_TABLE,
    USER_TABLE,
)

load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
TEMPLATE_ID = 'd-29a008d0f0f14bec9b320185096ba547'
FROM_EMAIL = 'care@aneeq.co'
FROM_NAME = 'aneeq'
UNSUBSCRIBE_GROUP_ID = 229902


def send_email(email, first_name, cta_url):
    payload = {
        'from': {'email': FROM_EMAIL, 'name': FROM_NAME},
        'personalizations': [{
            'to': [{'email': email}],
            'dynamic_template_data': {
                'first_name': first_name,
                'cta_url': cta_url
            }
        }],
        'template_id': TEMPLATE_ID,
        'asm': {'group_id': UNSUBSCRIBE_GROUP_ID}
    }
    response = requests.post(
        'https://api.sendgrid.com/v3/mail/send',
        headers={
            'Authorization': f'Bearer {SENDGRID_API_KEY}',
            'Content-Type': 'application/json'
        },
        json=payload
    )
    return response.ok, response.text[:100] if not response.ok else 'SENT'


def main():
    print('=' * 60)
    print('QUIZ DROPPER EMAIL CAMPAIGN - EXECUTING')
    print('=' * 60)
    print()

    # Fetch all data
    print('Fetching data from Airtable...')
    quiz_fields = ['Email', 'Phone Number', 'Date', 'Product Link', 'Quiz Type', 'first_name',
                   'User', 'never_ordered', 'unsubscribed_whattsapp (from User)']
    quiz_records = fetch_all_records(INSTAPRACT_TABLE, fields=quiz_fields)
    print(f'  Quiz records: {len(quiz_records):,}')

    mamo_records = fetch_all_records(MAMO_TABLE,
                                      fields=['customer_details_email', 'customer_details_phone_number', 'status'],
                                      filter_formula="{status}='captured'")
    print(f'  Mamo captured: {len(mamo_records):,}')

    woo_orders = fetch_all_records(ORDERS_TABLE,
                                    fields=['Email (Billing)', 'Phone (Billing)', 'status'],
                                    filter_formula="OR({status}='completed',{status}='processing')")
    print(f'  WooCommerce orders: {len(woo_orders):,}')

    unsub_users = fetch_all_records(USER_TABLE,
                                     fields=['user_email', 'phone_standarised', 'billing_phone', 'unsubscribed_whattsapp'],
                                     filter_formula='{unsubscribed_whattsapp}=TRUE()')
    print(f'  Unsubscribed users: {len(unsub_users):,}')

    antoine_users = fetch_all_records(USER_TABLE,
                                       fields=['user_email', 'phone_standarised', 'billing_phone'],
                                       filter_formula='{is_customer_antoine}=TRUE()')
    print(f'  Antoine customers: {len(antoine_users):,}')

    # Build exclusion sets
    print('\nBuilding exclusion sets...')
    converter_emails, converter_phones = build_converter_sets(mamo_records, woo_orders)

    for u in antoine_users:
        f = u.get('fields', {})
        email = normalize_email(f.get('user_email'))
        if email:
            converter_emails.add(email)
        for phone in [f.get('phone_standarised'), f.get('billing_phone')]:
            norm_phone = normalize_phone_for_matching(phone)
            if norm_phone:
                converter_phones.add(norm_phone)

    print(f'  Converter emails: {len(converter_emails):,}')
    print(f'  Converter phones: {len(converter_phones):,}')

    unsub_emails, unsub_phones = build_unsub_sets(unsub_users)
    print(f'  Unsub emails: {len(unsub_emails):,}')
    print(f'  Unsub phones: {len(unsub_phones):,}')

    # Filter
    print('\nFiltering quiz records...')
    droppers, _ = filter_quiz_droppers(quiz_records, converter_emails, converter_phones,
                                        unsub_emails, unsub_phones, None)
    unique_droppers, _ = deduplicate_droppers(droppers)
    print(f'  Unique droppers: {len(unique_droppers):,}')

    # Build email list
    print('\nBuilding email list...')
    email_droppers = []
    for d in unique_droppers:
        email = d.get('email')
        product_link = None
        for q in quiz_records:
            if q['id'] == d.get('record_id'):
                product_link = q.get('fields', {}).get('Product Link')
                break
        if email and product_link:
            email_droppers.append({
                'email': email,
                'first_name': (d.get('fname') or '').split()[0] if d.get('fname') else 'there',
                'cta_url': product_link,
            })

    print(f'  Final email droppers: {len(email_droppers):,}')

    # Category breakdown
    print('\n=== BY CATEGORY ===')
    quiz_type_map = {}
    for d in unique_droppers:
        for q in quiz_records:
            if q['id'] == d.get('record_id'):
                qt = q.get('fields', {}).get('Quiz Type') or 'Unknown'
                quiz_type_map[d.get('email')] = qt
                break

    category_counts = Counter(quiz_type_map.get(d['email'], 'Unknown') for d in email_droppers)
    for cat, count in category_counts.most_common():
        print(f'  {cat}: {count}')

    print(f'\n=== SENDING {len(email_droppers):,} EMAILS ===')

    success = 0
    failed = 0

    for i, d in enumerate(email_droppers):
        ok, msg = send_email(d['email'], d['first_name'], d['cta_url'])

        if ok:
            success += 1
            status = '✓'
        else:
            failed += 1
            status = f'✗ {msg}'

        print(f'  [{i+1}/{len(email_droppers)}] {d["email"][:40]:40} {status}')

        # Rate limiting - pause 1 sec every 50 emails (safe for SendGrid 100/sec limit)
        if (i + 1) % 50 == 0:
            print(f'    [Rate limit pause - 1 sec...]')
            time.sleep(1)

    print()
    print('=' * 60)
    print('SUMMARY')
    print('=' * 60)
    print(f'  Total: {len(email_droppers):,}')
    print(f'  Success: {success:,}')
    print(f'  Failed: {failed:,}')


if __name__ == '__main__':
    main()
