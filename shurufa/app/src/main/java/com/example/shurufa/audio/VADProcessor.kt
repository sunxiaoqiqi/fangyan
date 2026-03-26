package com.example.shurufa.audio

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlin.math.log10

/**
 * VAD (Voice Activity Detection) 语音活动检测器
 * 
 * 功能：
 * 1. 实时监测音频能量
 * 2. 检测静音（600ms）触发拆分
 * 3. 短片段保护（小于3秒不单独发送）
 * 4. 长片段强制拆分（大于20秒）
 * 5. 整个录音最长60秒
 */
class VADProcessor {
    
    companion object {
        // 静音阈值（分贝）
        private const val SILENCE_THRESHOLD_DB = -40.0
        
        // 静音持续时间阈值（毫秒）
        private const val SILENCE_DURATION_MS = 600L  // 600ms静音触发拆分
        
        // 最短片段时长（毫秒）
        const val MIN_SEGMENT_DURATION_MS = 3000L  // 3秒
        
        // 最长片段时长（毫秒）
        const val MAX_SEGMENT_DURATION_MS = 20000L  // 20秒，超过强制拆分
        
        // 整个录音最大时长（毫秒）
        const val MAX_RECORDING_DURATION_MS = 60000L  // 60秒
        
        // 采样率
        const val SAMPLE_RATE = 16000
        
        // 计算振幅阈值
        private val SILENCE_THRESHOLD_AMPLITUDE = calculateAmplitudeThreshold(SILENCE_THRESHOLD_DB)
        
        private fun calculateAmplitudeThreshold(dbThreshold: Double): Int {
            val linearValue = 32767.0 * Math.pow(10.0, dbThreshold / 20.0)
            return linearValue.toInt()
        }
    }
    
    // 回调接口
    interface VADCallback {
        fun onSegmentReady(audioData: ByteArray, durationMs: Long)  // 片段准备好发送
        fun onSpeakingStateChanged(isSpeaking: Boolean)  // 说话状态变化
        fun onMaxDurationReached()  // 达到最大录音时长
    }
    
    private var callback: VADCallback? = null
    
    // 录音状态
    private var isRecording = false
    
    // 整个录音的开始时间
    private var recordingStartTime = 0L
    
    // 当前片段
    private var currentSegmentData = mutableListOf<Byte>()
    private var segmentStartTime = 0L
    
    // 静音检测
    private var silenceStartTime = 0L
    
    // 待发送的短片段（小于3秒，合并到下一段）
    private var pendingShortSegment: ByteArray? = null
    private var pendingShortDuration = 0L
    
    // 状态
    private val _vadState = MutableStateFlow(VADState.IDLE)
    val vadState: StateFlow<VADState> = _vadState.asStateFlow()
    
    // 实时音量（分贝）
    private val _audioLevel = MutableStateFlow(0f)
    val audioLevel: StateFlow<Float> = _audioLevel.asStateFlow()
    
    // 是否正在说话（用于UI显示）
    private val _isSpeaking = MutableStateFlow(false)
    val isSpeaking: StateFlow<Boolean> = _isSpeaking.asStateFlow()
    
    // 录音时长（从开始计时）
    private val _recordingDuration = MutableStateFlow(0L)
    val recordingDuration: StateFlow<Long> = _recordingDuration.asStateFlow()
    
    // 片段计数
    private val _segmentCount = MutableStateFlow(0)
    val segmentCount: StateFlow<Int> = _segmentCount.asStateFlow()
    
    /**
     * 设置回调
     */
    fun setCallback(callback: VADCallback) {
        this.callback = callback
    }
    
    /**
     * 开始录音
     */
    fun start() {
        isRecording = true
        recordingStartTime = System.currentTimeMillis()  // 记录整个录音开始时间
        currentSegmentData.clear()
        pendingShortSegment = null
        pendingShortDuration = 0L
        segmentStartTime = recordingStartTime
        silenceStartTime = 0L
        _vadState.value = VADState.RECORDING
        _isSpeaking.value = false
        _audioLevel.value = 0f
        _recordingDuration.value = 0L
        _segmentCount.value = 0
    }
    
