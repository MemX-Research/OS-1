package life.memx.chat


import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.pm.PackageManager
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.text.Html
import android.text.Spanned
import android.util.Log
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.view.inputmethod.InputMethodManager
import android.widget.AdapterView
import android.widget.Button
import android.widget.EditText
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import androidx.annotation.RequiresApi
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.databinding.DataBindingUtil
import androidx.drawerlayout.widget.DrawerLayout
import androidx.lifecycle.ViewModelProvider
import com.alibaba.idst.nui.AsrResult
import com.alibaba.idst.nui.Constants
import com.alibaba.idst.nui.INativeFileTransCallback
import com.jiangdg.ausbc.utils.ToastUtils
import com.jiangdg.ausbc.utils.Utils
import edu.cmu.pocketsphinx.Assets;
import edu.cmu.pocketsphinx.Hypothesis;
import edu.cmu.pocketsphinx.SpeechRecognizer;
import edu.cmu.pocketsphinx.SpeechRecognizerSetup;
import life.memx.chat.services.CameraXService
//import com.konovalov.vad.silero.config.SampleRate.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import life.memx.chat.databinding.ActivityMainBinding
import life.memx.chat.services.AudioRecording
import life.memx.chat.services.AliAsrRecorder
import life.memx.chat.utils.NetUtils
import life.memx.chat.utils.TimerUtil
import life.memx.chat.view.PerformanceMonitorViewModel
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.File
import java.io.IOException
import java.io.InputStreamReader
import java.nio.file.Files
import java.nio.file.Paths
import java.util.LinkedList
import java.util.Queue
import java.util.Timer
import java.util.TimerTask
import java.util.concurrent.TimeUnit


class MainActivity : AppCompatActivity(){

    private val TAG: String = MainActivity::class.java.simpleName
    private var netUtils: NetUtils? = null
    private var dlContainer: DrawerLayout? = null
    private var uid: String = ""


    private var server_url: String = "https://your_server_url.com"   // TODO: DEFAULT SERVER URL

    private var is_first = true

    private val PERMISSIONS_REQUIRED: Array<String> = arrayOf<String>(
        Manifest.permission.READ_EXTERNAL_STORAGE,
        Manifest.permission.WRITE_EXTERNAL_STORAGE,
        Manifest.permission.MANAGE_EXTERNAL_STORAGE,
        Manifest.permission.CAMERA,
        Manifest.permission.RECORD_AUDIO
    )
    private lateinit var viewBinding: ActivityMainBinding
    private lateinit var performanceMonitorView: PerformanceMonitorViewModel
    private lateinit var pullResponseJob: Job   // this is used to handle pullResponse task
    private var tempFilePath = Environment.getExternalStorageDirectory().path.toString() +
            "/Android/data/life.memx.chat/"     // This is used to store temp files

    companion object {
        // Permission codes
        private const val PERMISSIONS_REQUEST_CODE = 10
        private const val REQUEST_CAMERA = 0
        private const val REQUEST_STORAGE = 1
        private const val TIMER_SERVER_PROCESSING = 1

        // The message types shown in the state TextView
        private const val LOGMSG = 0
        private const val INFOMSG = 1
        private const val ERRMSG = 2
    }

    private var mWakeLock: PowerManager.WakeLock? = null

    private var audioQueue: Queue<ByteArray> = LinkedList<ByteArray>()
    private var imageQueue: Queue<ByteArray> = LinkedList<ByteArray>()
    private var eyeImageQueue: Queue<ByteArray> = LinkedList<ByteArray>()

    private var voiceQueue: Queue<String> = LinkedList<String>()

    @Volatile
    private var audio: StringBuilder = StringBuilder()

    private var audioRecorder = AudioRecording(audioQueue, this)
    private var mediaPlayer = MediaPlayer()
    private var aliRecorder = AliAsrRecorder(this, server_url, object: INativeFileTransCallback {
        override fun onFileTransEventCallback(
            event: Constants.NuiEvent,
            resultCode: Int,
            finish: Int,
            asrResult: AsrResult,
            taskId: String
        ) {
            if (event == Constants.NuiEvent.EVENT_FILE_TRANS_UPLOADED) {
                Log.d("ali sdk", "Upload finished")
            } else if (event == Constants.NuiEvent.EVENT_FILE_TRANS_RESULT) {
                Log.d("ali sdk", asrResult.asrResult)
                val results = JSONObject(asrResult.asrResult)
                              .getJSONObject("flash_result")
                              .get("sentences") as JSONArray
                setStateText("Ali ASR: "+results.getJSONObject(0).get("text") as String, true, INFOMSG)
                for (i in 0 until results.length()){
                    if (isInterruptKeyword(results.getJSONObject(i).get("text") as String)){
                        handleInterrupt("ok")
                        break
                    }
                }
            } else if (event == Constants.NuiEvent.EVENT_ASR_ERROR) {
                if (resultCode == 240067) {
                    setStateText("Ali disconnected!", true, ERRMSG)
                } else if (resultCode==240075){
                    val errMsg = JSONObject(asrResult.asrResult).get("message")
                    setStateText(errMsg.toString(), true, INFOMSG)
                }
                Log.e("ali sdk", "error $resultCode")
            }
        }
    })

