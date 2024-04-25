package life.memx.chat.services

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.graphics.ImageFormat
import android.hardware.camera2.CameraAccessException
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CameraMetadata
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.TotalCaptureResult
import android.media.Image
import android.media.ImageReader
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.util.Range
import android.view.Surface
import java.nio.ByteBuffer
import java.util.Queue
import java.util.Timer
import java.util.TimerTask
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService


class ImageCapturing internal constructor(
    var queue: Queue<ByteArray>, private val activity: Activity
) {

    private val TAG: String = ImageCapturing::class.java.simpleName

    private lateinit var context: Context
    private lateinit var manager: CameraManager
    private lateinit var capturingExecutor: ScheduledExecutorService

    private var cameraOpened = false
    private var needCapturing = true
    private var cameraDevice: CameraDevice? = null

    private val onImageAvailableListener =
        ImageReader.OnImageAvailableListener { imReader: ImageReader ->
            val image: Image = imReader.acquireLatestImage()
            val buffer: ByteBuffer = image.planes[0].buffer
            val bytes = ByteArray(buffer.capacity())
            buffer.get(bytes)
            queue.add(bytes)
            image.close()
            imReader.close()
            closeCamera()
        }

    private val captureListener: CameraCaptureSession.CaptureCallback =
        object : CameraCaptureSession.CaptureCallback() {
            override fun onCaptureCompleted(
                session: CameraCaptureSession, request: CaptureRequest,
                result: TotalCaptureResult
            ) {
                super.onCaptureCompleted(session, request, result)
                Log.i(TAG, "Capture Completed")
                closeCamera()
            }
        }

    fun startCapturing() {
        context = activity.applicationContext
        manager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        Timer().schedule(object : TimerTask() {
            override fun run() {
                if (!needCapturing) {
                    Log.i(TAG, "Don't need capturing")
                    return
                }
                if (cameraOpened) {
                    Log.i(TAG, "Camera is already opened")
                    return
                }
                openCamera()
            }
        }, 0, 5000)
    }

    fun stopCapturing() {
        closeCamera()
    }

    fun setNeedCapturing(needCapturing: Boolean) {
        this.needCapturing = needCapturing
    }

    @SuppressLint("MissingPermission")
    private fun openCamera() {
        try {
            val cameraIdList: Array<String> = manager.cameraIdList
            if (cameraIdList.isNotEmpty()) {
                manager.openCamera(cameraIdList[0], stateCallback, Handler(Looper.getMainLooper()))
            } else {
                Log.e(TAG, "Camera Not Found")
            }
        } catch (e: CameraAccessException) {
            Log.e(TAG, "CameraAccessException: ", e)
        }
    }


    private fun closeCamera() {
        cameraOpened = false
        if (null != cameraDevice) {
            Log.i(TAG, "Closing Camera: " + cameraDevice!!.id)
            cameraDevice!!.close()
            cameraDevice = null
        }
        capturingExecutor.shutdown()
    }


    private val stateCallback: CameraDevice.StateCallback = object : CameraDevice.StateCallback() {
        override fun onOpened(camera: CameraDevice) {
            cameraOpened = true
            cameraDevice = camera
            Log.i(TAG, "Camera Opened: " + camera.id)
            capturingExecutor = Executors.newSingleThreadScheduledExecutor()
            capturingExecutor.schedule(
                {
                    try {
                        Log.i(TAG, "Capturing Image")
                        takePicture()
                    } catch (e: CameraAccessException) {
                        Log.e(TAG, "CameraAccessException: ", e)
                    }
                }, 500, java.util.concurrent.TimeUnit.MILLISECONDS
            )
        }

        override fun onDisconnected(camera: CameraDevice) {
            Log.i(TAG, "Camera Disconnected: " + camera.id)
            closeCamera()
        }

        override fun onClosed(camera: CameraDevice) {
            Log.i(TAG, "Camera Closed: " + camera.id)
            closeCamera()
        }

        override fun onError(camera: CameraDevice, error: Int) {
            Log.e(TAG, "Camera Error: $error")
            closeCamera()
        }
    }

    private fun takePicture() {
        val characteristics: CameraCharacteristics =
            manager.getCameraCharacteristics(cameraDevice!!.id)
        val streamConfigurationMap =
            characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
        streamConfigurationMap?.getOutputSizes(ImageFormat.JPEG)

        val imageReader: ImageReader = ImageReader.newInstance(1080, 1920, ImageFormat.JPEG, 1)
        val outputSurfaces: MutableList<Surface> = ArrayList()
        outputSurfaces.add(imageReader.surface)

        val captureBuilder =
            cameraDevice!!.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE)
        captureBuilder.addTarget(imageReader.surface)
        captureBuilder.set(
            CaptureRequest.CONTROL_AF_MODE,
            CameraMetadata.CONTROL_AF_MODE_CONTINUOUS_PICTURE
        )
        captureBuilder.set(CaptureRequest.CONTROL_MODE, CameraMetadata.CONTROL_MODE_AUTO)
        captureBuilder.set(CaptureRequest.CONTROL_AE_MODE, CameraMetadata.CONTROL_AE_MODE_ON)
//        captureBuilder.set(CaptureRequest.CONTROL_AE_LOCK, true)
        captureBuilder.set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range.create(5, 30))
        captureBuilder.set(CaptureRequest.CONTROL_AWB_MODE, CameraMetadata.CONTROL_AWB_MODE_AUTO)
//        captureBuilder.set(CaptureRequest.JPEG_ORIENTATION, Surface.ROTATION_90)
        imageReader.setOnImageAvailableListener(
            onImageAvailableListener,
            Handler(Looper.getMainLooper())
        )

        cameraDevice!!.createCaptureSession(
            outputSurfaces, object : CameraCaptureSession.StateCallback() {
                override fun onConfigured(session: CameraCaptureSession) {
                    try {
                        session.capture(
                            captureBuilder.build(),
                            captureListener,
                            Handler(Looper.getMainLooper())
                        )
                    } catch (e: CameraAccessException) {
                        Log.e(TAG, "CameraAccessException: ", e)
                    }
                }

                override fun onConfigureFailed(session: CameraCaptureSession) {
                    Log.e(TAG, "CameraCaptureSession Configure Failed")
                    closeCamera()
                }
            }, Handler(Looper.getMainLooper())
        )
    }
}