"""
Extract nationality from passport images using OCR

This script will:
1. Download passport images (once server is fixed)
2. Use OCR to extract text from images
3. Identify nationality information
4. Store results in a CSV file

Requirements:
pip install pytesseract pillow opencv-python
sudo apt-get install tesseract-ocr (Linux/Mac)
or download from: https://github.com/UB-Mannheim/tesseract/wiki (Windows)
"""

import os
import re
import csv
from PIL import Image
import requests
from io import BytesIO

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("⚠️  pytesseract not installed. Install with: pip install pytesseract")


def download_image(url):
    """Download image from URL"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"Error downloading image: {e}")
        return None


def extract_text_from_image(image_path_or_url):
    """Extract text from image using OCR"""
    if not OCR_AVAILABLE:
        print("❌ OCR not available. Install pytesseract first.")
        return None

    try:
        # Load image
        if image_path_or_url.startswith('http'):
            image = download_image(image_path_or_url)
        else:
            image = Image.open(image_path_or_url)

        if image is None:
            return None

        # Perform OCR
        text = pytesseract.image_to_string(image, lang='eng')
        return text

    except Exception as e:
        print(f"Error extracting text: {e}")
        return None


def extract_nationality(text):
    """
    Extract nationality from OCR text
    Common patterns in passports:
    - Nationality: UNITED ARAB EMIRATES
    - NAT: UAE
    - Nationality/Nationalité: INDIA
    """
    if not text:
        return None

    # Patterns to search for nationality
    patterns = [
        r'Nationality[:/\s]+([A-Z\s]+)',
        r'Nationalit[ée][:/\s]+([A-Z\s]+)',
        r'NAT[:/\s]+([A-Z]{2,3})',
        r'Citizen[ship]*[:/\s]+([A-Z\s]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            nationality = match.group(1).strip()
            # Clean up the result
            nationality = re.sub(r'\s+', ' ', nationality)
            return nationality

    # Common country codes in passports
    country_codes = {
        'UAE': 'United Arab Emirates',
        'IND': 'India',
        'PAK': 'Pakistan',
        'USA': 'United States',
        'GBR': 'United Kingdom',
        'SAU': 'Saudi Arabia',
        'EGY': 'Egypt',
        'JOR': 'Jordan',
        'LBN': 'Lebanon',
        'SYR': 'Syria',
        'IRQ': 'Iraq',
    }

    # Look for country codes in text
    for code, country in country_codes.items():
        if code in text.upper():
            return country

    return None


def process_customer_passport(customer_id, image_url):
    """Process a single customer's passport image"""
    print(f"\nProcessing customer {customer_id}...")
    print(f"Image URL: {image_url}")

    # Extract text
    text = extract_text_from_image(image_url)

    if not text:
        print("❌ Failed to extract text")
        return {
            'customer_id': customer_id,
            'image_url': image_url,
            'nationality': None,
            'status': 'Failed to extract text'
        }

    # Extract nationality
    nationality = extract_nationality(text)

    if nationality:
        print(f"✅ Found nationality: {nationality}")
    else:
        print("⚠️  Could not identify nationality")
        # Print first 500 chars of OCR text for manual review
        print(f"OCR Text (first 500 chars):\n{text[:500]}")

    return {
        'customer_id': customer_id,
        'image_url': image_url,
        'nationality': nationality,
        'full_text': text[:1000],  # Store first 1000 chars
        'status': 'Success' if nationality else 'Manual review needed'
    }


def batch_process_passports(customer_data):
    """
    Process multiple customer passports
    customer_data should be a list of dicts with 'customer_id' and 'image_url'
    """
    results = []

    for customer in customer_data:
        result = process_customer_passport(
            customer['customer_id'],
            customer['image_url']
        )
        results.append(result)

    # Save results to CSV
    output_file = 'passport_nationality_results.csv'
    fieldnames = ['customer_id', 'image_url', 'nationality', 'status', 'full_text']

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ Results saved to {output_file}")
    print(f"Processed {len(results)} passports")
    print(f"Successful extractions: {sum(1 for r in results if r['nationality'])}")

    return results


if __name__ == "__main__":
    print("=" * 70)
    print("PASSPORT NATIONALITY EXTRACTION TOOL")
    print("=" * 70)

    # Check if OCR is available
    if not OCR_AVAILABLE:
        print("\n⚠️  Warning: pytesseract is not installed!")
        print("Install it with: pip install pytesseract pillow")
        print("\nYou also need to install Tesseract OCR engine:")
        print("- Ubuntu/Debian: sudo apt-get install tesseract-ocr")
        print("- Mac: brew install tesseract")
        print("- Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        exit(1)

    # Example usage - replace with your actual data
    customer_data = [
        {
            'customer_id': '1192057627',
            'image_url': 'https://qa-uaesaas-api.instapract.ae/web/images/idproof/1192057627_idproof_1727180827.jpg'
        },
        # Add more customers here
    ]

    # Process all passports
    results = batch_process_passports(customer_data)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for result in results:
        print(f"Customer {result['customer_id']}: {result['nationality'] or 'NOT FOUND'} ({result['status']})")
