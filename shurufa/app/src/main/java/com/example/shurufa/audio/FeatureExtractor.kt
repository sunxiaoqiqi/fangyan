package com.example.shurufa.audio

import android.content.Context
import android.media.MediaExtractor
import android.media.MediaFormat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.nio.ByteBuffer
import kotlin.math.cos
import kotlin.math.log10
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

class FeatureExtractor(private val context: Context) {
    
    companion object {
        private const val SAMPLE_RATE = 16000
        private const val N_FFT = 400
        private const val HOP_LENGTH = 160
        private const val N_MELS = 80
        private const val WIN_LENGTH = 400
        private const val FMIN = 0.0
        private const val FMAX = 8000.0
        private const val PI = 3.14159265358979323846
    }
    
    private val melFilterbank = createMelFilterbank()
    
    suspend fun extractFeatures(audioFile: File): Result<Array<FloatArray>> = withContext(Dispatchers.Default) {
        try {
            if (!audioFile.exists()) {
                return@withContext Result.failure(IllegalArgumentException("音频文件不存在"))
            }
            
            if (audioFile.length() < 1024) {
                return@withContext Result.failure(IllegalArgumentException("音频文件太小"))
            }
            
            val audioData = loadAudioFile(audioFile)
            
            if (audioData.isEmpty()) {
                return@withContext Result.failure(IllegalArgumentException("音频数据为空"))
            }
            
            val melSpectrogram = computeMelSpectrogram(audioData)
            
            if (melSpectrogram.isEmpty()) {
                return@withContext Result.failure(IllegalArgumentException("特征提取结果为空"))
            }
            
            Result.success(melSpectrogram)
        } catch (e: IllegalArgumentException) {
            e.printStackTrace()
            Result.failure(e)
        } catch (e: Exception) {
            e.printStackTrace()
            Result.failure(e)
        }
    }
    
    private fun loadAudioFile(file: File): FloatArray {
        val extractor = MediaExtractor()
        extractor.setDataSource(file.absolutePath)
        
        val audioTrackIndex = (0 until extractor.trackCount).firstOrNull { index ->
            val format = extractor.getTrackFormat(index)
            format.getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true
        } ?: throw IllegalArgumentException("找不到音频轨道")
        
        extractor.selectTrack(audioTrackIndex)
        val format = extractor.getTrackFormat(audioTrackIndex)
        
        val sampleRate = try {
            format.getInteger(MediaFormat.KEY_SAMPLE_RATE) ?: SAMPLE_RATE
        } catch (e: Exception) {
            SAMPLE_RATE
        }
        val maxBufferSize = try {
            format.getInteger(MediaFormat.KEY_MAX_INPUT_SIZE) ?: 1024 * 1024
        } catch (e: Exception) {
            1024 * 1024
        }
        
        val audioBuffer = ByteBuffer.allocate(maxBufferSize)
        val audioData = mutableListOf<Float>()
        
        while (true) {
            audioBuffer.clear()  // 重置buffer，设置position=0, limit=capacity
            val bytesRead = extractor.readSampleData(audioBuffer, 0)
            if (bytesRead < 0) break
            
            // 将buffer切换到读取模式
            audioBuffer.limit(bytesRead)
            
            for (i in 0 until bytesRead step 2) {
                if (i + 1 < bytesRead) {
                    val sample = audioBuffer.getShort(i).toFloat() / 32767.0f
                    audioData.add(sample)
                }
            }
            
            if (!extractor.advance()) break
        }
        
        extractor.release()
        
        println("音频数据加载完成: ${audioData.size} 样本, 采样率: $sampleRate Hz")
        
        return if (sampleRate == SAMPLE_RATE) {
            audioData.toFloatArray()
        } else {
            println("需要重采样: $sampleRate Hz -> $SAMPLE_RATE Hz")
            resample(audioData.toFloatArray(), sampleRate, SAMPLE_RATE)
        }
    }
    
    private fun resample(audioData: FloatArray, fromRate: Int, toRate: Int): FloatArray {
        val ratio = fromRate.toFloat() / toRate.toFloat()
        val outputLength = (audioData.size / ratio).toInt()
        val output = FloatArray(outputLength)
        
        for (i in 0 until outputLength) {
            val inputIndex = (i * ratio).toInt()
            output[i] = audioData[min(inputIndex, audioData.size - 1)]
        }
        
        return output
    }
    
