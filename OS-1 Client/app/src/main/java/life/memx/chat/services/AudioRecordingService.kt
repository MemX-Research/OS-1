package life.memx.chat.services


//import com.konovalov.vad.silero.Vad
//import com.konovalov.vad.silero.VadListener
//import com.konovalov.vad.silero.config.FrameSize
//import com.konovalov.vad.silero.config.Mode
//import com.konovalov.vad.silero.config.SampleRate
import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Environment
import android.provider.Settings
import android.util.Log
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.alibaba.fastjson.JSONException
import com.alibaba.fastjson.JSONObject
import com.alibaba.idst.nui.CommonUtils
import com.alibaba.idst.nui.Constants
import com.alibaba.idst.nui.INativeFileTransCallback
import com.alibaba.idst.nui.NativeNui
import okhttp3.Call
import okhttp3.Callback
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.util.Queue


class AudioRecording internal constructor(
    var queue: Queue<ByteArray>, private val activity: AppCompatActivity
) {
    private val TAG: String = AudioRecording::class.java.simpleName

    private val audioSource: Int = MediaRecorder.AudioSource.VOICE_COMMUNICATION
    private val sampleRateInHz: Int = 16000
    private val channelConfig: Int = AudioFormat.CHANNEL_IN_MONO
    private val audioFormat: Int = AudioFormat.ENCODING_PCM_16BIT
    private val bufferSizeInBytes: Int = 32000
    private var isRecording: Boolean = false
    private var needRecording: Boolean = true
    private var audioRecorder: AudioRecord? = null


    @SuppressLint("MissingPermission")
    fun startRecording() {
        if (!needRecording) {
            Log.d(TAG, "needRecording is false")
            return
        }
        Log.d(TAG, "startRecording")
        audioRecorder =
            AudioRecord(audioSource, sampleRateInHz, channelConfig, audioFormat, bufferSizeInBytes)
        try {
            audioRecorder!!.startRecording()
        } catch (e: Exception) {
            Log.e(TAG, "startRecording error: $e")
            Toast.makeText(
                activity, "startRecording error: $e", Toast.LENGTH_LONG
            ).show();
            return
        }
        isRecording = true
        Thread(Runnable {
            try {
                while (true) {
                    if (!isRecording) {
                        break
                    }
                    val buffer = ByteArray(bufferSizeInBytes)
                    val read = audioRecorder!!.read(buffer, 0, bufferSizeInBytes)
                    if (read > 0) {
                        queue.add(buffer)
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Recording error: $e")
                Toast.makeText(
                    activity, "Recording error: $e", Toast.LENGTH_LONG
                ).show();
            }
        }).start()
    }

    fun stopRecording() {
        Log.d(TAG, "stopRecording")
        try {
            isRecording = false
            audioRecorder?.release()
        } catch (e: Exception) {
            Log.e(TAG, "stopRecording error: $e")
            Toast.makeText(
                activity, "stopRecording error: $e", Toast.LENGTH_LONG
            ).show();
        }
    }

    fun setNeedRecording(needRecording: Boolean) {
        this.needRecording = needRecording
    }
}

class AliAsrRecorder internal constructor(private val activity: AppCompatActivity,
                                        private var server_url: String,
                                        private val interruptHandler: INativeFileTransCallback,
                                        ) {
    private val aliAppKey: String = "ALI_APP_KEY" // TODO: put your aliyun app_key
    private val audioSource: Int = MediaRecorder.AudioSource.VOICE_COMMUNICATION
    private val sampleRateInHz: Int = 16000
    private val channelConfig: Int = AudioFormat.CHANNEL_IN_MONO
    private val audioFormat: Int = AudioFormat.ENCODING_PCM_16BIT
    private val bufferSizeInBytes: Int = 16000              // store 0.5s audio
    private val fileBufferSize: Int = bufferSizeInBytes*2   // store 1s audio
    private var audioRecorder: AudioRecord? = null
//    private var count = 1
    private var filePath = Environment.getExternalStorageDirectory().path.toString() +
                           "/Android/data/life.memx.chat/"
    private var PCMPath: String = ""    // store the pcm raw file
    private var WAVPath: String = ""    // store the wav file (which was sent to ali)
    // the first half to store 0.5s audio before VAD, the second half to record 0.5s audio after VAD
    private var fileBuffer = ByteArray(fileBufferSize)
    private var sdkToken: String = ""
    private var expireTime: Int = 0
    var nui_instance = NativeNui()      // Ali SDK
    var isTriggered: Boolean = false    // whether the VAD is triggered
    var isInitiated: Boolean = false    // whether the Ali SDK has initiated

    @SuppressLint("MissingPermission")
    fun initRecorder() {
        audioRecorder =
            AudioRecord(audioSource, sampleRateInHz, channelConfig, audioFormat, bufferSizeInBytes)
        audioRecorder?.startRecording()
        Thread {
            // Listening to whether VAD is triggered
            while (true) {
                if(!isTriggered || !isInitiated) {
                    val read = audioRecorder!!.read(fileBuffer, 0, bufferSizeInBytes)
                } else {
                    // Ali SDK initiated and VAD triggered, collect second half and send to Ali
                    val read = audioRecorder!!.read(fileBuffer, bufferSizeInBytes, bufferSizeInBytes)
                    writeDateTOFile()
                    copyWaveFile(PCMPath, WAVPath)
//                    count++
                    val task_id = ByteArray(32)
                    nui_instance.startFileTranscriber(genDialogParams(), task_id)
                    isTriggered = false
                }
            }
        }.start()
    }

    fun refreshAliSDKifNeeded() {
        val sharedPreferences = activity.getSharedPreferences("data", AppCompatActivity.MODE_PRIVATE)
        expireTime = sharedPreferences.getInt("expire_time", 0)
        var currentTime: Long = System.currentTimeMillis()/1000
        Log.e("ali sdk", "current: $currentTime; expired: $expireTime")
        if ((expireTime-currentTime)/(60*60)<12){
            // less than 12 hours to expire time
            isInitiated = false
            getTokenThenInitAliSDK()
        }
    }

    fun getTokenThenInitAliSDK() {
        var url = "$server_url/get_token"
        val client = OkHttpClient()
        val request = Request.Builder().url(url).build()
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e("ali sdk", "fetch token failed!")
            }
            override fun onResponse(call: Call, response: Response) {
                var responseStr = response.body!!.string()
                val responseObj = org.json.JSONObject(responseStr)
                val status = responseObj.getInt("status")
                if (status == 1) {
                    sdkToken = responseObj.getString("token")
                    expireTime = responseObj.getInt("expire_time")
                    val sharedPreferences = activity.getSharedPreferences("data",
                        AppCompatActivity.MODE_PRIVATE
                    )
                    val editor = sharedPreferences.edit()
                    editor.putString("token", sdkToken)
                    editor.putInt("expire_time", expireTime)
                    editor.commit()
                    Log.e("ali sdk", sdkToken)
                    initAliSDK(sdkToken)
                }
            }
        })
    }

    private fun initAliSDK(token: String) {
        //Proactively call to complete the copying of SDK configuration files here
        if (CommonUtils.copyAssetsData(activity)) {
            Log.i("ali sdk", "copy assets data done")
        } else {
            Log.i("ali sdk", "copy assets failed")
            return
        }

        //Get the path of the configuration file
        val assets_path = CommonUtils.getModelPath(activity)
        Log.i(
            "ali sdk",
            "use workspace $assets_path"
        )

        val debug_path: String = filePath
        //Initialize the SDK. Note that users need to fill in relevant ID information in Auth.getAliYunTicket before it can be used.
        val ret: Int = nui_instance.initialize(
            interruptHandler,
            genInitParams(assets_path, debug_path, token),
            Constants.LogLevel.LOG_LEVEL_VERBOSE
        )
        Log.i("ali sdk", "result = $ret")
        if (ret == Constants.NuiResultCode.SUCCESS) {
            Log.i("ali sdk", "init!")
            isInitiated = true
        } else {
            Log.e("ali sdk", "init failed!")
        }
    }

    private fun genInitParams(workpath: String, debugpath: String, token: String): String? {
        var str = ""
        try {
            val `object` = JSONObject()
            //  ak_id ak_secret app_key. Please refer to https://help.aliyun.com/document_detail/72138.html
            `object`.put("app_key", aliAppKey)
            `object`.put("token", token)
            `object`.put(
                "url", "https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/FlashRecognizer"
            )
            `object`.put(
                "device_id",
                Settings.Secure.ANDROID_ID
            )

            `object`.put("workspace", workpath)

            `object`.put("debug_path", debugpath)

            `object`.put("service_mode", Constants.ModeFullCloud)
            str = `object`.toString()
        } catch (e: JSONException) {
            e.printStackTrace()
        }
        Log.i("ali sdk", "InsideUserContext:$str")
        return str
    }

    fun setServerUrl(updated_url: String) {
        server_url = updated_url
    }

    fun startRecord():Int {
        refreshAliSDKifNeeded()
        isTriggered=true
        return 0
    }

    fun stopRecord() {
        isTriggered = false
        audioRecorder?.stop()
    }

    fun releaseRecorder() {
        audioRecorder?.release()
        isTriggered = false
        audioRecorder = null
    }

    private fun writeDateTOFile() {
        // just for test, save all the files
//        PCMPath = "$filePath/RawAudio$count.pcm"
//        WAVPath = "$filePath/FinalAudio$count.wav"

        PCMPath = "$filePath/RawAudio.pcm"
        WAVPath = "$filePath/FinalAudio.wav"
        val file = File(PCMPath)
        if (!file.parentFile.exists()) {
            file.parentFile.mkdirs()
        }
        if (file.exists()) {
            file.delete()
        }
        file.createNewFile()
        val out = BufferedOutputStream(FileOutputStream(file))
        out.write(fileBuffer, 0, fileBuffer.size)
        out.flush()
        out.close()
    }

    private fun copyWaveFile(pcmPath: String, wavPath: String) {

        var fileIn = FileInputStream(pcmPath)
        var fileOut = FileOutputStream(wavPath)
        val data = ByteArray(fileBufferSize)
        val totalAudioLen = fileIn.channel.size()
        val totalDataLen = totalAudioLen + 36
        writeWaveFileHeader(fileOut, totalAudioLen, totalDataLen)
        var count = fileIn.read(data, 0, fileBufferSize)
        while (count != -1) {
            fileOut.write(data, 0, count)
            fileOut.flush()
            count = fileIn.read(data, 0, fileBufferSize)
        }
        fileIn.close()
        fileOut.close()
    }

    //Add WAV file headers
    private fun writeWaveFileHeader(out:FileOutputStream , totalAudioLen:Long,
                                    totalDataLen:Long){

        val channels = 1
        val byteRate = 16 * sampleRateInHz * channels / 8
        val header = ByteArray(44)
        header[0] = 'R'.code.toByte()
        header[1] = 'I'.code.toByte()
        header[2] = 'F'.code.toByte()
        header[3] = 'F'.code.toByte()
        header[4] = (totalDataLen and 0xff).toByte()
        header[5] = (totalDataLen shr 8 and 0xff).toByte()
        header[6] = (totalDataLen shr 16 and 0xff).toByte()
        header[7] = (totalDataLen shr 24 and 0xff).toByte()
        header[8] = 'W'.code.toByte()
        header[9] = 'A'.code.toByte()
        header[10] = 'V'.code.toByte()
        header[11] = 'E'.code.toByte()
        header[12] = 'f'.code.toByte() // 'fmt ' chunk
        header[13] = 'm'.code.toByte()
        header[14] = 't'.code.toByte()
        header[15] = ' '.code.toByte()
        header[16] = 16 // 4 bytes: size of 'fmt ' chunk
        header[17] = 0
        header[18] = 0
        header[19] = 0
        header[20] = 1 // format = 1
        header[21] = 0
        header[22] = channels.toByte()
        header[23] = 0
        header[24] = (sampleRateInHz and 0xff).toByte()
        header[25] = (sampleRateInHz shr 8 and 0xff).toByte()
        header[26] = (sampleRateInHz shr 16 and 0xff).toByte()
        header[27] = (sampleRateInHz shr 24 and 0xff).toByte()
        header[28] = (byteRate and 0xff).toByte()
        header[29] = (byteRate shr 8 and 0xff).toByte()
        header[30] = (byteRate shr 16 and 0xff).toByte()
        header[31] = (byteRate shr 24 and 0xff).toByte()
        header[32] = (2 * 16 / 8).toByte() // block align
        header[33] = 0
        header[34] = 16 // bits per sample
        header[35] = 0
        header[36] = 'd'.code.toByte()
        header[37] = 'a'.code.toByte()
        header[38] = 't'.code.toByte()
        header[39] = 'a'.code.toByte()
        header[40] = (totalAudioLen and 0xff).toByte()
        header[41] = (totalAudioLen shr 8 and 0xff).toByte()
        header[42] = (totalAudioLen shr 16 and 0xff).toByte()
        header[43] = (totalAudioLen shr 24 and 0xff).toByte()
        out.write(header, 0, 44)
    }

    private fun genDialogParams(): String? {
        var params = ""
        try {
            val dialog_param = JSONObject()
            //If you want to switch app_key at runtime
            //dialog_param.put("app_key", "");
            dialog_param["file_path"] = WAVPath
            val nls_config = JSONObject()
            nls_config["format"] = "wav"
            dialog_param["nls_config"] = nls_config
            params = dialog_param.toString()
        } catch (e: JSONException) {
            e.printStackTrace()
        }
        Log.i("ali sdk", "dialog params: $params")
        return params
    }
}

