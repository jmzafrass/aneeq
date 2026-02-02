import requests
from datetime import datetime
import time
import json
import os

# CONFIGURATION
API_TOKEN = 'ZORCDCwIpC8YSlP87bjlTPT8wEcjnDyFaUJcpJu6jvw'
BUDGET_ID = 'c1a749b1-eb03-4b6e-9349-727b4ab788c3'
CONVERSION_RATE = 4.32  

# Updated to start from November since October is already processed
START_MONTH = '2024-11-01'

# State file to track progress
STATE_FILE = 'ynab_conversion_state.json'

# Extended skip list with October 2024 transactions
SKIP_TXN_IDS = [
    # Original skip list
    "9ba87182-613b-4401-b3d7-c6ac25bb715d",
    "3192446d-45c1-4a3d-bfe7-b6590ee848c7",
    "043248fa-a9d6-447c-8e3b-3d53757e4a2c",
    "d3ff2c9c-f11a-4299-a0a3-cb1c1726e978",
    "2a8defb0-6391-47d3-9ab5-a1f4333bbf6f",
    "025d7375-16cf-4c7b-a54f-c2eada8f1717",
    "6b63e140-a8dd-4e8b-a1f9-c8039e21e24a",
    "ebc39f00-3529-431d-8021-ca3dfe6e82a7",
    "938b060a-73a4-45d9-a8ef-23ae6edec5e4",
    "2166e2b5-1bbd-44d5-9a3a-1eacafef07a6",
    "8d3be4f7-b4a3-486c-988a-141e38ea8996",
    "1e64aea1-ca09-4f8a-9ced-af6b6d648c73_2024-08-01",
    "f97d66a3-9580-47fb-bee1-360264600d40",
    "a4588f44-fe35-444a-86dd-f69570fd9376",
    "90ae6d46-42ca-4765-9040-36fbf6b108c1",
    "ac8bd1d7-c9e5-42d0-9a0b-c833558a5f68",
    "e93f758b-5f5f-4423-bd0a-63bbaa4e85ce",
    "1432601f-0ad8-46e6-b0f5-3a09f7f4a268",
    "372eff99-0e94-45b7-b9c8-07f696072196",
    "dccbd171-e25d-4f3f-ac31-fdd2ebeb6db2",
    "0ab0be21-5501-4f3d-a9a6-9809f9bc3d67",
    "85847010-db6d-4783-a507-36ac8614a506",
    "3b9b2d07-5f96-4c83-bc46-e38e717e0523",
    "2fb95719-2323-45e7-8561-9ae3776d144e",
    "fc6b6e2f-ffcb-4abe-be99-29d3df0b4eca",
    "2d0b3416-24cd-4124-9752-4355a85b37f9",
    "be4c405b-7365-4760-8fb8-d6965ea61939",
    "ba6e12ee-2179-4ede-b604-3e282685758e",
    "564a3646-8466-464f-a78e-1251066d5e42",
    "3c0f9da3-5add-4133-9629-967b0a12534d",
    "4d89e157-f050-424e-8b32-e0ca6b04739f",
    "77f4aae1-978e-419f-b9ac-3559f77b889e",
    "70177bb3-7ad5-427a-aa7b-5b11a83a863d",
    "cc0d28ac-3a1e-4bb9-a6b2-152dd21cb547",
    "48d06b78-f0c3-4b65-8196-ed0dc75857b5",
    "c0448a32-f738-4c55-9e41-e8d7d10b5e09",
    "16931e80-9697-4fb4-b72c-5869131dbc95",
    "f0e71b00-913a-4768-b1b8-7c95d8c6bc0b",
    "31c6fc63-cb0d-4b07-a5c5-bd02f1a35b9d",
    "fa871d8e-53e7-4326-80d7-72f4e5b0987c",
    "6cd5e8f5-ccc5-4c88-92b4-4735a3200e8f",
    "aa1f27b4-fdff-4484-8c34-16582865db29",
    "8c0244d3-a2ed-43db-80c3-1afce23afbd6",
    "98649f57-3a85-4b9c-9542-750c48884c4e",
    "a9d53ed7-0975-4da7-adef-50843736fd2c",
    "ae3e5816-1640-44b1-9624-46196e3a1912",
    "13ff39b8-9bff-4bb6-b5d2-285ad0f8ecb5",
    "6b62526c-619e-4c5c-97c9-8a529243e88a",
    "21767f9f-84dd-4e33-a1e1-a4cffbc7f638",
    "7f8e6f7f-a540-4cf1-9c3b-ef64c6a11988",
    "1485117e-ba50-4cf9-9489-180f775872df",
    "f14ec097-a2fd-40dd-bfc1-27b125d76694",
    "e0c2c61f-b0f9-41a5-bb24-51b27389f0ce",
    "af8f2934-dda8-4ce7-97ff-8a3136f4f733",
    "6c7a5007-780b-4038-9bde-0b5b21874917",
    "302ad849-7903-4857-b216-86e63ba19a91",
    "7b980e46-04d7-4883-975b-ff8bd9579266",
    "aa4cb9d1-9b24-4300-b12e-27f63e8ef962",
    "e29295e8-d87a-48ef-9aa9-02fc9a35160f",
    "fe2e042b-0c9a-4040-bfa0-3ca526076c58",
    "2bce7dd9-e8dd-4562-b023-d84767266d37",
    "7370e0da-f07d-42f9-a45f-157f41087eef",
    "538e0705-9fb1-4a4c-a23f-78bb3f252b8b",
    "1da3d01d-7f65-4459-b980-4d7342a34afa",
    "24e0a5a9-7ce5-4a3e-a300-0ced827c30bc",
    "16492a50-ac5e-4746-9300-f48eae91ae8a",
    "4971ccdf-0547-40ad-9fe0-2a44f6f917f9",
    "57b7920e-c90b-4c93-99b4-a9ab42b869aa",
    "cb8a7887-bf19-48ba-a62e-c72d9a8a884c",
    "53156b1a-e95d-40d0-b3fe-b7fb8f6b5d9b",
    "9237be0d-38a1-4df7-8691-7a8feec29b77",
    "939f2740-05c6-4b34-b575-5b6687d9e087",
    "47808614-29e4-4f44-935e-8f90fc7f69cd",
    "1afc7a79-aad9-498a-9a0e-3c36873b58ef",
    "dae44bbc-28f8-4d5b-a8ce-02c5cc014cf4",
    "a0d50672-be1f-4d5a-8b09-8635ae5edfa7",
    "79cff210-f34f-4a18-84dc-4fe3323b2b45",
    "427bae74-b03f-497d-8816-f633b91dbda7",
    "6b278fec-cc11-4b6d-8a64-59add3d43593",
    "130d170d-7279-4874-9506-aebe3e402cb8",
    "4529f1e8-ba18-4dfb-8811-4dc4b1c28388",
    "6b5b2318-8251-4c82-b136-14821c659d89",
    # October 2024 transactions that were successfully updated
    "07ccda16-13de-47e9-a47e-5998129b3c09_2024-10-01",
    "c4535b45-a942-49d6-a481-5f1cf7bb60ec",
    "1b826018-3f8b-41d3-b450-ec8c71af29ce",
    "570b028e-b2f5-4c4c-9bbf-608a2ff79f89",
    "157d8657-69ae-4a35-ad35-a6b7bfc5ccdd",
    "1e64aea1-ca09-4f8a-9ced-af6b6d648c73_2024-10-01",
    "5fe9f22f-d7da-43a1-ac89-d2534a97ada7",
    "12fe16ef-8f57-4ad2-8782-5844c4ed48de",
    "14dcf88f-7496-4377-83b9-c5342fb748fb",
    "c0cbad48-a75b-43b7-bd53-43c3b2ddc730",
    "35bc7b15-b57a-4a98-b3a3-99f74fe33a91",
    "e3b04bf3-0ab3-4489-abed-2fef52f1fb9a",
    "9faa7e09-a44c-44f7-9205-1dd21881912a",
    "b7fce3ab-a71c-4153-887b-a47acdde0ab2",
    "b532d624-25fb-435d-aee3-689173597486",
    "a11cdd3d-a7b6-4d49-8e01-e77db045e809",
    "611b6570-d63f-4688-a3a4-29c896261718",
    "49ec84ad-72d3-47ed-aaa6-bfcdc5bd7f91",
    "6157156b-1098-404e-8a86-aaa6e96182ad",
    "a7c3c97d-5082-4b68-9530-c93e84c6848a",
    "519c065f-aaba-432a-a573-314a6b3326be",
    "a3d4e9e5-94b5-4977-b869-52d054cda9f7",
    "3a9c8949-db49-4dfd-8b03-d167ddbf44dc",
    "9e0b00db-195e-4c68-bb43-4b503a019971",
    "b9eaabc0-7bc8-4662-967c-6fa40bed37d4",
    "b5f05333-9f24-4818-8322-a2613cf80b2a",
    "06a7ca65-d5e9-461f-afe6-72a7e743923e",
    "d4f32d9b-3595-4970-8f9b-b76078237235",
    "848d93af-6d1c-46d3-bea9-eb1670bf03e7",
    "eb68b28e-f9b9-49c0-a391-8ec0375cca95",
    "106f1033-e054-44e4-a8e6-874da0804b6b",
    "32af4175-7439-4b59-bc73-5a87c89d5485",
    "b6ab577b-cd41-4c0d-a976-3ab12d4d8f6e",
    "6fddd965-be03-47c2-8801-c2afc1142747",
    "5f54f70a-0c16-4eaa-801d-3e448fc62bee",
    "88dd1ba5-b10e-4452-ad07-ef296f0431a6",
    "9a808a85-18e0-4969-885f-0e2d0b0617f4",
    "c5bc6d04-5ee2-41d5-94e4-96da74960cb8",
    "6202ddf6-20a5-4406-87bc-56556e477973",
    "24113d15-6b95-4333-a9cc-7cfc48b1d55d",
    "a1e185dd-d83d-4561-a881-eeb6525e3e37",
    "e4e00de8-9588-43d0-b302-1e2745793891",
    "8d146424-f975-460b-8a52-888fc3d3003f",
    "0e465d84-7c83-4d6e-9249-7d4e85c0786b",
    "07f6a30e-5065-4847-b8fd-420a1acfa2b5",
    "8713ad04-a030-4564-bfc3-c13315ac9951",
    "fff2999b-696d-472b-92fd-95d9a01838f5",
    "3c48a637-8779-4489-8105-2aee40938e51",
    "4b564f4a-dacf-49d1-aafd-9136a1953a4f",
    "196833d4-71e5-4264-9be7-41290295ef96",
    "2c51f08e-be87-48f8-b111-a4f3da688627",
    "11aaf37b-e275-456f-bcfa-9cc2e9e77612",
    "b8f10384-967b-4e02-a5fd-3b90c5f77e38",
    "c09ebe92-0b94-484c-97c8-9bd34bed30a2",
    "552063af-7281-42e0-b989-40eee81f779e"
]