    /**
     * 停止录音，发送最后一个片段
     */
    fun stop() {
        if (!isRecording) {
            android.util.Log.e("VOICE_DEBUG", "VAD.stop: 未在录音，直接返回")
            return
        }
        
        val currentDuration = System.currentTimeMillis() - segmentStartTime
        val currentData = currentSegmentData.toByteArray()
        val totalDuration = System.currentTimeMillis() - recordingStartTime
        
        android.util.Log.e("VOICE_DEBUG", ">>> VAD.stop CALLED")
        android.util.Log.e("VOICE_DEBUG", "Total duration: ${totalDuration}ms")
        android.util.Log.e("VOICE_DEBUG", "Current segment: ${currentDuration}ms, ${currentData.size} bytes")
        
        println("VAD.stop: 停止录音")
        println("  - 录音总时长: ${totalDuration}ms")
        println("  - 当前片段时长: ${currentDuration}ms")
        println("  - 当前片段数据大小: ${currentData.size} 字节")
        println("  - 待发送短片段: ${pendingShortSegment?.size ?: 0} 字节")
        println("  - 待发送短片段时长: ${pendingShortDuration}ms")
        
        // 如果有待发送的短片段，合并到当前片段
        if (pendingShortSegment != null && pendingShortSegment!!.isNotEmpty()) {
            val combinedData = pendingShortSegment!! + currentData
            val combinedDuration = pendingShortDuration + currentDuration
            
            println("  - 合并后时长: ${combinedDuration}ms, 大小: ${combinedData.size} 字节")
            
            // 发送最后一个片段
            if (combinedDuration >= MIN_SEGMENT_DURATION_MS || _segmentCount.value == 0) {
                android.util.Log.e("VOICE_DEBUG", ">>> Calling callback with combined segment")
                println("  -> 发送合并后的片段")
                callback?.onSegmentReady(combinedData, combinedDuration)
                _segmentCount.value++
            } else {
                println("  -> 片段太短，不发送 (${combinedDuration}ms < ${MIN_SEGMENT_DURATION_MS}ms)")
            }
        } else if (currentData.isNotEmpty()) {
            println("  - 无待合并片段，当前片段: ${currentDuration}ms, ${currentData.size} 字节")
            
            // 发送当前片段
            if (currentDuration >= MIN_SEGMENT_DURATION_MS || _segmentCount.value == 0) {
                android.util.Log.e("VOICE_DEBUG", ">>> Checking callback...")
                android.util.Log.e("VOICE_DEBUG", ">>> callback is null: ${callback == null}")
                android.util.Log.e("VOICE_DEBUG", ">>> Size: ${currentData.size}, Duration: ${currentDuration}ms")
                
                if (callback != null) {
                    android.util.Log.e("VOICE_DEBUG", ">>> Calling callback with current segment")
                    println("  -> 发送当前片段")
                    callback?.onSegmentReady(currentData, currentDuration)
                    _segmentCount.value++
                } else {
                    android.util.Log.e("VOICE_DEBUG", ">>> ERROR: callback is NULL!")
                    println("  -> 错误：callback为null！")
                }
            } else {
                println("  -> 片段太短，不发送 (${currentDuration}ms < ${MIN_SEGMENT_DURATION_MS}ms)")
            }
        } else {
            android.util.Log.e("VOICE_DEBUG", ">>> No audio data to send")
            println("  -> 没有音频数据，不发送")
        }
        
        isRecording = false
        _vadState.value = VADState.IDLE
        currentSegmentData.clear()
        pendingShortSegment = null
        pendingShortDuration = 0L
    }
    
    /**
     * 处理音频数据
     */
    fun processAudioData(audioData: ByteArray) {
        if (!isRecording || _vadState.value == VADState.IDLE) return
        
        val currentTime = System.currentTimeMillis()
        
        // 更新整个录音时长（从点击开始计算）
        _recordingDuration.value = currentTime - recordingStartTime
        
        // 计算音频能量
        val amplitude = calculateRMSAmplitude(audioData)
        val dbLevel = calculateDBLevel(amplitude)
        _audioLevel.value = dbLevel
        
        // 检查是否为语音
        val currentlySpeaking = amplitude > SILENCE_THRESHOLD_AMPLITUDE
        _isSpeaking.value = currentlySpeaking
        
        // 添加到当前片段
        currentSegmentData.addAll(audioData.toList())
        
        if (currentlySpeaking) {
            // 有语音
            silenceStartTime = 0L
            
        } else {
            // 静音
            if (silenceStartTime == 0L) {
                silenceStartTime = currentTime
            }
        }
        
        // 计算片段时长
        val segmentDuration = currentTime - segmentStartTime
        
        // 每500ms打印一次状态
        if (segmentDuration % 500 < 20) {
            val silenceDur = if (silenceStartTime > 0) currentTime - silenceStartTime else 0
            println("VAD: ${segmentDuration}ms, 能量:${dbLevel.toInt()}dB, 静音:${silenceDur}ms, 数据:${currentSegmentData.size}")
        }
        
        // 检查1: 是否达到最大片段时长（20秒强制拆分）
        if (segmentDuration >= MAX_SEGMENT_DURATION_MS) {
            println("VAD: 片段达到${MAX_SEGMENT_DURATION_MS/1000}秒，强制拆分")
            forceSplitSegment()
            return
        }
        
        // 检查2: 静音超时（600ms），需要拆分
        if (silenceStartTime > 0) {
            val silenceDuration = currentTime - silenceStartTime
            if (silenceDuration >= SILENCE_DURATION_MS && segmentDuration >= MIN_SEGMENT_DURATION_MS) {
                println("VAD: 静音${silenceDuration}ms，触发拆分")
                splitCurrentSegment()
                return
            }
        }
        
        // 检查3: 是否达到整个录音最大时长（60秒）
        if (currentTime - recordingStartTime >= MAX_RECORDING_DURATION_MS) {
            _vadState.value = VADState.MAX_DURATION_REACHED
            callback?.onMaxDurationReached()
        }
    }
    
