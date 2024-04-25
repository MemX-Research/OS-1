package life.memx.chat.services


import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.ImageFormat
import android.hardware.camera2.*
import android.hardware.camera2.CameraCaptureSession.CaptureCallback
import android.media.Image
import android.media.ImageReader
import android.media.ImageReader.OnImageAvailableListener
import android.os.Handler
import android.util.Log
import android.util.Range
import android.util.Size
import android.view.Surface
import androidx.core.app.ActivityCompat
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.ByteBuffer
import java.util.*


interface PictureCapturingListener {

    fun onCaptureDone(pictureUrl: String?, pictureData: ByteArray?)

//    fun onDoneCapturingAllPhotos(picturesTaken: TreeMap<String, ByteArray>?)
}


class PictureCapturingService internal constructor(private val activity: Activity) {

    var context: Context
    var manager: CameraManager

    private val TAG: String = PictureCapturingService::class.java.getSimpleName()

    private var cameraDevice: CameraDevice? = null
    private var imageReader: ImageReader? = null

    private var cameraIds: Queue<String>? = null

    private var currentCameraId: String? = null
    private var cameraClosed = false

    private var picturesTaken: TreeMap<String, ByteArray>? = null
    private var capturingListener: PictureCapturingListener? = null

//    public fun getInstance(activity: Activity): PictureCapturingService? {
//        return PictureCapturingService(activity)
//    }

    fun startCapturing(listener: PictureCapturingListener?) {
        Log.i(TAG, "startCapturing")
        picturesTaken = TreeMap()
        capturingListener = listener
        cameraIds = LinkedList()
        try {
            val cameraIdList: Array<String> = manager.cameraIdList
            if (cameraIdList.size > 0) {
//                cameraIds?.addAll(Arrays.asList(cameraIdList).toString())
//                currentCameraId = this.cameraIds.poll()
                currentCameraId = cameraIdList[0]
                openCamera()
            } else {
//                val characteristics: CameraCharacteristics = manager.getCameraCharacteristics("0")
//                Log.e(TAG, characteristics.toString())
                Log.e(TAG, "No camera detected!")
                // capturingListener!!.onDoneCapturingAllPhotos(picturesTaken)
            }
        } catch (e: CameraAccessException) {
            Log.e(TAG, "Exception occurred while accessing the list of cameras", e)
        }
    }

