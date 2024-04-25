package life.memx.chat.services

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import com.jiangdg.ausbc.MultiCameraClient
import com.jiangdg.ausbc.base.CameraFragment
import com.jiangdg.ausbc.callback.ICameraStateCallBack
import com.jiangdg.ausbc.callback.ICaptureCallBack
import com.jiangdg.ausbc.camera.bean.CameraRequest
import com.jiangdg.ausbc.render.env.RotateType
import com.jiangdg.ausbc.utils.Logger
import com.jiangdg.ausbc.utils.ToastUtils
import com.jiangdg.ausbc.widget.AspectRatioTextureView
import com.jiangdg.ausbc.widget.IAspectRatio
import life.memx.chat.databinding.FragmentDemoBinding
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.Queue

class ExCamFragment internal constructor(
    var queue: Queue<ByteArray>
) : CameraFragment() {

//    private var mCameraMode = CaptureMediaView.CaptureMode.MODE_CAPTURE_PIC

    private lateinit var mViewBinding: FragmentDemoBinding
    private var needCapturing = true
    private lateinit var cacheDir: String
    private val rotate = 270 // TODO


    fun startCapturing() {

        val handler = Handler(Looper.getMainLooper())

        val runTask: Runnable = object : Runnable {
            override fun run() {
                handler.postDelayed(this, 10000) // Photo interval
                if (!needCapturing) {
                    Log.i(TAG, "Don't need capturing")
                    return
                }
                if (!isCameraOpened()) {
                    initView()
                }
                captureImage()

            }
        }
        handler.post(runTask)
    }

    fun setNeedCapturing(b: Boolean) {
        needCapturing = b
    }

    fun stopCapturing() {
        closeCamera()
    }


    override fun initView() {
        unRegisterMultiCamera()

        registerMultiCamera()

        super.initView()
        Logger.i(
            TAG,
            "initView, cams = ${getDeviceList()}"
        )
        Logger.i(TAG, "getDefaultCamera(): ${getDefaultCamera()}")


        cacheDir = requireContext().cacheDir.absolutePath
    }

    override fun initData() {
        super.initData()

    }

    override fun onCameraState(
        self: MultiCameraClient.ICamera,
        code: ICameraStateCallBack.State,
        msg: String?
    ) {
        Logger.w(
            TAG,
            "onCameraState: $code"
        )
        when (code) {
            ICameraStateCallBack.State.OPENED -> handleCameraOpened()
            ICameraStateCallBack.State.CLOSED -> handleCameraClosed()
            ICameraStateCallBack.State.ERROR -> handleCameraError(msg)
        }
    }

    private fun handleCameraError(msg: String?) {
        Logger.e(
            TAG,
            "camera opened error: $msg"
        )
        ToastUtils.show("camera opened error: $msg")
    }

    private fun handleCameraClosed() {
//        ToastUtils.show("camera closed success")
    }

    private fun handleCameraOpened() {

//        mViewBinding.brightnessSb.progress =
//            (getCurrentCamera() as? CameraUVC)?.getBrightness() ?: 0
//        Logger.i(
//            TAG,
//            "max = ${mViewBinding.brightnessSb.max}, progress = ${mViewBinding.brightnessSb.progress}"
//        )
//        mViewBinding.brightnessSb.setOnSeekBarChangeListener(object :
//            SeekBar.OnSeekBarChangeListener {
//            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
//                (getCurrentCamera() as? CameraUVC)?.setBrightness(progress)
//            }
//
//            override fun onStartTrackingTouch(seekBar: SeekBar?) {
//
//            }
//
//            override fun onStopTrackingTouch(seekBar: SeekBar?) {
//
//            }
//        })
//        ToastUtils.show("camera opened success")
    }


    override fun getCameraView(): IAspectRatio {
        return AspectRatioTextureView(requireContext())
    }

    override fun getCameraViewContainer(): ViewGroup {
        return mViewBinding.cameraViewContainer
    }

    override fun getRootView(inflater: LayoutInflater, container: ViewGroup?): View {
        mViewBinding = FragmentDemoBinding.inflate(inflater, container, false)
        return mViewBinding.root
    }

    override fun getGravity(): Int = Gravity.CENTER

    private fun uploadImage(img_path: String) {
        if (rotate != 0) {
            val sourceBitmap = BitmapFactory.decodeFile(img_path)
            val matrix = Matrix()
            matrix.postRotate(rotate.toFloat())
//            matrix.postScale(-1.0f, 1.0f)
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
            val bytes = File(img_path).readBytes()
            queue.add(bytes)
        }

    }
    override fun getCameraRequest(): CameraRequest {
        return CameraRequest.Builder()
            .setPreviewWidth(640) // camera preview width
            .setPreviewHeight(640) // camera preview height
            .setRenderMode(CameraRequest.RenderMode.OPENGL) // camera render mode
            .setDefaultRotateType(RotateType.ANGLE_180) // rotate camera image when opengl mode
            .create()
    }
    private fun captureImage() {
        val savePath = cacheDir + System.currentTimeMillis().toString() + ".jpg"
        captureImage(object : ICaptureCallBack {
            override fun onBegin() {
//                mTakePictureTipView.show("", 100)
            }

            override fun onError(error: String?) {
                Logger.e(TAG, error ?: "unknown error")
                ToastUtils.show(error ?: "unknown error")
            }

            override fun onComplete(path: String?) {
                if (path != null) {
                    uploadImage(path)
                }
                closeCamera()
            }
        }, savePath = savePath)
    }

    override fun onDestroyView() {
        super.onDestroyView()
    }


    companion object {
        private const val TAG = "DemoFragment"
    }
}


