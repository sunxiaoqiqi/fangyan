package com.example.shurufa.audio

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.os.Build
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException

class AudioRecorder(private val context: Context) {
    
    private var mediaRecorder: MediaRecorder? = null
    private var isRecording = false
    private var outputFile: File? = null
    
    fun hasPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }
    
    private var isRecordingReady = false
    
    suspend fun startRecording(): Result<File> = withContext(Dispatchers.IO) {
        if (!hasPermission()) {
            println("录音权限未授予")
            return@withContext Result.failure(SecurityException("录音权限未授予"))
        }
        
        if (isRecording) {
            println("录音已在进行中")
            return@withContext Result.failure(IllegalStateException("录音已在进行中"))
        }
        
        try {
            // 优先使用外部Downloads目录，便于在文件管理器中找到
            val downloadsDir = context.getExternalFilesDir(android.os.Environment.DIRECTORY_DOWNLOADS)
            outputFile = if (downloadsDir != null && downloadsDir.canWrite()) {
                File(downloadsDir, "voice_input_${System.currentTimeMillis()}.wav")
            } else {
                // 回退到cache目录
                File(context.cacheDir, "voice_input_${System.currentTimeMillis()}.wav")
            }
            println("录音文件路径: ${outputFile?.absolutePath}")
            
            mediaRecorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                try {
                    MediaRecorder(context)
                } catch (e: Exception) {
                    val errorMessage = "MediaRecorder初始化失败 (API S+): ${e.message}"
                    println(errorMessage)
                    return@withContext Result.failure(IllegalStateException(errorMessage))
                }
            } else {
                try {
                    @Suppress("DEPRECATION")
                    MediaRecorder()
                } catch (e: Exception) {
                    val errorMessage = "MediaRecorder初始化失败 (旧API): ${e.message}"
                    println(errorMessage)
                    return@withContext Result.failure(IllegalStateException(errorMessage))
                }
            }
            
            if (mediaRecorder == null) {
                val errorMessage = "MediaRecorder初始化失败"
                println(errorMessage)
                isRecording = false
                isRecordingReady = false
                return@withContext Result.failure(IllegalStateException(errorMessage))
            }
            
            var success = false
            
            try {
                // 使用更兼容的配置
                mediaRecorder?.apply {
                    setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION)
                    setOutputFormat(MediaRecorder.OutputFormat.AAC_ADTS)
                    setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                    setAudioEncodingBitRate(96000)
                    setAudioSamplingRate(16000)
                    setAudioChannels(1)
                    setOutputFile(outputFile?.absolutePath)
                    
                    prepare()
                    Thread.sleep(1000)
                    start()
                    
                    success = true
                    isRecordingReady = true
                    println("录音已成功开始 (VOICE_RECOGNITION + AAC)")
                }
            } catch (e: Exception) {
                e.printStackTrace()
                println("首次配置失败: ${e.message}")
                
                // 尝试降级配置
                try {
                    mediaRecorder?.apply {
                        reset()
                        setAudioSource(MediaRecorder.AudioSource.MIC)
                        setOutputFormat(MediaRecorder.OutputFormat.DEFAULT)
                        setAudioEncoder(MediaRecorder.AudioEncoder.DEFAULT)
                        setOutputFile(outputFile?.absolutePath)
                        
                        prepare()
                        Thread.sleep(1000)
                        start()
                        
                        success = true
                        isRecordingReady = true
                        println("降级配置后录音成功开始 (MIC + DEFAULT)")
                    }
                } catch (e2: Exception) {
                    e2.printStackTrace()
                    val errorMessage = "录音配置失败: ${e2.message}"
                    println(errorMessage)
                    isRecordingReady = false
                    return@withContext Result.failure(IllegalStateException(errorMessage))
                }
            }
            
            // 确保success被设置
            if (!success && mediaRecorder != null) {
                println("录音配置失败，尝试使用默认配置")
                try {
                    mediaRecorder?.apply {
                        reset()
                        setAudioSource(MediaRecorder.AudioSource.MIC)
                        setOutputFormat(MediaRecorder.OutputFormat.DEFAULT)
                        setAudioEncoder(MediaRecorder.AudioEncoder.DEFAULT)
                        setOutputFile(outputFile?.absolutePath)
                        
                        prepare()
                        Thread.sleep(1000)
                        start()
                        
                        success = true
                        isRecordingReady = true
                        println("默认配置后录音成功开始")
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                    val errorMessage = "默认配置失败: ${e.message}"
                    println(errorMessage)
                    isRecordingReady = false
                    return@withContext Result.failure(IllegalStateException(errorMessage))
                }
            }
            
            isRecording = true
            if (success) {
                return@withContext Result.success(outputFile!!)
            } else {
                isRecording = false
                isRecordingReady = false
                val errorMessage = "录音未真正开始"
                println(errorMessage)
                return@withContext Result.failure(IllegalStateException(errorMessage))
            }
        } catch (e: IOException) {
            e.printStackTrace()
            val errorMessage = "IOException: ${e.message}"
            println(errorMessage)
            isRecording = false
            isRecordingReady = false
            return@withContext Result.failure(IllegalStateException(errorMessage))
        } catch (e: Exception) {
            e.printStackTrace()
            val errorMessage = "Exception: ${e.message}"
            println(errorMessage)
            isRecording = false
            isRecordingReady = false
            return@withContext Result.failure(IllegalStateException(errorMessage))
        }
    }
    
    suspend fun stopRecording(): Result<File> = withContext(Dispatchers.IO) {
        if (!isRecording) {
            return@withContext Result.failure(IllegalStateException("录音已停止"))
        }
        
        try {
            if (isRecordingReady) {
                mediaRecorder?.apply {
                    try {
                        stop()
                        reset()
                        release()
                    } catch (e: Exception) {
                        e.printStackTrace()
                        // 即使停止失败，也要确保资源被释放
                        try {
                            reset()
                            release()
                        } catch (e2: Exception) {
                            e2.printStackTrace()
                        }
                    }
                }
            } else {
                // 录音未就绪，直接释放资源
                mediaRecorder?.apply {
                    try {
                        reset()
                        release()
                    } catch (e: Exception) {
                        e.printStackTrace()
                    }
                }
            }
            
            isRecording = false
            isRecordingReady = false
            
            // 检查文件是否存在且有内容
            outputFile?.let { file ->
                if (file.exists()) {
                    val fileSize = file.length()
                    println("录音文件大小: $fileSize 字节")
                    if (fileSize > 0) {
                        return@withContext Result.success(file)
                    } else {
                        println("录音文件为空，删除文件")
                        file.delete()
                        return@withContext Result.failure(IOException("录音文件为空"))
                    }
                } else {
                    return@withContext Result.failure(IOException("录音文件不存在"))
                }
            } ?: return@withContext Result.failure(IOException("录音文件未创建"))
        } catch (e: Exception) {
            e.printStackTrace()
            isRecording = false
            isRecordingReady = false
            return@withContext Result.failure(e)
        } finally {
            mediaRecorder = null
        }
    }
    
    fun cancelRecording() {
        if (isRecording) {
            try {
                if (isRecordingReady) {
                    mediaRecorder?.apply {
                        stop()
                        reset()
                        release()
                    }
                } else {
                    // 录音未就绪，直接释放资源
                    mediaRecorder?.apply {
                        reset()
                        release()
                    }
                }
                outputFile?.delete()
            } catch (e: Exception) {
                e.printStackTrace()
            } finally {
                mediaRecorder = null
                isRecording = false
                isRecordingReady = false
                outputFile = null
            }
        }
    }
    
    fun isRecording(): Boolean = isRecording
    
    fun release() {
        cancelRecording()
    }
}