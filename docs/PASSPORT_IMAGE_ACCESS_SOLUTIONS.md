# Passport Image Access - Problem & Solutions

## Problem
The passport/ID proof images stored at `https://qa-uaesaas-api.instapract.ae/web/images/idproof/` cannot be accessed because:

1. Yii2 is treating the image URLs as application routes
2. The web server is not configured to serve static files directly
3. The `.htaccess` or Nginx configuration is missing rules to bypass static files

**Error received:**
```
yii\base\InvalidRouteException: Unable to resolve the request "images/idproof/331419357_idproof_1726814968.jpg"
```

---

## Solution 1: Fix Apache .htaccess (RECOMMENDED)

### Steps:
1. SSH into your server: `ssh user@qa-uaesaas-api.instapract.ae`
2. Navigate to the web directory: `cd /var/www/html/web/`
3. Edit or create `.htaccess` file: `nano .htaccess`
4. Add the following content:

```apache
# Yii2 Web Directory .htaccess
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
```

5. Save and test: `curl -I https://qa-uaesaas-api.instapract.ae/web/images/idproof/1192057627_idproof_1727180827.jpg`

---

## Solution 2: Fix Nginx Configuration

If your server uses Nginx instead of Apache:

1. Edit your Nginx site configuration: `sudo nano /etc/nginx/sites-available/default`
2. Add/modify the location blocks:

```nginx
server {
    listen 80;
    server_name qa-uaesaas-api.instapract.ae;
    root /var/www/html/web;
    index index.php;

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
}
```

3. Test configuration: `sudo nginx -t`
4. Reload Nginx: `sudo systemctl reload nginx`

---

## Solution 3: Create Yii2 Image Controller (TEMPORARY WORKAROUND)

If you cannot modify server configuration immediately, create a controller to serve images:

### Step 1: Add the ImageController

Copy `ImageController.php` to your Yii2 application:
```bash
cp ImageController.php /var/www/html/controllers/
```

### Step 2: Update URL rules (optional)

Edit `config/web.php` to add URL rules:

```php
'urlManager' => [
    'enablePrettyUrl' => true,
    'showScriptName' => false,
    'rules' => [
        'image/<file:.+\.(jpg|jpeg|png|gif)>' => 'image/serve',
        // ... other rules
    ],
],
```

### Step 3: Access images via controller

New URL format:
```
https://qa-uaesaas-api.instapract.ae/image/serve?file=1192057627_idproof_1727180827.jpg
```

---

## Solution 4: Access via Direct Server Path

If you have server SSH access, you can access files directly:

```bash
ssh user@qa-uaesaas-api.instapract.ae
cd /var/www/html/web/images/idproof/
ls -la
cat 1192057627_idproof_1727180827.jpg
```

Then copy to your local machine:
```bash
scp user@qa-uaesaas-api.instapract.ae:/var/www/html/web/images/idproof/1192057627_idproof_1727180827.jpg ./passport_images/
```

---

## Solution 5: Create API Endpoint to Fetch Images

Create a proper API endpoint in your Yii2 application:

```php
// In controllers/ApiController.php

public function actionGetIdProof($customerId)
{
    $customer = Customer::findOne($customerId);
    if (!$customer || !$customer->id_proof_path) {
        throw new NotFoundHttpException('ID proof not found');
    }

    $imagePath = Yii::getAlias('@webroot') . '/' . $customer->id_proof_path;

    if (!file_exists($imagePath)) {
        throw new NotFoundHttpException('Image file not found');
    }

    return Yii::$app->response->sendFile($imagePath, null, ['inline' => true]);
}
```

Access via:
```
https://qa-uaesaas-api.instapract.ae/api/get-id-proof?customerId=1192057627
```

---

## Testing After Fix

Use the Python script to test if images are accessible:

```bash
python3 download_passport_images.py
```

Or test with curl:
```bash
curl -I https://qa-uaesaas-api.instapract.ae/web/images/idproof/1192057627_idproof_1727180827.jpg
```

You should see:
```
HTTP/1.1 200 OK
Content-Type: image/jpeg
Content-Length: [file size]
```

---

## Extracting Nationality from Passport

Once images are accessible, you can use OCR to extract nationality:

### Option 1: Use Python OCR (Tesseract)
```python
pip install pytesseract pillow
```

### Option 2: Use Cloud OCR Services
- Google Cloud Vision API
- AWS Textract
- Azure Computer Vision

### Option 3: Manual Database Update
If you have passport data in another system, update the WooCommerce customer meta directly.

---

## Recommended Action

**Priority 1**: Fix the `.htaccess` or Nginx configuration (Solution 1 or 2)
- This is the root cause and proper fix
- All static files will work correctly

**Priority 2**: Use the ImageController (Solution 3) as a temporary workaround
- Quick deployment
- No server config changes needed

**Priority 3**: Create a proper API endpoint (Solution 5)
- Best practice for production
- Includes security and validation
