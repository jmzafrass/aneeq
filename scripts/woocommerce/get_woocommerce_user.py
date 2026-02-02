import requests
from requests.auth import HTTPBasicAuth
import csv
import json
from datetime import datetime
import urllib3
import os
from dotenv import load_dotenv
load_dotenv()

# Disable SSL warnings if needed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API credentials - use your WooCommerce credentials
consumer_key = os.getenv("WC_CONSUMER_KEY")
consumer_secret = os.getenv("WC_CONSUMER_SECRET")


# WooCommerce Customers API endpoint
base_url = 'https://aneeq.co/wp-json/wc/v3/customers'

# Try alternate endpoint if needed
# base_url = 'https://aneeq.co/wp-json/wp/v2/users'  # WordPress users endpoint (might have more users)

def fetch_all_woocommerce_users():
    """Fetch all WooCommerce users with specific fields."""
    all_users = []
    page = 1
    total_pages = None
    total_users = None
    
    print("🔍 Fetching all WooCommerce users...")
    print("=" * 50)
    
    while True:
        params = {
            'per_page': 100,
            'page': page,
            'orderby': 'registered_date',
            'order': 'asc',
            'role': 'all',  # Fetch all user roles
            'context': 'view'  # Ensure we get all viewable data
        }
        
        print(f"📄 Fetching page {page}...")
        
        try:
            response = requests.get(
                base_url, 
                auth=HTTPBasicAuth(consumer_key, consumer_secret), 
                params=params,
                verify=False  # Disable SSL verification due to SSL issues
            )
            response.raise_for_status()
            
            # Check pagination headers
            if page == 1:
                total_pages = response.headers.get('X-WP-TotalPages')
                total_users = response.headers.get('X-WP-Total')
                if total_pages:
                    print(f"📊 Total pages available: {total_pages}")
                if total_users:
                    print(f"👥 Total users in database: {total_users}")
            
            # Debug: Print response headers
            print(f"  Headers: Total={response.headers.get('X-WP-Total')}, TotalPages={response.headers.get('X-WP-TotalPages')}, Current Page={page}")
            
            users = response.json()
            
            # Check if we've reached the end
            if not users:
                print(f"  ⚠️  No users returned on page {page}")
                # Check if we should continue based on headers
                if total_pages and page <= int(total_pages):
                    print(f"  🔄 Continuing despite empty response (page {page}/{total_pages})")
                    page += 1
                    continue
                else:
                    break
            
            # Process each user and extract required fields
            for user in users:
                billing = user.get('billing', {})
                shipping = user.get('shipping', {})

                user_data = {
                    'source_user_id': user.get('id'),
                    'user_email': user.get('email', ''),
                    'user_registered': user.get('date_created', ''),
                    'user_login': user.get('username', ''),
                    'phone_number': '',  # Will be populated from billing if available
                    'last_name': user.get('last_name', ''),
                    'first_name': user.get('first_name', ''),
                    'date_created': user.get('date_created', ''),

                    # Billing information
                    'billing_email': billing.get('email', ''),
                    'billing_first_name': billing.get('first_name', ''),
                    'billing_last_name': billing.get('last_name', ''),
                    'billing_phone': billing.get('phone', ''),
                    'billing_city': billing.get('city', ''),
                    'billing_country': billing.get('country', ''),
                    'billing_postcode': billing.get('postcode', ''),
                    'billing_state': billing.get('state', ''),
                    'billing_address_1': billing.get('address_1', ''),
                    'billing_address_2': billing.get('address_2', ''),

                    # Shipping information
                    'shipping_first_name': shipping.get('first_name', ''),
                    'shipping_last_name': shipping.get('last_name', ''),
                    'shipping_phone': shipping.get('phone', ''),
                    'shipping_city': shipping.get('city', ''),
                    'shipping_country': shipping.get('country', ''),
                    'shipping_postcode': shipping.get('postcode', ''),
                    'shipping_state': shipping.get('state', ''),
                    'shipping_address_1': shipping.get('address_1', ''),
                    'shipping_address_2': shipping.get('address_2', '')
                }

                # Use billing phone as phone_number if available
                if user_data['billing_phone']:
                    user_data['phone_number'] = user_data['billing_phone']

                all_users.append(user_data)
            
            print(f"  ✅ Retrieved {len(users)} users (Total so far: {len(all_users)}")
            
            # Check if we've reached the last page based on headers
            if total_pages and page >= int(total_pages):
                print(f"  📍 Reached last page ({page}/{total_pages})")
                break
            
            page += 1
            
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
            print(f"   Response Status: {e.response.status_code if e.response else 'No response'}")
            print(f"   Response: {e.response.text[:500] if e.response else 'No response'}...")  # First 500 chars
            
            # If we get a 400 error, it might be because we're past the last page
            if e.response and e.response.status_code == 400:
                print("  ℹ️  Received 400 error - may have exceeded available pages")
                if all_users:
                    print(f"  ✅ Continuing with {len(all_users)} users fetched so far")
                    break
            else:
                break
        except Exception as e:
            print(f"❌ Error: {e}")
            break
    
    print("=" * 50)
    print(f"✅ Total users fetched: {len(all_users)}")
    
    return all_users