    private fun computeMelSpectrogram(audioData: FloatArray): Array<FloatArray> {
        val numFrames = (audioData.size - WIN_LENGTH) / HOP_LENGTH + 1
        val melSpectrogram = Array(numFrames) { FloatArray(N_MELS) }
        
        for (i in 0 until numFrames) {
            val start = i * HOP_LENGTH
            val end = min(start + WIN_LENGTH, audioData.size)
            val frame = FloatArray(WIN_LENGTH) { 
                if (start + it < end) audioData[start + it] else 0.0f 
            }
            
            val windowedFrame = applyHannWindow(frame)
            val fftResult = computeFFT(windowedFrame)
            val magnitude = computeMagnitude(fftResult)
            val melFeatures = applyMelFilterbank(magnitude)
            
            melSpectrogram[i] = melFeatures
        }
        
        return melSpectrogram
    }
    
    private fun applyHannWindow(frame: FloatArray): FloatArray {
        val windowed = FloatArray(frame.size)
        for (i in frame.indices) {
            val hann = 0.5f * (1.0f - cos(2.0f * PI.toFloat() * i / (frame.size - 1)))
            windowed[i] = frame[i] * hann
        }
        return windowed
    }
    
    private fun computeFFT(input: FloatArray): Array<Float> {
        val n = input.size
        if (n <= 1) {
            return input.map { it }.toTypedArray()
        }
        
        val even = computeFFT(input.indices.filter { it % 2 == 0 }.map { input[it] }.toFloatArray())
        val odd = computeFFT(input.indices.filter { it % 2 != 0 }.map { input[it] }.toFloatArray())
        
        val result = Array(n) { 0.0f }
        for (k in 0 until n / 2) {
            val t = -2.0f * PI.toFloat() * k / n
            val expRe = cos(t)
            val expIm = sin(t)
            
            val oddRe = if (k < odd.size) odd[k] else 0.0f
            val oddIm = if (k + n / 2 < odd.size) odd[k + n / 2] else 0.0f
            
            result[k] = even[k] + (expRe * oddRe - expIm * oddIm)
            result[k + n / 2] = even[k] - (expRe * oddRe - expIm * oddIm)
        }
        
        return result
    }
    
    private fun computeMagnitude(fftResult: Array<Float>): FloatArray {
        val magnitude = FloatArray(fftResult.size / 2)
        for (i in magnitude.indices) {
            val real = fftResult[i]
            val imag = fftResult[i + fftResult.size / 2]
            magnitude[i] = sqrt(real * real + imag * imag)
        }
        return magnitude
    }
    
    private fun applyMelFilterbank(magnitude: FloatArray): FloatArray {
        val melFeatures = FloatArray(N_MELS)
        
        for (i in 0 until N_MELS) {
            var sum = 0.0f
            for (j in magnitude.indices) {
                sum += magnitude[j] * melFilterbank[i][j]
            }
            melFeatures[i] = sum
        }
        
        return melFeatures
    }
    
    private fun createMelFilterbank(): Array<FloatArray> {
        val filterbank = Array(N_MELS) { FloatArray(N_FFT / 2 + 1) }
        
        val melMin = hzToMel(FMIN)
        val melMax = hzToMel(FMAX)
        val melPoints = FloatArray(N_MELS + 2) { i ->
            (melMin + (melMax - melMin) * i / (N_MELS + 1)).toFloat()
        }
        
        val hzPoints = melPoints.map { melToHz(it.toDouble()) }
        val binPoints = hzPoints.map { (it * (N_FFT / 2 + 1) / (SAMPLE_RATE / 2)).toInt() }
        
        for (i in 0 until N_MELS) {
            for (j in binPoints[i] until binPoints[i + 1]) {
                filterbank[i][j] = (j - binPoints[i]).toFloat() / 
                                   (binPoints[i + 1] - binPoints[i]).toFloat()
            }
            for (j in binPoints[i + 1] until binPoints[i + 2]) {
                filterbank[i][j] = (binPoints[i + 2] - j).toFloat() / 
                                   (binPoints[i + 2] - binPoints[i + 1]).toFloat()
            }
        }
        
        return filterbank
    }
    
    private fun hzToMel(hz: Double): Double {
        return 2595.0 * log10(1.0 + hz / 700.0)
    }
    
    private fun melToHz(mel: Double): Double {
        return 700.0 * (Math.pow(10.0, mel / 2595.0) - 1.0)
    }
}