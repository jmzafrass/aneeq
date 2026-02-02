"""
Script to diagnose and fix passport image access issues

The problem: Yii2 is routing image requests through the application instead of serving them directly.

Solutions:
1. Access images via direct server file path (if you have server access)
2. Create an API endpoint to serve the images
3. Fix the .htaccess/nginx configuration
"""

import requests
import os

# Test different URL patterns
def test_image_urls(base_filename):
    """
    Try different URL patterns to access the image
    """
    customer_id = base_filename.split('_')[0]

    test_urls = [
        # Original URL
        f"https://qa-uaesaas-api.instapract.ae/web/images/idproof/{base_filename}",

        # Try without /web/
        f"https://qa-uaesaas-api.instapract.ae/images/idproof/{base_filename}",

        # Try with uploads path
        f"https://qa-uaesaas-api.instapract.ae/uploads/idproof/{base_filename}",
        f"https://qa-uaesaas-api.instapract.ae/web/uploads/idproof/{base_filename}",

        # Try with assets path
        f"https://qa-uaesaas-api.instapract.ae/assets/images/idproof/{base_filename}",

        # Try with static path
        f"https://qa-uaesaas-api.instapract.ae/static/images/idproof/{base_filename}",
    ]

    print(f"Testing URLs for: {base_filename}\n")

    for url in test_urls:
        try:
            print(f"Testing: {url}")
            response = requests.head(url, timeout=5, allow_redirects=True)

            if response.status_code == 200:
                print(f"  ✅ SUCCESS! Status: {response.status_code}")
                print(f"  Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
                print(f"  Content-Length: {response.headers.get('Content-Length', 'Unknown')} bytes")
                return url
            else:
                print(f"  ❌ Failed: {response.status_code}")
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:50]}")
        print()

    return None


# Generate .htaccess fix
def generate_htaccess_fix():
    """
    Generate the correct .htaccess configuration
    """
    htaccess_content = """# Yii2 Web Directory .htaccess
RewriteEngine on

# if a directory or a file exists, use it directly
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d

# otherwise forward it to index.php
RewriteRule . index.php

# Ensure images, CSS, JS are served directly
<FilesMatch "\.(jpg|jpeg|png|gif|ico|css|js|pdf|svg|woff|woff2|ttf|eot)$">
    # Disable PHP execution in upload directories
    php_flag engine off
</FilesMatch>
"""

    with open('.htaccess_fix', 'w') as f:
        f.write(htaccess_content)

    print("✅ Generated .htaccess_fix file")
    print("\nTo fix the issue on the server:")
    print("1. Copy this content to /var/www/html/web/.htaccess")
    print("2. Ensure Apache mod_rewrite is enabled")
    print("3. Restart Apache: sudo systemctl restart apache2")
    print("\nContent:")
    print(htaccess_content)


# Generate Nginx fix
def generate_nginx_fix():
    """
    Generate the correct Nginx configuration
    """
    nginx_content = """# Yii2 Nginx Configuration

location / {
    # Try to serve file directly, fallback to index.php
    try_files $uri $uri/ /index.php?$args;
}

# Serve static files directly with caching
location ~* \.(jpg|jpeg|png|gif|ico|css|js|pdf|svg|woff|woff2|ttf|eot)$ {
    expires 1y;
    access_log off;
    add_header Cache-Control "public, immutable";
}

# Deny access to sensitive files
location ~ /\.(ht|git|svn) {
    deny all;
}

# PHP processing
location ~ \.php$ {
    fastcgi_pass unix:/var/run/php/php-fpm.sock;
    fastcgi_index index.php;
    fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    include fastcgi_params;
}
"""

    with open('nginx_fix.conf', 'w') as f:
        f.write(nginx_content)

    print("\n✅ Generated nginx_fix.conf file")
    print("\nTo fix the issue on Nginx server:")
    print("1. Add this configuration to your server block in /etc/nginx/sites-available/")
    print("2. Test config: sudo nginx -t")
    print("3. Reload Nginx: sudo systemctl reload nginx")
    print("\nContent:")
    print(nginx_content)


if __name__ == "__main__":
    print("=" * 70)
    print("PASSPORT IMAGE ACCESS DIAGNOSTIC TOOL")
    print("=" * 70)
    print()

    # Test the specific image
    test_filename = "1192057627_idproof_1727180827.jpg"
    working_url = test_image_urls(test_filename)

    print("\n" + "=" * 70)
    print("SOLUTION CONFIGURATIONS")
    print("=" * 70)
    print()

    # Generate fixes
    generate_htaccess_fix()
    generate_nginx_fix()

    if working_url:
        print(f"\n✅ Working URL found: {working_url}")
    else:
        print("\n❌ No working URL found. Server configuration needs to be fixed.")
        print("\nThe issue is that Yii2 is intercepting image requests.")
        print("Apply the configuration fixes above to resolve this.")