def save_to_csv(users, filename='woocommerce_users.csv'):
    """Save users data to CSV file."""
    if not users:
        print("⚠️  No users to save")
        return
    
    fieldnames = [
        'source_user_id', 'user_email', 'user_registered', 'user_login',
        'phone_number', 'last_name', 'first_name', 'date_created',
        'billing_email', 'billing_first_name', 'billing_last_name',
        'billing_phone', 'billing_city', 'billing_country', 'billing_postcode',
        'billing_state', 'billing_address_1', 'billing_address_2',
        'shipping_first_name', 'shipping_last_name', 'shipping_phone',
        'shipping_city', 'shipping_country', 'shipping_postcode',
        'shipping_state', 'shipping_address_1', 'shipping_address_2'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(users)
    
    print(f"📁 Data saved to {filename}")

def save_to_json(users, filename='woocommerce_users.json'):
    """Save users data to JSON file."""
    if not users:
        print("⚠️  No users to save")
        return
    
    with open(filename, 'w', encoding='utf-8') as jsonfile:
        json.dump(users, jsonfile, indent=2, ensure_ascii=False)
    
    print(f"📁 Data saved to {filename}")

def print_summary(users):
    """Print summary statistics about the fetched users."""
    if not users:
        return
    
    print("\n📊 USER DATA SUMMARY")
    print("=" * 50)
    print(f"Total users: {len(users)}")
    
    # Count users with billing information
    users_with_billing = sum(1 for u in users if u.get('billing_email'))
    print(f"Users with billing info: {users_with_billing}")
    
    # Count users with phone numbers
    users_with_phone = sum(1 for u in users if u.get('billing_phone'))
    print(f"Users with phone numbers: {users_with_phone}")
    
    # Count users with addresses
    users_with_address = sum(1 for u in users if u.get('billing_address_1'))
    print(f"Users with addresses: {users_with_address}")
    
    # Show sample data
    if users:
        print("\n📋 Sample user data (first 3 users):")
        for i, user in enumerate(users[:3], 1):
            print(f"\nUser {i}:")
            print(f"  ID: {user.get('source_user_id')}")
            print(f"  Email: {user.get('user_email')}")
            print(f"  Name: {user.get('first_name')} {user.get('last_name')}")
            print(f"  Registered: {user.get('user_registered')}")

def main():
    """Main function to execute the user fetching process."""
    print("\n🚀 WooCommerce User Fetcher")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: https://aneeq.co")
    print("=" * 50)
    
    # Fetch all users
    users = fetch_all_woocommerce_users()
    
    if users:
        # Save to both CSV and JSON
        save_to_csv(users)
        save_to_json(users)
        
        # Print summary
        print_summary(users)
        
        print("\n✅ Process completed successfully!")
    else:
        print("\n⚠️  No users were fetched. Please check your API credentials and endpoint.")

if __name__ == "__main__":
    main()