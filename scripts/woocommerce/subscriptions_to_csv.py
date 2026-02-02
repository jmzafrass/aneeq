import json
import csv
from datetime import datetime

def extract_meta_value(meta_data, key):
    """Extract value from meta_data array by key"""
    for item in meta_data:
        if item.get('key') == key:
            return item.get('value', '')
    return ''

def extract_line_items(line_items):
    """Extract line items as a formatted string"""
    items = []
    for item in line_items:
        items.append(f"{item.get('name', '')} (ID:{item.get('product_id', '')}, Var:{item.get('variation_id', '')}, Qty:{item.get('quantity', '')}, Price:{item.get('price', '')})")
    return ' | '.join(items)

def json_to_csv(json_file, csv_file):
    # Read JSON data
    with open(json_file, 'r') as f:
        subscriptions = json.load(f)
    
    # Define CSV headers
    headers = [
        # Record IDs
        'subscription_id',
        'parent_id',
        'number',
        
        # Account
        'customer_id',
        
        # Lifecycle status
        'status',
        
        # Timestamps (UTC)
        'date_created_gmt',
        'date_paid_gmt',
        'last_payment_date_gmt',
        'next_payment_date_gmt',
        'end_date_gmt',
        
        # Payment rails
        'payment_method',
        'payment_method_title',
        
        # Order → Mamopay handshake
        'order_key',
        
        # Mamopay tokens & links
        'mamopay_ws_payment_token',
        'mamo_pay_payment_link_id',
        'mamo_pay_payment_link_type',
        'mamo_pay_payment_url',
        'mamo_pay_order_total_hash',
        
        # Financials
        'currency',
        'total',
        'shipping_total',
        'discount_total',
        
        # Item details
        'line_items',
        
        # Additional useful fields
        'billing_email',
        'billing_name',
        'billing_phone'
    ]
    
    # Write CSV
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        
        for sub in subscriptions:
            row = {
                # Record IDs
                'subscription_id': sub.get('id', ''),
                'parent_id': sub.get('parent_id', ''),
                'number': sub.get('number', ''),
                
                # Account
                'customer_id': sub.get('customer_id', ''),
                
                # Lifecycle status
                'status': sub.get('status', ''),
                
                # Timestamps
                'date_created_gmt': sub.get('date_created_gmt', ''),
                'date_paid_gmt': sub.get('date_paid_gmt', ''),
                'last_payment_date_gmt': sub.get('last_payment_date_gmt', ''),
                'next_payment_date_gmt': sub.get('next_payment_date_gmt', ''),
                'end_date_gmt': sub.get('end_date_gmt', ''),
                
                # Payment rails
                'payment_method': sub.get('payment_method', ''),
                'payment_method_title': sub.get('payment_method_title', ''),
                
                # Order key
                'order_key': sub.get('order_key', ''),
                
                # Extract Mamopay fields from meta_data
                'mamopay_ws_payment_token': extract_meta_value(sub.get('meta_data', []), '_mamopay_ws_payment_token'),
                'mamo_pay_payment_link_id': extract_meta_value(sub.get('meta_data', []), '_mamo_pay_payment_link_id'),
                'mamo_pay_payment_link_type': extract_meta_value(sub.get('meta_data', []), '_mamo_pay_payment_link_type'),
                'mamo_pay_payment_url': extract_meta_value(sub.get('meta_data', []), '_mamo_pay_payment_url'),
                'mamo_pay_order_total_hash': extract_meta_value(sub.get('meta_data', []), '_mamo_pay_order_total_hash'),
                
                # Financials
                'currency': sub.get('currency', ''),
                'total': sub.get('total', ''),
                'shipping_total': sub.get('shipping_total', ''),
                'discount_total': sub.get('discount_total', ''),
                
                # Line items
                'line_items': extract_line_items(sub.get('line_items', [])),
                
                # Additional fields from billing
                'billing_email': sub.get('billing', {}).get('email', ''),
                'billing_name': f"{sub.get('billing', {}).get('first_name', '')} {sub.get('billing', {}).get('last_name', '')}".strip(),
                'billing_phone': sub.get('billing', {}).get('phone', '')
            }
            writer.writerow(row)
    
    print(f"CSV file created: {csv_file}")
    print(f"Total subscriptions exported: {len(subscriptions)}")

if __name__ == '__main__':
    json_to_csv('subscriptions_this_month.json', 'subscriptions_mamopay_reconciliation.csv')