    private var imageCapturer = CameraXService(imageQueue, this)


    private var cameraSwitch: Switch? = null
    private var audioSwitch: Switch? = null
    private var userText: EditText? = null
    private var serverSpinner: Spinner? = null

    private var responseText: TextView? = null
    private var responseScroll: ScrollView? = null
    private var userTextBtn: Button? = null
    private var responseQueue: Queue<String> = LinkedList<String>()
    private var stateQueue: Queue<String> = LinkedList<String>()

    private lateinit var speechRecognizer: SpeechRecognizer
    private var isListening = false     // whether the SpeechRecognizer is listening to interruption
    private var isInterrupted = false   // whether the interruption is detected
    private var updateUrl = false       // whether need to update the url for long http connection
    private var currentResId: String = "no response"    // the current response id
    private var banResId: String = "no ban"     // the banned response id, which will not be played

    private lateinit var audioManager: AudioManager
    private val timerUtil = TimerUtil()

    private val mRecognizerListener: edu.cmu.pocketsphinx.RecognitionListener = object :
        edu.cmu.pocketsphinx.RecognitionListener {
        override fun onBeginningOfSpeech() {
            aliRecorder.startRecord()
            setStateText("State: Speech Begin", true)
        }

        override fun onEndOfSpeech() {
//            aliRecorder.stopRecord()
            setStateText("State: Speech End", true)
        }

        override fun onPartialResult(hypothesis: Hypothesis?) {
//            speechRecognizer.cancel()
//            speechRecognizer.startListening("HOT_WORD_SEARCH")
            if (hypothesis == null) {
                return
            }
            val text = hypothesis.hypstr
            Log.d(
                TAG, String.format(
                    "onPartialResult: hypothesis string: %s, prob=[%d], bestScore=[%d]",
                    text, hypothesis.prob, hypothesis.bestScore
                )
            )
//            setStateText("State: detected: $text", true, INFOMSG)
            if (text.contains("ok") && isListening) {
//                setStateText("sphinx detected", true, INFOMSG)
                speechRecognizer.cancel()
                speechRecognizer.startListening("HOT_WORD_SEARCH")
//                handleInterrupt(text)
            } else {
                Log.e(TAG, "onPartialResult: unexpected hypothesis string: $text")
                if (text.contains("ok") && isListening) {
//                    handleInterrupt(text)
                    // TODO currently we shutdown after this but it might be necessary to cancel
                    //  when later we don't
                    // mRecognizer.cancel();
                }
            }
        }

        override fun onResult(hypothesis: Hypothesis?) {
            if (hypothesis == null) {
                Log.e(TAG, "on Result: null")
                return
            }
            Log.d(TAG, "on Result: " + hypothesis.hypstr + " : " + hypothesis.bestScore)
        }

        override fun onError(e: Exception) {
            Log.e(TAG, "onError()", e)
        }

        override fun onTimeout() {
            Log.d(TAG, "onTimeout()")
        }
    }

    private fun handleInterrupt(text: String) {
        setStateText("Interrupt detected: $text", true, INFOMSG)
        isListening = false
//        speechRecognizer.cancel()
        // send a message to the server to interrupt GPT-4 from generating the response
        var url = "$server_url/interrupt/$uid"
        val client = OkHttpClient()
        val request = Request.Builder().url(url).build()
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e(TAG, "Update interruption state error")
            }
            override fun onResponse(call: Call, response: Response) {}
        })
        try {
            if (mediaPlayer != null) {
                if (mediaPlayer.isPlaying){
                    mediaPlayer.stop()
                }
            }
        } catch (e: Exception) {
            Log.e("Handle interruption", "Exception: $e")
        }

        voiceQueue.clear()
        if (currentResId != "no response"){
            // prevent current message id to be played
            banResId = currentResId
//            setStateText("banning: $banResId", true)
        }
        isListening = true
