package life.memx.chat.view
import androidx.lifecycle.ViewModel
import androidx.databinding.ObservableField

class PerformanceMonitorViewModel :ViewModel(){
    val uploadDelay = ObservableField<String>("Upload Delay: ")
    val pullDelay = ObservableField<String>("Pull msg Delay: ")
    val processingDelay = ObservableField<String>("Perceived Delay: ")   // from asr finish to first package received
    val asrDelay = ObservableField<String>("ASR Delay: ")
    val promptDelay = ObservableField<String>("Prompt Delay: ")
    val gptDelay = ObservableField<String>("GPT-4 Delay: ")
    val ttsDelay = ObservableField<String>("TTS Delay: ")

    fun setUploadDelay(delay_ms: Long) {
        uploadDelay.set("Upload Delay: $delay_ms ms" )
    }

    fun setPullDelay(delay_ms: Long) {
        pullDelay.set("Pull msg Delay: $delay_ms ms" )
    }
    fun setProcessingDelay(delay_ms: Long) {
        if (delay_ms > 10) {
            processingDelay.set("Delay after [UNDER_PROCESSING]: $delay_ms ms" )
        }
    }

    fun setExtraStatistics(statistics: MutableMap<String, String>) {
        statistics.forEach { (k, v) ->
            when (k) {
                "asr_delay" -> asrDelay.set("ASR Delay: $v ms" )
                "prompt_delay" -> promptDelay.set("Prompt Delay: $v ms" )
                "gpt_delay" -> gptDelay.set("GPT-4 Delay: $v ms" )
                "tts_delay" -> ttsDelay.set("TTS Delay: $v ms" )
            }
        }
    }

    fun reset() {
        uploadDelay.set("Upload Delay: - ms" )
        pullDelay.set("Pull msg Delay: - ms" )
        processingDelay.set("Perceived Delay: - ms" )
        asrDelay.set("ASR Delay: - ms" )
        ttsDelay.set("TTS Delay: - ms" )
        promptDelay.set("Prompt Delay: - ms" )
        gptDelay.set("GPT-4 Delay: - ms" )
    }

}