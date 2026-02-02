import requests
import os
from urllib.parse import urlparse

def download_passport_image(url, output_dir='passport_images'):
    """
    Download passport/ID proof images from the server
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Extract filename from URL
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)

        # Full path for saving
        output_path = os.path.join(output_dir, filename)

        # Download the image
        print(f"Downloading: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Save the image
        with open(output_path, 'wb') as f:
            f.write(response.content)

        print(f"✅ Downloaded successfully: {output_path}")
        return output_path

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ Error downloading image: {e}")
        return None


def download_multiple_images(urls):
    """
    Download multiple passport images
    """
    downloaded_files = []
    for url in urls:
        result = download_passport_image(url)
        if result:
            downloaded_files.append(result)

    print(f"\n✅ Downloaded {len(downloaded_files)} out of {len(urls)} images")
    return downloaded_files


if __name__ == "__main__":
    # Example usage
    urls = [
        "https://qa-uaesaas-api.instapract.ae/web/images/idproof/1192057627_idproof_1727180827.jpg",
        # Add more URLs here as needed
    ]

    download_multiple_images(urls)
