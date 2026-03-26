package com.example.shurufa.audio

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * WAV格式音频录制器
 */
class WavAudioRecorder(private val context: Context) {
    
    companion object {
        const val SAMPLE_RATE = 16000
        const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
    }
    
    private var audioRecord: AudioRecord? = null
    private var isRecording = false
    private var recordingThread: Thread? = null
    
    private val vadProcessor = VADProcessor()
    private var vadCallback: VADCallback? = null
    
    private val bufferSize: Int by lazy {
        val minBuffer = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
        minBuffer * 2
    }
    
    interface VADCallback {
        fun onSegmentReady(file: File, durationMs: Long)
        fun onSpeakingStateChanged(isSpeaking: Boolean)
        fun onMaxDurationReached()
        fun onRecordingStateChanged(state: String)
    }
    
    fun setVADCallback(callback: VADCallback) {
        this.vadCallback = callback
        vadProcessor.setCallback(object : VADProcessor.VADCallback {
            override fun onSegmentReady(audioData: ByteArray, durationMs: Long) {
                android.util.Log.e("AUDIO_CB", "WavRecorder.onSegmentReady")
                android.util.Log.e("AUDIO_CB", "Size=${audioData.size}, Dur=${durationMs}ms")
                
                try {
                    val file = saveSegmentToWavSync(audioData)
                    if (file != null) {
                        android.util.Log.e("AUDIO_CB", "File saved OK")
                        callback.onSegmentReady(file, durationMs)
                    } else {
                        android.util.Log.e("AUDIO_CB", "File save FAILED")
                    }
                } catch (e: Exception) {
                    android.util.Log.e("AUDIO_CB", "Exception: ${e.message}")
                }
            }
            
            override fun onSpeakingStateChanged(isSpeaking: Boolean) {
                android.util.Log.d("AUDIO_CB", "Speaking: $isSpeaking")
                callback.onSpeakingStateChanged(isSpeaking)
            }
            
            override fun onMaxDurationReached() {
                android.util.Log.e("AUDIO_CB", "MaxDurationReached")
                callback.onMaxDurationReached()
            }
        })
    }
    
    private fun saveSegmentToWavSync(audioData: ByteArray): File? {
        if (audioData.isEmpty()) return null
        
        return try {
            val file = File(context.cacheDir, "segment_${System.currentTimeMillis()}.wav")
            
            println("WavAudioRecorder: 保存片段，文件: ${file.absolutePath}, 大小: ${audioData.size} 字节")
            
            FileOutputStream(file).use { out ->
                writeWavHeader(out, audioData.size.toLong())
                out.write(audioData)
            }
            
            println("WavAudioRecorder: 片段保存成功")
            file
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }
    
    suspend fun startRecording(): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) 
                != PackageManager.PERMISSION_GRANTED) {
                return@withContext Result.failure(SecurityException("没有录音权限"))
            }
            
            isRecording = true
            vadProcessor.start()
            
            println("WavAudioRecorder: 开始录音")
            vadCallback?.onRecordingStateChanged("recording")
            
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                SAMPLE_RATE,
                CHANNEL_CONFIG,
                AUDIO_FORMAT,
                bufferSize
            )
            
            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                vadProcessor.cancel()
                return@withContext Result.failure(IllegalStateException("AudioRecord初始化失败"))
            }
            
            audioRecord?.startRecording()
            
            recordingThread = Thread {
                val buffer = ByteArray(bufferSize)
                
                while (isRecording && audioRecord?.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    val bytesRead = audioRecord?.read(buffer, 0, bufferSize) ?: 0
                    
                    if (bytesRead > 0) {
                        val validData = buffer.copyOf(bytesRead)
                        vadProcessor.processAudioData(validData)
                    }
                    
                    try {
                        Thread.sleep(10)
                    } catch (e: InterruptedException) {
                        break
                    }
                }
            }
            recordingThread?.start()
            
            Result.success(Unit)
            
        } catch (e: Exception) {
            e.printStackTrace()
            vadProcessor.cancel()
            Result.failure(e)
        }
    }
    
    fun stopRecording() {
        println("WavAudioRecorder.stopRecording: 开始停止")
        
        if (!isRecording) {
            println("WavAudioRecorder.stopRecording: 未在录音，直接返回")
            return
        }
        
        vadCallback?.onRecordingStateChanged("stopping")
        
        isRecording = false
        
        try {
            recordingThread?.join(1000)
        } catch (e: InterruptedException) {
            println("WavAudioRecorder: 等待线程中断: ${e.message}")
        }
        
        if (recordingThread?.isAlive == true) {
            println("WavAudioRecorder: 录音线程还在运行，强制中断")
            recordingThread?.interrupt()
        }
        recordingThread = null
        
        try {
            if (audioRecord?.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                audioRecord?.stop()
            }
            audioRecord?.release()
        } catch (e: Exception) {
            println("WavAudioRecorder: 停止/释放AudioRecord异常: ${e.message}")
        }
        audioRecord = null
        
        vadProcessor.stop()
        println("WavAudioRecorder.stopRecording: 停止完成")
    }
    
    private fun writeWavHeader(out: FileOutputStream, dataSize: Long) {
        val totalDataLen = dataSize + 36
        val byteRate = SAMPLE_RATE.toLong() * 1 * 16 / 8
        val blockAlign = 2
        
        out.write("RIFF".toByteArray(Charsets.US_ASCII))
        out.write(intToByteArray(totalDataLen.toInt()))
        out.write("WAVE".toByteArray(Charsets.US_ASCII))
        out.write("fmt ".toByteArray(Charsets.US_ASCII))
        out.write(intToByteArray(16))
        out.write(shortToByteArray(1))
        out.write(shortToByteArray(1))
        out.write(intToByteArray(SAMPLE_RATE))
        out.write(intToByteArray(byteRate.toInt()))
        out.write(shortToByteArray(blockAlign))
        out.write(shortToByteArray(16))
        out.write("data".toByteArray(Charsets.US_ASCII))
        out.write(intToByteArray(dataSize.toInt()))
    }
    
    private fun intToByteArray(value: Int): ByteArray {
        return ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(value).array()
    }
    
    private fun shortToByteArray(value: Int): ByteArray {
        return ByteBuffer.allocate(2).order(ByteOrder.LITTLE_ENDIAN).putShort(value.toShort()).array()
    }
    
    fun release() {
        isRecording = false
        recordingThread?.interrupt()
        recordingThread = null
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (e: Exception) {
            e.printStackTrace()
        }
        audioRecord = null
        vadProcessor.cancel()
    }
    
    fun cancelRecording() {
        isRecording = false
        recordingThread?.interrupt()
        recordingThread = null
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (e: Exception) {
            e.printStackTrace()
        }
        audioRecord = null
        vadProcessor.cancel()
        vadCallback?.onRecordingStateChanged("cancelled")
    }
    
    fun isRecording(): Boolean = isRecording
    
    fun getVADProcessor(): VADProcessor = vadProcessor
}