    private fun openCamera() {
        Log.d(TAG, "opening camera $currentCameraId")
        try {
            if (ActivityCompat.checkSelfPermission(context, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED
                && ActivityCompat.checkSelfPermission(
                    context,
                    Manifest.permission.WRITE_EXTERNAL_STORAGE
                )
                == PackageManager.PERMISSION_GRANTED
            ) {
                currentCameraId?.let { manager.openCamera(it, stateCallback, null) }
            }
        } catch (e: CameraAccessException) {
            Log.e(TAG, " exception occurred while opening camera $currentCameraId", e)
        }
    }

    private val captureListener: CaptureCallback = object : CaptureCallback() {
        override fun onCaptureCompleted(
            session: CameraCaptureSession, request: CaptureRequest,
            result: TotalCaptureResult
        ) {
            super.onCaptureCompleted(session, request, result)
            if (picturesTaken!!.lastEntry() != null) {
                capturingListener!!.onCaptureDone(
                    picturesTaken!!.lastEntry().key,
                    picturesTaken!!.lastEntry().value
                )
                Log.i(TAG, "done taking picture from camera " + cameraDevice!!.id)
            }
            closeCamera()
        }
    }


    private val onImageAvailableListener = OnImageAvailableListener { imReader: ImageReader ->
        val image: Image = imReader.acquireLatestImage()
        val buffer: ByteBuffer = image.getPlanes().get(0).getBuffer()
        val bytes = ByteArray(buffer.capacity())
        buffer.get(bytes)
        saveImageToDisk(bytes)
        image.close()
    }

    private val stateCallback: CameraDevice.StateCallback = object : CameraDevice.StateCallback() {
        override fun onOpened(camera: CameraDevice) {
            cameraClosed = false
            Log.d(TAG, "camera " + camera.id + " opened")
            cameraDevice = camera
            Log.i(TAG, "Taking picture from camera " + camera.id)
            //Take the picture after some delay. It may resolve getting a black dark photos.
            Handler().postDelayed({
                try {
                    takePicture()
                } catch (e: CameraAccessException) {
                    Log.e(TAG, " exception occurred while taking picture from $currentCameraId", e)
                }
            }, 500)
        }

        override fun onDisconnected(camera: CameraDevice) {
            Log.d(TAG, " camera " + camera.id + " disconnected")
            if (cameraDevice != null && !cameraClosed) {
                cameraClosed = true
                cameraDevice!!.close()
            }
        }

        override fun onClosed(camera: CameraDevice) {
            cameraClosed = true
            Log.d(TAG, "camera " + camera.id + " closed")
            //once the current camera has been closed, start taking another picture
//            if (!cameraIds!!.isEmpty()) {
//                takeAnotherPicture()
//            } else {
//                capturingListener!!.onDoneCapturingAllPhotos(picturesTaken)
//            }
        }

        override fun onError(camera: CameraDevice, error: Int) {
            Log.e(TAG, "camera in error, int code $error")
            if (cameraDevice != null && !cameraClosed) {
                cameraDevice!!.close()
            }
        }
    }


    @Throws(CameraAccessException::class)
    private fun takePicture() {
        if (null == cameraDevice) {
            Log.e(TAG, "cameraDevice is null")
            return
        }
        val characteristics: CameraCharacteristics =
            manager.getCameraCharacteristics(cameraDevice!!.getId())
        var jpegSizes: Array<Size>? = null
        val streamConfigurationMap =
            characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
        if (streamConfigurationMap != null) {
            jpegSizes = streamConfigurationMap.getOutputSizes(ImageFormat.JPEG)
        }
        val jpegSizesNotEmpty = jpegSizes != null && 0 < jpegSizes.size
        val width = 1920 // if (jpegSizesNotEmpty) jpegSizes!![0].getWidth() else 1920
        val height = 1080 //if (jpegSizesNotEmpty) jpegSizes!![0].getHeight() else 1080
        val reader = ImageReader.newInstance(width, height, ImageFormat.JPEG, 1)
        val outputSurfaces: MutableList<Surface> = ArrayList()
        outputSurfaces.add(reader.surface)
        val captureBuilder = cameraDevice!!.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE)
        captureBuilder.addTarget(reader.surface)
        captureBuilder.set(CaptureRequest.CONTROL_MODE, CameraMetadata.CONTROL_MODE_AUTO)
        captureBuilder.set(CaptureRequest.CONTROL_AE_MODE, CameraMetadata.CONTROL_AE_MODE_ON)
        captureBuilder.set(CaptureRequest.CONTROL_AE_LOCK, true)
        captureBuilder.set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range.create(5,30))
        captureBuilder.set(CaptureRequest.CONTROL_AWB_MODE, CameraMetadata.CONTROL_AWB_MODE_AUTO)
        captureBuilder.set(CaptureRequest.JPEG_ORIENTATION, Surface.ROTATION_90)
        reader.setOnImageAvailableListener(onImageAvailableListener, null)
        cameraDevice!!.createCaptureSession(
            outputSurfaces,
            object : CameraCaptureSession.StateCallback() {
                override fun onConfigured(session: CameraCaptureSession) {
                    try {
                        session.capture(captureBuilder.build(), captureListener, null)
                    } catch (e: CameraAccessException) {
                        Log.e(TAG, " exception occurred while accessing $currentCameraId", e)
                    }
                }
                override fun onConfigureFailed(session: CameraCaptureSession) {}
            },
            null)
    }


    private fun saveImageToDisk(bytes: ByteArray) {
        val file = File(context.getExternalFilesDir(null).toString() + "/world.jpg")
        try {
            FileOutputStream(file).use { output ->
                output.write(bytes)
                picturesTaken!!.put(file.getPath(), bytes)
            }
        } catch (e: IOException) {
            Log.e(TAG, "Exception occurred while saving picture to external storage ", e)
        }
    }

    private fun takeAnotherPicture() {
        currentCameraId = cameraIds!!.poll()
        openCamera()
    }

    private fun closeCamera() {
        Log.d(TAG, "closing camera " + cameraDevice!!.id)
        if (null != cameraDevice && !cameraClosed) {
            cameraDevice!!.close()
            cameraDevice = null
        }
        if (null != imageReader) {
            imageReader!!.close()
            imageReader = null
        }
    }

    init {
        context = activity.applicationContext
        manager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
    }
}