//class VadDetector (private val activity: Context) {
//    private lateinit var audioRecord: AudioRecord
//    private val sampleRate = 16000
//    private val channelConfig = AudioFormat.CHANNEL_IN_MONO
//    private val audioFormat = AudioFormat.ENCODING_PCM_16BIT
//    private val bufferSize = 1536
//    private val audioArray: ShortArray = ShortArray(bufferSize)
//    private var isListening: Boolean = false
//    private val vad = Vad.builder()
//                    .setContext(activity)
//                    .setSampleRate(SampleRate.SAMPLE_RATE_8K)
//                    .setFrameSize(FrameSize.FRAME_SIZE_1536)
//                    .setMode(Mode.NORMAL)
//                    .setSilenceDurationMs(300)
//                    .setSpeechDurationMs(50)
//                    .build()
//
//    @SuppressLint("MissingPermission")
//    fun startListening() {
//        Log.e("VAD", bufferSize.toString())
//        Log.d("VadDetector", "startListening")
//        audioRecord = AudioRecord(
//            MediaRecorder.AudioSource.VOICE_COMMUNICATION,
//            sampleRate,
//            channelConfig,
//            audioFormat,
//            bufferSize
//        )
//        try {
//            audioRecord!!.startRecording()
//        } catch (e: Exception) {
//            Log.e("VadDetector", "startRecording error: $e")
//            Toast.makeText(
//                activity, "startRecording error: $e", Toast.LENGTH_LONG
//            ).show();
//            return
//        }
//        isListening = true
//        Thread(Runnable {
//            try {
//                while (true) {
//                    if (!isListening) {
//                        break
//                    }
//                    val buffer = ShortArray(bufferSize)
//                    val readSize = audioRecord!!.read(buffer, 0, bufferSize)
//                    if (readSize > 0) {
//                        System.arraycopy(buffer, 0, audioArray, 0, readSize)
//                    }
//                    val isSpeech = vad.isSpeech(audioArray)
//                    if (isSpeech) {
//                        Log.e("VAD", "speech detected!")
//                    }
//                }
//            } catch (e: Exception) {
//                Log.e("VadDetector", "Recording error: $e")
//                Toast.makeText(
//                    activity, "Recording error: $e", Toast.LENGTH_LONG
//                ).show();
//            }
//        }).start()
//    }
//
//    fun stop() {
//        Log.e("VAD", "closed listening!")
//        isListening = false
//        audioRecord.stop()
//        audioRecord.release()
//    }
//}