//        speechRecognizer.startListening("HOT_WORD_SEARCH")
    }

    @RequiresApi(Build.VERSION_CODES.S)
    private fun useBuiltinSpeaker() {
        val devices = audioManager.availableCommunicationDevices
        for (device in devices) {
            if (device.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER) {
                audioManager.setCommunicationDevice(device)
                Toast.makeText(
                    applicationContext, "Use Builtin Speaker", Toast.LENGTH_SHORT
                ).show()
            }
        }
    }

    @RequiresApi(Build.VERSION_CODES.S)
    fun registerAudioManagerListener() {
        audioManager.registerAudioDeviceCallback(object : AudioDeviceCallback() {
            override fun onAudioDevicesAdded(addedDevices: Array<AudioDeviceInfo>) {
                super.onAudioDevicesAdded(addedDevices)
                for (device in addedDevices) {
                    if (device in audioManager.availableCommunicationDevices &&
                        device.type != AudioDeviceInfo.TYPE_BUILTIN_EARPIECE && device.type != AudioDeviceInfo.TYPE_BUILTIN_SPEAKER
                    ) {
                        audioManager.setCommunicationDevice(device)
                        Log.i(
                            TAG,
                            "audioManager add device: ${device.type} ${device.productName}"
                        )
                        val deviceName = if (device.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO) {
                            "Bluetooth Headset"
                        } else if (device.type == AudioDeviceInfo.TYPE_WIRED_HEADSET) {
                            "Wired Headset"
                        } else {
                            "Device${device.type}"
                        }
                        Toast.makeText(
                            applicationContext,
                            "$deviceName Connected",
                            Toast.LENGTH_LONG
                        ).show()
                    }
                }
            }

            override fun onAudioDevicesRemoved(removedDevices: Array<AudioDeviceInfo>) {
                super.onAudioDevicesRemoved(removedDevices)
                Log.w(TAG, "audioManager onAudioDevicesRemoved: $removedDevices")
                for (device in removedDevices) {
                    Log.w(TAG, "audioManager remove device: ${device.type} ${device.productName}")
                }
                useBuiltinSpeaker()
            }
        }, null)
    }

    private fun verifyPermissions(activity: Activity) = PERMISSIONS_REQUIRED.all {
        ActivityCompat.checkSelfPermission(activity, it) == PackageManager.PERMISSION_GRANTED
    }

    @RequiresApi(Build.VERSION_CODES.S)
    @SuppressLint("HardwareIds")

    override fun onCreate(savedInstanceState: Bundle?) {

        super.onCreate(savedInstanceState)
        viewBinding = DataBindingUtil.setContentView(this, R.layout.activity_main)
        viewBinding.lifecycleOwner = this


        // init UI
        uid = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID)
        val sharedPreferences = getSharedPreferences("data", MODE_PRIVATE)
        uid = sharedPreferences.getString("uid", uid).toString()

        registerUserText()
        registerCameraSwitch()
        registerAudioSwitch()
        registerServerSpinner()
        registerPerformanceMonitor()

//        replaceDemoFragment(DemoMultiCameraFragment())
//        replaceDemoFragment(imageCapturer)

        netUtils = NetUtils(this@MainActivity)
        dlContainer = findViewById(R.id.dlContainer)
        var chatlogText: EditText = findViewById(R.id.chatLogText)
        chatlogText.keyListener = null

        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        deleteCache()

        Log.i(TAG, "uid: $uid")

        if (!verifyPermissions(this)) {
            ActivityCompat.requestPermissions(
                this, PERMISSIONS_REQUIRED, PERMISSIONS_REQUEST_CODE
            )
        } else {
            run()
        }

        ToastUtils.init(this)

//        audioManager = getSystemService(AUDIO_SERVICE) as AudioManager
//        useBuiltinSpeaker()
//        registerAudioManagerListener()

        netUtils?.setDelayTime(0)?.setRecyclerTime(300)?.start(findViewById(R.id.tvNetSpeed))//Network
    }

