package life.memx.chat.services

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.hardware.usb.UsbDevice
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.recyclerview.widget.GridLayoutManager
import com.chad.library.adapter.base.BaseQuickAdapter
import com.chad.library.adapter.base.BaseViewHolder
import com.jiangdg.ausbc.MultiCameraClient
import com.jiangdg.ausbc.base.MultiCameraFragment
import com.jiangdg.ausbc.callback.ICameraStateCallBack
import com.jiangdg.ausbc.callback.ICaptureCallBack
import com.jiangdg.ausbc.camera.CameraUVC
import com.jiangdg.ausbc.camera.bean.CameraRequest
import com.jiangdg.ausbc.utils.Logger
import com.jiangdg.ausbc.utils.ToastUtils
import life.memx.chat.R
import life.memx.chat.databinding.FragmentMultiCameraBinding
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.Queue

/** Multi-road camera demo
 *
 * @author Created by jiangdg on 2022/7/20
 */
class MultiCameraFragment internal constructor(
    var scene_queue: Queue<ByteArray>, var eye_queue: Queue<ByteArray>
) : MultiCameraFragment(), ICameraStateCallBack {

    private var needCapturing = true
    private lateinit var cacheDir: String
    private val rotate = 90 // TODO

    private lateinit var mAdapter: CameraAdapter
    private lateinit var mViewBinding: FragmentMultiCameraBinding
    private val mCameraList by lazy {
        ArrayList<MultiCameraClient.ICamera>()
    }
    private val mHasRequestPermissionList by lazy {
        ArrayList<MultiCameraClient.ICamera>()
    }

    fun startCapturing() {


        val handler = Handler(Looper.getMainLooper())

        val sceneTask: Runnable = object : Runnable {
            override fun run() {
                handler.postDelayed(this, 10000) // scene_cam Photo interval
                if (!needCapturing) {
                    Log.i(TAG, "Don't need capturing")
                    return
                }
                captureImage(eye = false)

            }
        }
        handler.post(sceneTask)

        val eyeTask: Runnable = object : Runnable {
            override fun run() {
                handler.postDelayed(this, 1000) // eye_cam Photo interval
                if (!needCapturing) {
                    Log.i(TAG, "Don't need capturing")
                    return
                }
                captureImage(eye = true)

            }
        }
        handler.post(eyeTask)
    }

    fun setNeedCapturing(b: Boolean) {
        needCapturing = b
    }

    fun stopCapturing() {
        needCapturing = false
    }

    fun openAllCams() {
        mAdapter.data.forEach { cam ->
            cam.openCamera(null, getCameraRequest())
        }
    }

    override fun onCameraAttached(camera: MultiCameraClient.ICamera) {
        Logger.i(TAG, "onCameraAttached: ${camera.toString()}")
        mAdapter.data.add(camera)
        mAdapter.notifyItemInserted(mAdapter.data.size - 1)
        mViewBinding.multiCameraTip.visibility = View.GONE
    }

    override fun onCameraDetached(camera: MultiCameraClient.ICamera) {
        mHasRequestPermissionList.remove(camera)
        for ((position, cam) in mAdapter.data.withIndex()) {
            if (cam.getUsbDevice().deviceId == camera.getUsbDevice().deviceId) {
                camera.closeCamera()
                mAdapter.data.removeAt(position)
                mAdapter.notifyItemRemoved(position)
                break
            }
        }
        if (mAdapter.data.isEmpty()) {
            mViewBinding.multiCameraTip.visibility = View.VISIBLE
        }
    }

    override fun generateCamera(ctx: Context, device: UsbDevice): MultiCameraClient.ICamera {
        return CameraUVC(ctx, device)
    }

    override fun onCameraConnected(camera: MultiCameraClient.ICamera) {
        for ((position, cam) in mAdapter.data.withIndex()) {
            if (cam.getUsbDevice().deviceId == camera.getUsbDevice().deviceId) {
                val textureView =
                    mAdapter.getViewByPosition(position, R.id.multi_camera_texture_view)
                cam.openCamera(textureView, getCameraRequest())
                cam.setCameraStateCallBack(this)
                break
            }
        }
        // request permission for other camera
        mAdapter.data.forEach { cam ->
            val device = cam.getUsbDevice()
            if (!hasPermission(device)) {
                mHasRequestPermissionList.add(cam)
                requestPermission(device)
                return@forEach
            }
        }
    }

    override fun onCameraDisConnected(camera: MultiCameraClient.ICamera) {
        camera.closeCamera()
    }


    override fun onCameraState(
        self: MultiCameraClient.ICamera,
        code: ICameraStateCallBack.State,
        msg: String?
    ) {
        if (code == ICameraStateCallBack.State.ERROR) {
            ToastUtils.show(msg ?: "open camera failed.")
        }
        for ((position, cam) in mAdapter.data.withIndex()) {
            if (cam.getUsbDevice().deviceId == self.getUsbDevice().deviceId) {
                mAdapter.notifyItemChanged(position, "switch")
                break
            }
        }
    }


    override fun initView() {
        super.initView()

//        openDebug(true)
        mAdapter = CameraAdapter()
        mAdapter.setNewData(mCameraList)
        mAdapter.bindToRecyclerView(mViewBinding.multiCameraRv)
        mViewBinding.multiCameraRv.adapter = mAdapter
        mViewBinding.multiCameraRv.layoutManager = GridLayoutManager(requireContext(), 2)

        cacheDir = requireContext().cacheDir.absolutePath

    }

    override fun getRootView(inflater: LayoutInflater, container: ViewGroup?): View {
        mViewBinding = FragmentMultiCameraBinding.inflate(inflater, container, false)
        return mViewBinding.root
    }

    private fun getCameraRequest(): CameraRequest {
        return CameraRequest.Builder()  // TODO: set resolution
//            .setPreviewWidth(640)
//            .setPreviewHeight(480)
            .create()
    }

    inner class CameraAdapter :
        BaseQuickAdapter<MultiCameraClient.ICamera, BaseViewHolder>(R.layout.layout_item_camera) {
        override fun convert(helper: BaseViewHolder, camera: MultiCameraClient.ICamera?) {}

        override fun convertPayloads(
            helper: BaseViewHolder,
            camera: MultiCameraClient.ICamera?,
            payloads: MutableList<Any>
        ) {
            camera ?: return
            if (payloads.isEmpty()) {
                return
            }
            helper.setText(R.id.multi_camera_name, "${camera.device.productId}")
//            helper.addOnClickListener(R.id.multi_camera_capture_image)

        }
    }

    private fun getCamera(eye: Boolean): MultiCameraClient.ICamera? {
        val deviceIds = ArrayList<Int>()
        for (camera in mAdapter.data) {
            deviceIds.add(camera.device.deviceId)
        }
        if (deviceIds.size == 0) {
            return null
        }
        val deviceId = if (eye) deviceIds.max() else deviceIds.min()

        for (camera in mAdapter.data) {
            if (camera.device.deviceId == deviceId) {
                return camera
            }
        }

        return null
    }

    private fun uploadImage(img_path: String, eye: Boolean) {
        val queue = if (eye) eye_queue else scene_queue
        if (rotate != 0) {
            val sourceBitmap = BitmapFactory.decodeFile(img_path)
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
            val bytes = File(img_path).readBytes()
            queue.add(bytes)
        }

    }


    private fun captureImage(eye: Boolean) {
        val savePath = cacheDir + System.currentTimeMillis().toString() + ".jpg"

        val camera = getCamera(eye)

        camera?.captureImage(object : ICaptureCallBack {
            override fun onBegin() {}

            override fun onError(error: String?) {
                ToastUtils.show(error ?: "capture image failed")
            }

            override fun onComplete(path: String?) {
//                ToastUtils.show("capture image success, eye=${eye}")
                if (path != null) {
                    uploadImage(path, eye)
                }
            }
        }, path = savePath)


    }

    companion object {
        private const val TAG = "MultiCameraFragment"
    }
}