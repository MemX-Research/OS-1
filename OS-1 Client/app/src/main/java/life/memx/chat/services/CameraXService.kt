package life.memx.chat.services

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.util.Size
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.common.util.concurrent.ListenableFuture
import life.memx.chat.R
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.Queue
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors


class CameraXService internal constructor(
    var queue: Queue<ByteArray>, private val activity: AppCompatActivity
) {
    private val TAG: String = CameraXService::class.java.simpleName
    private val rotate = 0 // TODO set image rotation

    private var imageSize = Size(480, 640)

    private var needCapturing = true
    private var previewView: PreviewView? = null
    private var mPreview: Preview? = null

    private lateinit var cameraProviderFuture: ListenableFuture<ProcessCameraProvider>
    private lateinit var cameraExecutor: ExecutorService
    private lateinit var processCameraProvider: ProcessCameraProvider
    private lateinit var cameraSelector: CameraSelector
    private var imageCapture: ImageCapture? = null
//    private var imageAnalyzer: ImageAnalysis? = null
    private var lensFacing = CameraSelector.LENS_FACING_BACK
    private var mCamera: Camera? = null


    fun startCapturing() {
        previewView = activity.findViewById(R.id.previewView)
        mPreview?.setSurfaceProvider(previewView?.surfaceProvider)

        val handler = Handler(Looper.getMainLooper())

        val runTask: Runnable = object : Runnable {
            override fun run() {
                try {
                    handler.postDelayed(this, 10000)
                    if (!needCapturing) {
                        Log.i(TAG, "Don't need capturing")
                        return
                    }
                    openCameraThenShoot()
                } catch (e: Exception) {
                    Log.e(TAG, "openCameraThenShoot error: $e")
                    Toast.makeText(
                        activity,
                        "openCameraThenShoot error: $e",
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
        }
        handler.post(runTask)
    }

    fun openCameraThenShoot() {
        cameraExecutor = Executors.newSingleThreadExecutor()
        cameraProviderFuture = ProcessCameraProvider.getInstance(activity)
        cameraProviderFuture.addListener(Runnable {
            processCameraProvider = cameraProviderFuture.get()
            //Set the camera parameters
            bindCameraUseCases()

            val shootHandler = Handler(Looper.getMainLooper())
            val shootTask: Runnable = Runnable {
                Log.d(TAG, "takePicture")
                takePicture()
            }
            shootHandler.postDelayed(shootTask, 500)   // waiting for initialization
        }, ContextCompat.getMainExecutor(activity))
    }

    fun setImageSize(w: Int, h: Int) {
        imageSize = Size(w, h)
    }

    private fun uploadImage(file: File) {
        if (rotate != 0) {
            val sourceBitmap = BitmapFactory.decodeFile(file.absolutePath)
            val matrix = Matrix()
            matrix.postRotate(rotate.toFloat())
            val rotatedBitmap =
                Bitmap.createBitmap(
                    sourceBitmap,
                    0,
                    0,
                    sourceBitmap.width,
                    sourceBitmap.height,
                    matrix,
                    true
                )

            val out = ByteArrayOutputStream()
            rotatedBitmap.compress(Bitmap.CompressFormat.JPEG, 100, out)

            val bytes = out.toByteArray()
            queue.add(bytes)
        } else {
            val bytes = file.readBytes()
            queue.add(bytes)
        }
        closeCamera()
    }


    /**
     * take picture
     */
    private fun takePicture() {

        val photoFile = createPhotoFile()
        val metadata = ImageCapture.Metadata().apply {
            isReversedHorizontal = lensFacing == CameraSelector.LENS_FACING_FRONT
        }

        val outputOptions = ImageCapture.OutputFileOptions.Builder(photoFile)
            .setMetadata(metadata)
            .build()

        imageCapture?.takePicture(
            outputOptions, cameraExecutor, object : ImageCapture.OnImageSavedCallback {
                override fun onError(exc: ImageCaptureException) {
                    Log.e(TAG, "Photo capture failed: ${exc.message}", exc)
                    Toast.makeText(
                        activity,
                        "Photo capture failed: ${exc.message}",
                        Toast.LENGTH_LONG
                    ).show()
                }

                override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                    val savedUri = output.savedUri ?: Uri.fromFile(photoFile)
                    uploadImage(photoFile)
                    Log.d(TAG, "Photo capture succeeded: $savedUri")
                }
            })
    }


    private fun createPhotoFile(): File {
        return File(activity.cacheDir, System.currentTimeMillis().toString() + ".jpg")
    }

    private fun closeCamera() {
        val handler = Handler(Looper.getMainLooper())

        val runTask: Runnable = Runnable {
            try {
                cameraExecutor.shutdown()
                processCameraProvider.unbindAll()
            } catch (e: Exception) {
                Log.e(TAG, "closeCamera error: $e")
                Toast.makeText(
                    activity,
                    "closeCamera error: $e",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
        handler.post(runTask)
    }


    /**
     * Instantiate camera & preview
     */
    fun bindCameraUseCases() {

        mPreview = Preview.Builder()
            .build()
        cameraSelector = CameraSelector.Builder().requireLensFacing(lensFacing).build()

        processCameraProvider.unbindAll()

        initTakePictureCases()
        // All instances are bound to the lifecycle
        mCamera = processCameraProvider.bindToLifecycle(
            activity,
            cameraSelector,
            mPreview,
            imageCapture,
//            imageAnalyzer
        )

        mPreview?.setSurfaceProvider(previewView?.surfaceProvider)
        previewView?.implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        previewView?.rotation = rotate.toFloat()
    }


    /**
     * Initialize photo taking instance
     */
    private fun initTakePictureCases() {
        // ImageCapture
        imageCapture = ImageCapture.Builder()
//            .setTargetAspectRatio(aspectRatio())
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
            .setFlashMode(ImageCapture.FLASH_MODE_OFF)
            .setTargetResolution(imageSize) // Target resolution, the actual output size is greater than or equal to this size
//            .setTargetRotation(Surface.ROTATION_90)
            .build()

    }


    fun setNeedCapturing(b: Boolean) {
        needCapturing = b
    }

    fun stopCapturing() {
        closeCamera()
    }

    companion object {
        private const val RATIO_4_3_VALUE = 4.0 / 3.0
        private const val RATIO_16_9_VALUE = 16.0 / 9.0
    }


}
