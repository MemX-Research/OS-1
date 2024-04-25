package life.memx.chat.utils

import java.util.HashMap

class TimerUtil {
    private val timers = HashMap<Int, Long>() // timer start moments

    fun startTimer(id: Int) {
        val startTime = System.currentTimeMillis()
        timers[id] = startTime
    }

    // stop timer and return elapsed time
    fun stopTimer(id: Int): Long {
        val startTime = timers[id]
        if (startTime != null) {
            val endTime = System.currentTimeMillis()
            val elapsedTime = endTime - startTime
            timers.remove(id)
            return elapsedTime
        } else {
            return -1
        }
    }
}

fun main() {
    val timerUtil = TimerUtil()

    timerUtil.startTimer(1)

    Thread.sleep(2000)

    val elapsedTime = timerUtil.stopTimer(1)

    println("Timer 1: $elapsedTime ms")
}
