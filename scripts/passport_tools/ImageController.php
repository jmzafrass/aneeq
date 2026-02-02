<?php
namespace app\controllers;

use Yii;
use yii\web\Controller;
use yii\web\NotFoundHttpException;
use yii\web\Response;

/**
 * Image Controller - Serves ID proof images
 *
 * Add this controller to your Yii2 application to serve passport/ID images
 *
 * Usage: https://qa-uaesaas-api.instapract.ae/image/serve?file=1192057627_idproof_1727180827.jpg
 */
class ImageController extends Controller
{
    /**
     * @inheritdoc
     */
    public $enableCsrfValidation = false;

    /**
     * Serves ID proof images
     *
     * @param string $file - The filename to serve
     * @return Response
     * @throws NotFoundHttpException
     */
    public function actionServe($file = null)
    {
        if (empty($file)) {
            throw new NotFoundHttpException('File parameter is required');
        }

        // Sanitize filename to prevent directory traversal
        $file = basename($file);

        // Define the image directory path
        $imagePath = Yii::getAlias('@webroot/images/idproof/') . $file;

        // Check if file exists
        if (!file_exists($imagePath)) {
            throw new NotFoundHttpException('Image not found');
        }

        // Get file mime type
        $mimeType = mime_content_type($imagePath);

        // Allowed image types
        $allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];

        if (!in_array($mimeType, $allowedTypes)) {
            throw new NotFoundHttpException('Invalid file type');
        }

        // Set response headers
        Yii::$app->response->format = Response::FORMAT_RAW;
        Yii::$app->response->headers->set('Content-Type', $mimeType);
        Yii::$app->response->headers->set('Content-Length', filesize($imagePath));

        // Optional: Enable caching
        Yii::$app->response->headers->set('Cache-Control', 'public, max-age=31536000');
        Yii::$app->response->headers->set('Expires', gmdate('D, d M Y H:i:s', time() + 31536000) . ' GMT');

        // Return the file content
        return Yii::$app->response->sendFile($imagePath, null, ['inline' => true]);
    }

    /**
     * Alternative action that accepts filename in URL path
     *
     * Usage: https://qa-uaesaas-api.instapract.ae/image/get/1192057627_idproof_1727180827.jpg
     *
     * Requires URL rule in config:
     * 'image/get/<file:.+\.(jpg|jpeg|png|gif)>' => 'image/get',
     */
    public function actionGet($file)
    {
        return $this->actionServe($file);
    }
}