HEADERS = {
    'Authorization': f'Bearer {API_TOKEN}',
    'Content-Type': 'application/json'
}

# Rate limiting configuration
REQUESTS_PER_HOUR = 200  # YNAB's limit
SAFE_REQUESTS_PER_HOUR = 180  # Leave some buffer
SECONDS_BETWEEN_REQUESTS = 3600 / SAFE_REQUESTS_PER_HOUR  # ~20 seconds

class YNABConverter:
    def __init__(self):
        self.state = self.load_state()
        self.request_count = 0
        self.last_request_time = time.time()
        
    def load_state(self):
        """Load the conversion state from file"""
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return {
            'skip_txn_ids': SKIP_TXN_IDS.copy(),
            'last_processed_month': None,
            'failed_transactions': []
        }
    
    def save_state(self):
        """Save the current state to file"""
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def rate_limit_wait(self):
        """Implement smart rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < SECONDS_BETWEEN_REQUESTS:
            wait_time = SECONDS_BETWEEN_REQUESTS - elapsed
            print(f"Rate limiting: waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
        self.last_request_time = time.time()
        self.request_count += 1
        
        # Every 50 requests, take a longer break
        if self.request_count % 50 == 0:
            print(f"Completed {self.request_count} requests. Taking a 5-minute break...")
            time.sleep(300)  # 5 minutes
    
    def make_request(self, method, url, **kwargs):
        """Make a request with retry logic and error handling"""
        max_retries = 5
        base_wait = 60
        
        for attempt in range(max_retries):
            try:
                self.rate_limit_wait()
                
                if method == 'GET':
                    response = requests.get(url, headers=HEADERS, **kwargs)
                elif method == 'PUT':
                    response = requests.put(url, headers=HEADERS, **kwargs)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                if response.status_code == 429:
                    # Rate limited - exponential backoff
                    wait_time = base_wait * (2 ** attempt)
                    print(f"Rate limited. Waiting {wait_time} seconds (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                return response
                
            except requests.exceptions.ConnectionError as e:
                print(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)
                    print(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    raise
            except Exception as e:
                print(f"Unexpected error: {e}")
                raise
        
        raise Exception(f"Max retries exceeded for {url}")
    
    def month_str_to_dt(self, month_str):
        return datetime.strptime(month_str, '%Y-%m-%d')
    
    def get_all_months(self):
        """Fetch all available months"""
        url = f'https://api.ynab.com/v1/budgets/{BUDGET_ID}/months'
        response = self.make_request('GET', url)
        months = [m['month'] for m in response.json()['data']['months']]
        return months
    
    def fetch_transactions_for_month(self, month):
        """Fetch transactions for a specific month"""
        url = f'https://api.ynab.com/v1/budgets/{BUDGET_ID}/months/{month}/transactions'
        response = self.make_request('GET', url)
        return response.json()['data']['transactions']
    
    def update_transaction_amount(self, txn_id, new_milliunits, memo):
        """Update a single transaction"""
        url = f'https://api.ynab.com/v1/budgets/{BUDGET_ID}/transactions/{txn_id}'
        data = {
            "transaction": {
                "amount": new_milliunits,
                "memo": memo
            }
        }
        
        try:
            response = self.make_request('PUT', url, json=data)
            print(f"✓ Updated {txn_id}")
            # Add to skip list after successful update
            if txn_id not in self.state['skip_txn_ids']:
                self.state['skip_txn_ids'].append(txn_id)
                self.save_state()
            return True
        except Exception as e:
            print(f"✗ Failed to update {txn_id}: {e}")
            if txn_id not in self.state['failed_transactions']:
                self.state['failed_transactions'].append(txn_id)
                self.save_state()
            return False
    
    def convert_and_update(self):
        """Main conversion process"""
        print("Starting YNAB currency conversion...")
        print(f"Conversion rate: EUR to AED = {CONVERSION_RATE}")
        print(f"Starting from: {START_MONTH}")
        print(f"Already processed: {len(self.state['skip_txn_ids'])} transactions")
        print("-" * 50)
        
        try:
            months = self.get_all_months()
            print(f"Found {len(months)} months total")
            
            # Filter months based on start date
            months_to_process = [m for m in months if self.month_str_to_dt(m) >= self.month_str_to_dt(START_MONTH)]
            print(f"Will process {len(months_to_process)} months")
            
            total_updated = 0
            total_skipped = 0
            total_failed = 0
            
            for month_idx, month in enumerate(months_to_process):
                print(f"\n[{month_idx + 1}/{len(months_to_process)}] Processing {month}...")
                self.state['last_processed_month'] = month
                self.save_state()
                
                transactions = self.fetch_transactions_for_month(month)
                print(f"  Found {len(transactions)} transactions")
                
                month_updated = 0
                month_skipped = 0
                month_failed = 0
                
                for txn in transactions:
                    if txn.get('deleted'):
                        continue
                    
                    if txn['id'] in self.state['skip_txn_ids']:
                        month_skipped += 1
                        continue
                    
                    # Calculate conversion
                    old_amount_eur = txn['amount'] / 1000.0
                    new_amount_aed = old_amount_eur * CONVERSION_RATE
                    new_milliunits = int(round(new_amount_aed * 1000))
                    
                    # Skip if amount hasn't changed (edge case)
                    if new_milliunits == txn['amount']:
                        month_skipped += 1
                        continue
                    
                    # Update transaction
                    if self.update_transaction_amount(txn['id'], new_milliunits, txn.get('memo', '')):
                        month_updated += 1
                    else:
                        month_failed += 1
                
                print(f"  Month summary: {month_updated} updated, {month_skipped} skipped, {month_failed} failed")
                total_updated += month_updated
                total_skipped += month_skipped
                total_failed += month_failed
                
                # Save state after each month
                self.save_state()
                
        except KeyboardInterrupt:
            print("\n\nConversion interrupted by user.")
            print("Progress has been saved. You can resume from where you left off.")
            self.save_state()
        except Exception as e:
            print(f"\n\nError occurred: {e}")
            print("Progress has been saved. You can resume from where you left off.")
            self.save_state()
            raise
        
        print("\n" + "=" * 50)
        print("CONVERSION COMPLETE!")
        print(f"Total transactions updated: {total_updated}")
        print(f"Total transactions skipped: {total_skipped}")
        print(f"Total transactions failed: {total_failed}")
        
        if self.state['failed_transactions']:
            print(f"\nFailed transactions saved to state file: {len(self.state['failed_transactions'])}")
            print("You can retry these by removing them from the failed_transactions list in the state file.")

if __name__ == '__main__':
    converter = YNABConverter()
    converter.convert_and_update()