    /**
     * 拆分当前片段
     */
    private fun splitCurrentSegment() {
        val segmentData = currentSegmentData.toByteArray()
        val segmentDuration = System.currentTimeMillis() - segmentStartTime
        
        if (segmentData.isEmpty()) {
            resetForNextSegment()
            return
        }
        
        // 如果片段太短（小于3秒），缓存起来合并到下一个片段
        if (segmentDuration < MIN_SEGMENT_DURATION_MS) {
            println("VAD: 片段${segmentDuration}ms太短，缓存等待合并")
            pendingShortSegment = segmentData
            pendingShortDuration = segmentDuration
            resetForNextSegment()
            return
        }
        
        // 发送当前片段
        println("VAD: 准备发送片段，callback=${callback != null}, 数据大小=${segmentData.size}")
        try {
            callback?.onSegmentReady(segmentData, segmentDuration)
        } catch (e: Exception) {
            println("VAD: 回调异常: ${e.message}")
            e.printStackTrace()
        }
        _segmentCount.value++
        println("VAD: 发送片段${_segmentCount.value}，时长${segmentDuration}ms")
        
        resetForNextSegment()
    }
    
    /**
     * 强制拆分（20秒）
     */
    private fun forceSplitSegment() {
        val segmentData = currentSegmentData.toByteArray()
        val segmentDuration = System.currentTimeMillis() - segmentStartTime
        
        if (segmentData.isEmpty()) {
            resetForNextSegment()
            return
        }
        
        // 强制拆分，不管时长
        callback?.onSegmentReady(segmentData, segmentDuration)
        _segmentCount.value++
        println("VAD: 强制拆分片段${_segmentCount.value}，时长${segmentDuration}ms")
        
        resetForNextSegment()
    }
    
    /**
     * 重置为下一个片段
     */
    private fun resetForNextSegment() {
        currentSegmentData.clear()
        segmentStartTime = System.currentTimeMillis()
        silenceStartTime = 0L
    }
    
    /**
     * 计算RMS振幅
     */
    private fun calculateRMSAmplitude(audioData: ByteArray): Int {
        if (audioData.size < 2) return 0
        
        var sum = 0.0
        val sampleCount = audioData.size / 2
        
        for (i in 0 until sampleCount) {
            val index = i * 2
            val sample = (audioData[index].toInt() and 0xFF) or 
                        ((audioData[index + 1].toInt() shl 8))
            val signedSample = if (sample > 32767) sample - 65536 else sample
            sum += signedSample * signedSample
        }
        
        val rms = Math.sqrt(sum / sampleCount)
        return rms.toInt()
    }
    
    /**
     * 计算分贝级别
     */
    private fun calculateDBLevel(amplitude: Int): Float {
        if (amplitude == 0) return -100f
        val db = 20 * log10(amplitude.toDouble() / 32767.0)
        return db.toFloat()
    }
    
    /**
     * 检查是否达到最大时长（整个录音）
     */
    fun isMaxDurationReached(): Boolean {
        return _vadState.value == VADState.MAX_DURATION_REACHED
    }
    
    /**
     * 取消录音
     */
    fun cancel() {
        isRecording = false
        _vadState.value = VADState.IDLE
        currentSegmentData.clear()
        pendingShortSegment = null
        pendingShortDuration = 0L
    }
}

/**
 * VAD状态
 */
enum class VADState {
    IDLE,                  // 空闲
    RECORDING,             // 正在录音
    MAX_DURATION_REACHED    // 达到最大录音时长
}