//    private fun replaceDemoFragment(fragment: Fragment) {
//        val transaction = supportFragmentManager.beginTransaction()
//        transaction.replace(R.id.fragment_container, fragment)
//        transaction.commitAllowingStateLoss()
//    }

    private fun isInterruptKeyword(input: String): Boolean {
        val lowercaseInput = input.lowercase()
//        val keywords = listOf("stop", "ok", "yes", "no", "yeah", "yep")
        val keywords = listOf("ok")

        for (keyword in keywords) {
            if (lowercaseInput.contains(keyword.lowercase())) {
                return true
            }
        }
        return false
    }

    private fun registerCameraSwitch() {
        cameraSwitch = findViewById(R.id.camera_switch)
        cameraSwitch?.setOnCheckedChangeListener { _, isChecked ->
            try {
                if (isChecked) {
                    imageCapturer.setNeedCapturing(true)
                    Log.d(TAG, "setNeedCapturing: true")
                    Toast.makeText(
                        applicationContext, "open camera", Toast.LENGTH_SHORT
                    ).show();
                } else {
//                    imageCapturer.stopCapturing()
                    imageCapturer.setNeedCapturing(false)
                    Log.d(TAG, "setNeedCapturing: false")
                    Toast.makeText(
                        applicationContext, "close camera", Toast.LENGTH_SHORT
                    ).show();
                }
            } catch (e: Exception) {
                Log.e(TAG, "set camera error: $e")
                Toast.makeText(
                    applicationContext, "set camera error: $e", Toast.LENGTH_LONG
                ).show();
            }
        }
    }


    private fun registerAudioSwitch() {
        audioSwitch = findViewById(R.id.audio_switch)
        audioSwitch?.setOnCheckedChangeListener { _, isChecked ->
            try {
                if (isChecked) {
                    audioRecorder.setNeedRecording(true)
                    audioRecorder.startRecording()
                    Log.d(TAG, "setNeedRecording: true")
                    setStateText("State: Waiting for voice.", true)
                    Toast.makeText(
                        applicationContext, "open audio", Toast.LENGTH_SHORT
                    ).show();
                } else {
                    audioRecorder.setNeedRecording(false)
                    audioRecorder.stopRecording()
                    Log.d(TAG, "setNeedRecording: false")
                    setStateText("State: stop recording audio.", true)
                    Toast.makeText(
                        applicationContext, "close audio", Toast.LENGTH_SHORT
                    ).show();
                }
            } catch (e: Exception) {
                Log.e(TAG, "set audio error: $e")
                Toast.makeText(
                    applicationContext, "set audio error: $e", Toast.LENGTH_LONG
                ).show();
            }
        }
    }

    private fun registerUserText() {
        userText = findViewById(R.id.user_text)
        userText?.setText(uid)
        userTextBtn = findViewById(R.id.upload_user_text)
        userTextBtn?.setOnClickListener {
            try {
                val text = userText?.text.toString()
                if (text.isNotEmpty()) {
                    Log.d(TAG, "user text: $text")
                    uid = text
                    val sharedPreferences = getSharedPreferences("data", MODE_PRIVATE)
                    val editor = sharedPreferences.edit()
                    editor.putString("uid", uid)
                    editor.commit()
                    Toast.makeText(applicationContext, "Set user: $text", Toast.LENGTH_SHORT)
                        .show();
                    // restart pull response loop
                    if (this::pullResponseJob.isInitialized) {
                        pullResponseJob.cancel()
                        pullResponseJob = GlobalScope.launch {
                            pullResponseLoop()
                        }
                        Log.i("Stream", "Update url: $updateUrl")
                    }
                } else {
                    Log.d(TAG, "user text is empty")
                    Toast.makeText(
                        applicationContext, "The user cannot be set to empty", Toast.LENGTH_SHORT
                    ).show();
                }
                // hide keyboard
                val imm = getSystemService(INPUT_METHOD_SERVICE) as? InputMethodManager
                imm?.hideSoftInputFromWindow(userText?.windowToken, 0)
            } catch (e: Exception) {
                Log.e(TAG, "set user text error: $e")
                Toast.makeText(
                    applicationContext, "set user text error: $e", Toast.LENGTH_LONG
                ).show();
            }
        }

        viewBinding.outerContainer.setOnClickListener { v ->
            val imm = getSystemService(INPUT_METHOD_SERVICE) as? InputMethodManager
            imm?.hideSoftInputFromWindow(v?.windowToken, 0)
        }
    }

    private fun registerPerformanceMonitor() {
        performanceMonitorView = ViewModelProvider(this)[PerformanceMonitorViewModel::class.java]
        viewBinding.performanceMonitor = performanceMonitorView
        performanceMonitorView.reset()
    }

    private fun registerServerSpinner() {
        serverSpinner = findViewById(R.id.server_spinner)
        serverSpinner?.setOnItemSelectedListener(object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, pos: Int, id: Long) {
                try {
                    val server_ips = resources.getStringArray(R.array.server_ips)
                    server_url = server_ips[pos]
                    aliRecorder.setServerUrl(server_url)
                    Toast.makeText(applicationContext, "server: $server_url", Toast.LENGTH_SHORT)
                        .show();
                    // restart pull response loop
                    if (this@MainActivity::pullResponseJob.isInitialized) {
                        pullResponseJob.cancel()
                        pullResponseJob = GlobalScope.launch {
                            pullResponseLoop()
                        }
                    }
                    Log.i("Stream", "Update url: $updateUrl")
                } catch (e: Exception) {
                    Log.e(TAG, "set url error: $e")
                    Toast.makeText(
                        applicationContext, "set url error: $e", Toast.LENGTH_LONG
                    ).show();
                }
            }

            override fun onNothingSelected(parent: AdapterView<*>?) {
                // Another interface callback
            }
        })
    }

    private fun setStateText(text: String, append: Boolean = false, type: Int = LOGMSG) {
        // Set color of the string according to message type
        var htmlText: String = ""
        when (type) {
            INFOMSG -> htmlText = "<font color='yellow'>$text</font>"
            ERRMSG -> htmlText = "<font color='red'>$text</font>"
            LOGMSG -> htmlText = text
            else -> {
                htmlText = text
                Log.e(TAG, "message type not allowed!")
            }
        }

        // Decide whether to append msg or clear the state window
        val stateText: TextView? = findViewById(R.id.state_text)
        val stateScroll: ScrollView? = findViewById(R.id.state_scroll)
        if (append) {
            stateQueue.add(htmlText)
        } else {
            stateQueue.clear()
            stateQueue.add(htmlText)
        }

        // Concat all the html texts and show the state
        var displaySpan: Spanned
        var displayText = ""
        if (stateQueue.size >= 30) {
            stateQueue.remove()
        }
        for (item in stateQueue) {
            displayText += "$item<br>"
        }
        displaySpan = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            Html.fromHtml(displayText, Html.FROM_HTML_MODE_LEGACY);
        } else {
            Html.fromHtml(displayText);
        }
        runOnUiThread { stateText?.setText(displaySpan) }
        stateScroll?.fullScroll(View.FOCUS_DOWN)
    }

    private fun setResponseText(text: String) {
        responseText = findViewById(R.id.response_text)
        responseScroll = findViewById(R.id.response_scroll)
        responseQueue.add(text)

        if (responseQueue.size >= 30) {
            responseQueue.remove()
        }

        var display_text = ""
        for (item in responseQueue) {
            if (item.startsWith("<User>")) {
                Log.e("display string", item)
                display_text += "<font color='#FF9900' weight='600'>User: </font>"+
                                item.substring(7)+"<br>"
            } else {
                display_text += "$item<br>"
            }
        }
        var displaySpan: Spanned
        displaySpan = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            Html.fromHtml(display_text, Html.FROM_HTML_MODE_LEGACY);
        } else {
            Html.fromHtml(display_text);
        }
        runOnUiThread { responseText?.setText(displaySpan) }
        responseScroll?.fullScroll(View.FOCUS_DOWN)
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERMISSIONS_REQUEST_CODE) {
            Log.w(TAG, "onRequestPermissionsResult ${grantResults.size}")
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                run()
            } else {
                Log.e(TAG, "Permission Denied");
            }
        }
    }

    override fun onStart() {
        super.onStart()
        mWakeLock = Utils.wakeLock(this)
    }

    override fun onStop() {
        super.onStop()
        mWakeLock?.apply {
            Utils.wakeUnLock(this)
        }
//        audioRecorder.stopRecording()
//        imageCapturer.stopCapturing()
//        setStateText("State: stop recording audio.", true)
        setStateText("State: stop event triggered.", true)
    }


    private fun run() {
        imageCapturer.startCapturing()
        imageCapturer.setImageSize(640, 480) //TODO: set image size
        aliRecorder.getTokenThenInitAliSDK()    // fetch token and setup ali sdk
        aliRecorder.initRecorder()              // setup AudioRecorder and start recording
        audioRecorder.startRecording()

        // Initialize Sphinx speechRecognizer, it will keep listening all the time
        val assets = Assets(application)
        val assetsDir = assets.syncAssets()
        speechRecognizer = SpeechRecognizerSetup.defaultSetup()
            .setAcousticModel(File(assetsDir, "models/en-us-ptm-8khz"))
            .setDictionary(File(assetsDir, "models/lm/words.dic"))
            .setKeywordThreshold(1.0E-10F) // set lower to make 'stop' easier to be detected
            .setSampleRate(8000)
            .recognizer
        speechRecognizer.addKeyphraseSearch("HOT_WORD_SEARCH", "ok")
        speechRecognizer.addListener(mRecognizerListener)
        if (speechRecognizer == null) {
            Toast.makeText(
                applicationContext,
                "No speech recognition service in this device, interruption disabled",
                Toast.LENGTH_LONG
            ).show();
        }
        isListening = true
        speechRecognizer.startListening("HOT_WORD_SEARCH")
        setStateText("State: Waiting for voice.", true)

        pullResponseTask()

        Timer().schedule(object : TimerTask() {
            @RequiresApi(Build.VERSION_CODES.O)
            override fun run() {
                pushData()
            }
        }, 0, 100)
    }

    @RequiresApi(Build.VERSION_CODES.O)
    private fun pushData() {
        try {
            val gaze = JSONObject()
            gaze.put("timestamp", System.currentTimeMillis())
            gaze.put("confidence", 0)
            gaze.put("norm_pos_x", 0.5)
            gaze.put("norm_pos_y", 0.5)
            gaze.put("diameter", 0)
            val gazes = JSONArray()
            gazes.put(gaze)
            val data = JSONObject()
            data.put("uid", uid)
            data.put("gazes", gazes)
            data.put("timestamp", System.currentTimeMillis())
            val mAudioFile = getAudio()
            val mImageFile = getImage()
            if (mAudioFile != null) {
                uploadServer(
                    "$server_url/heartbeat", data, mAudioFile, null
                )
            }
            if (mImageFile != null) {
                uploadServer(
                    "$server_url/heartbeat", data, null, mImageFile
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "pushData error: $e")
            Looper.prepare()
            Toast.makeText(
                applicationContext, "pushData error: $e", Toast.LENGTH_LONG
            ).show();
            Looper.loop()
        }
    }

    @RequiresApi(Build.VERSION_CODES.O)
    private fun getAudio(): File? {
        try {
            val data = audioQueue.poll()
            if (data != null) {
                val f = Files.createTempFile(Paths.get(tempFilePath),"audio", ".pcm")
                Files.write(f, data)
                return f.toFile()
            }
        } catch (e: Exception) {
            Log.e(TAG, "getAudio error: $e")
            Looper.prepare()
            Toast.makeText(
                applicationContext, "getAudio error: $e", Toast.LENGTH_LONG
            ).show();
            Looper.loop()
        }
        return null
    }

    @RequiresApi(Build.VERSION_CODES.O)
    private fun getImage(): File? {
        try {
            val data = imageQueue.poll()
            if (data != null) {
                val f = Files.createTempFile(Paths.get(tempFilePath),"image", ".jpeg")
                Files.write(f, data)
                return f.toFile()
            }
        } catch (e: Exception) {
            Log.e(TAG, "getImage error: $e")
            Looper.prepare()
            Toast.makeText(
                applicationContext, "getImage error: $e", Toast.LENGTH_LONG
            ).show();
            Looper.loop()
        }
        return null
    }

    @RequiresApi(Build.VERSION_CODES.O)
    private fun getEyeImage(): File? {
        try {
            var data = eyeImageQueue.poll()
            if (data != null) {
                var f = Files.createTempFile(Paths.get(tempFilePath),"image", ".jpeg")
                Files.write(f, data)
                return f.toFile()
            }
        } catch (e: Exception) {
            Log.e(TAG, e.toString())
        }
        return null
    }

    private fun getGaze() {
//        do {
//            val voice = voiceQueue.poll()
//            if (voice != null) {
//                Log.i(TAG, "getVoice: " + voice)
//            }
//        }while (voiceQueue.isEmpty())
    }

    private fun uploadServer(url: String, data: JSONObject, voiceFile: File?, sceneFile: File?) {
        val client = OkHttpClient()
        val requestBody = MultipartBody.Builder().setType(MultipartBody.FORM)

        requestBody.addFormDataPart("data", data.toString())
        if (voiceFile != null) {
            val body = voiceFile.asRequestBody("audio/*".toMediaTypeOrNull())
            requestBody.addFormDataPart("voice_file", voiceFile.name, body)
        }
        if (sceneFile != null) {
            val body = sceneFile.asRequestBody("image/*".toMediaTypeOrNull())
            requestBody.addFormDataPart("scene_file", sceneFile.name, body)
        }

        val currentMills = System.currentTimeMillis()

        val request = Request.Builder().url(url).post(requestBody.build()).build()
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e(TAG, e.toString())
            }

            override fun onResponse(call: Call, response: Response) {
                response.body!!.close()
                //network
                val uploadTime = System.currentTimeMillis() - currentMills
                performanceMonitorView.setUploadDelay(uploadTime)
                voiceFile?.delete()
                sceneFile?.delete()
            }
        })
    }

    //    private fun pushEyeImageTask() {
//        Timer().schedule(object : TimerTask() {
//            @RequiresApi(Build.VERSION_CODES.O)
//            override fun run() {
//                val data = JSONObject()
//                data.put("uid", uid)
//                data.put("timestamp", System.currentTimeMillis())
//                var mImageFile = getEyeImage()
//
//
//                val client = OkHttpClient()
//                val requestBody = MultipartBody.Builder().setType(MultipartBody.FORM)
//
//                requestBody.addFormDataPart("data", data.toString())
//
//                if (mImageFile != null) {
//                    val body = mImageFile.asRequestBody("image/*".toMediaTypeOrNull())
//                    requestBody.addFormDataPart("eye_file", mImageFile.name, body)
//                }
//
//                val request = Request.Builder().url(eye_server_url).post(requestBody.build()).build()
//                client.newCall(request).enqueue(object : Callback {
//                    override fun onFailure(call: Call, e: IOException) {
//                        Log.e(TAG, e.toString())
//                    }
//
//                    override fun onResponse(call: Call, response: Response) {
//                        response.body!!.close()
//                    }
//                })
//
//            }
//        }, 0, 1000)
//    }
    private fun pullResponseTask() {
        try {
            // Only to fetch the first 'hello' message when the app start up ([TURN ON])
            pullResponse()
        } catch (e: Exception) {
            Log.e(TAG, "pullResponse error: $e")
            Toast.makeText(
                applicationContext, "pullResponse error: $e", Toast.LENGTH_LONG
            ).show();
        }
        pullResponseJob = GlobalScope.launch {
            pullResponseLoop()
        }

        GlobalScope.launch {
            while (true) {
                try {
                    if (voiceQueue.isEmpty()) {
                        continue
                    }

                    mediaPlayer.setDataSource(voiceQueue.remove())
                    mediaPlayer.prepare();
                    mediaPlayer.start()
                    audioRecorder.stopRecording()
                    // waiting until the message is finished playing (or interrupted)
                    while (mediaPlayer.isPlaying) {

                    }
                    audioRecorder.startRecording()
                    // re-initiate the mediaPlayer to call the setDataSource() next time
                    mediaPlayer.release()
                    mediaPlayer = MediaPlayer()
                } catch (e: Exception) {
                    Log.e(TAG, "playback error: $e")
                    Looper.prepare()
                    Toast.makeText(
                        applicationContext,
                        "playback error: $e",
                        Toast.LENGTH_LONG
                    ).show();
                    Looper.loop()
                }
            }
        }
    }

    private suspend fun pullResponseLoop() {
        while (true) {
            try {
                pullStreamResponse()
            } catch (e: Exception) {
                Log.e(TAG, "pullStreamResponse thread: $e")
            } finally {
                withContext(Dispatchers.IO) {
                    TimeUnit.SECONDS.sleep(1)
                }
            }
        }
    }

    private fun pullResponse() {
        val startMills = System.currentTimeMillis()
        val url = "$server_url/response/$uid?is_first=$is_first"
        val client = OkHttpClient()
        val request = Request.Builder().url(url).build()
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e(TAG, "pullResponse error: $e")
            }

            override fun onResponse(call: Call, response: Response) {
                var responseStr = response.body!!.string()
                val responseObj = JSONObject(responseStr)
                val status = responseObj.getInt("status")
                val res = responseObj.getJSONObject("response")

                if (status == 1) {
                    Log.i(TAG, "responseStr: $responseStr")
                    val text = res.getJSONObject("""message""").getString("text")
                    val voice = res.getJSONObject("message").getString("voice")
                    Log.i("onResponse voice: ", voice)
                    setResponseText(text)
                    if (text == "[INTERRUPT]") {
                        voiceQueue.clear()
                    }
                    voiceQueue.add(voice)
                    is_first = false
                }

                val requestTime = System.currentTimeMillis() - startMills
                performanceMonitorView.setPullDelay(requestTime)

                response.body!!.close()
            }
        })
    }

    private fun pullStreamResponse() {
        var startMills = System.currentTimeMillis()
        val url = "$server_url/response/stream/$uid"
        Log.i(TAG, "pullStreamResponse start: $url")
        val client = OkHttpClient.Builder().readTimeout(604800, TimeUnit.SECONDS)
//            .connectTimeout(604800, TimeUnit.SECONDS).writeTimeout(604800, TimeUnit.SECONDS)
            .protocols(listOf(Protocol.HTTP_1_1))
//            .retryOnConnectionFailure(true)
            .build()
        val request = Request.Builder().url(url).build()
        val call = client.newCall(request)
        val response = call.execute()

        val input = response.body!!.byteStream()
        val buffer = BufferedReader(InputStreamReader(input))

        var firstResPkgFlag = false // flag to indicate the first response package
        var pkgCounter = 0
        var firstPkgMills = System.currentTimeMillis()
        try {
            while (true) {
                Log.i("Stream", "Update url in while loop: $updateUrl")
                if (updateUrl) {
                    Log.i("Stream update", "Update link")
                    call.cancel()
                    updateUrl = false
                    break
                }
                Log.i(TAG, "pullStreamResponse: $url")

                val strBuffer = buffer.readLine() ?: break
                Log.i(TAG, "pullStreamResponse: $strBuffer")
                val responseObj = JSONObject(strBuffer)
                val status = responseObj.getInt("status")
                val res = responseObj.getJSONObject("response")
                if (status == 1) {
                    Log.i("onResponse", res.toString())
                    var resStartTime = res.getJSONObject("message").get("start_time").toString()
                    if (resStartTime != "null"){
                        // this message is generated by GPT-4, not an inform message (e.g. '[TURN ON]]')
                        currentResId = resStartTime
                        Log.e("onResponse_start time", currentResId)
//                        setStateText("current response id: $currentResId", true)
                    }
                    if (resStartTime == banResId) {
                        // if current response id is banned, skip handling it
                        continue
                    }
                    val text = res.getJSONObject("message").getString("text")
                    val voice = res.getJSONObject("message").getString("voice")

                    // Set extra statistics
                    if (res.has("extra")) {
                        val extra = res.getJSONObject("extra")
                        val extraMap = mutableMapOf<String, String>()
                        val keys = extra.keys()
                        while (keys.hasNext()) {
                            val key = keys.next()
                            extraMap[key] = extra.getString(key)
                        }
                        performanceMonitorView.setExtraStatistics(extraMap)
                    }
                    Log.i("onResponse voice: ", voice)
                    setResponseText(text)

                    if (text.startsWith("[")) {  // deal with command
                        pkgCounter = 0
                        firstResPkgFlag = true
                        if (text == "[INTERRUPT]") {
                            voiceQueue.clear()
                        } else if (text == "[UNDER_PROCESSING]") {
                            timerUtil.startTimer(TIMER_SERVER_PROCESSING)
                        }
                    } else if (text.startsWith("<User>")) {
                        // skip processing user input
                    } else {
                        pkgCounter += 1
                        if (firstResPkgFlag) {
                            firstPkgMills = System.currentTimeMillis()
                            firstResPkgFlag = false
                        } else {
                            val pullDelay = System.currentTimeMillis() - firstPkgMills
                            performanceMonitorView.setPullDelay(pullDelay / pkgCounter) // set avg delay
                            firstPkgMills = System.currentTimeMillis()
                        }

                        val processingMilSecs = timerUtil.stopTimer(TIMER_SERVER_PROCESSING)
                        performanceMonitorView.setProcessingDelay(processingMilSecs)
                    }
                    if (voice != "") {
                        voiceQueue.add(voice)
                    }
                }

            }
        } catch (e: Exception) {
            response.body!!.close()
            Log.e(TAG, "pullStreamResponse error: $e")
        }
    }

    fun checkNet(view: View) {
        dlContainer?.openDrawer(Gravity.LEFT)
    }


    fun deleteCache() {
        try {
            val dir = this.cacheDir
            deleteDir(dir)
        } catch (e: java.lang.Exception) {
            Log.e(TAG, "deleteCache error: $e")
            Toast.makeText(
                applicationContext, "deleteCache error: $e", Toast.LENGTH_LONG
            ).show();
        }
    }

    fun deleteDir(dir: File?): Boolean {
        return if (dir != null && dir.isDirectory) {
            val children = dir.list()
            for (i in children.indices) {
                val success = deleteDir(File(dir, children[i]))
                if (!success) {
                    return false
                }
            }
            dir.delete()
        } else if (dir != null && dir.isFile) {
            dir.delete()
        } else {
            false
        }
    }

    override fun onDestroy() {
        super.onDestroy()
    }
}
