package com.example.shurufa.inference

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.io.BufferedReader
import java.io.InputStreamReader
import com.google.gson.Gson
import com.google.gson.JsonObject

/**
 * HTTP Whisper客户端
 * 
 * 通过HTTP API调用faster-whisper服务器进行语音识别
 * 
 * 使用方法：
 * 1. 在本地PC运行 whisper_server.py
 * 2. 确保Android设备和PC在同一网络
 * 3. 修改 SERVER_URL 为PC的IP地址
 */
class HttpWhisperClient(private val context: Context) {
    
    companion object {
        // TODO: 修改为你的PC IP地址
        // 在PC上运行 ipconfig (Windows) 或 ifconfig (macOS/Linux) 查看IP
        private const val SERVER_URL = "http://192.168.1.3:5000"  // 修改为实际IP地址
    }
    
    private var isServerAvailable = false
    
    /**
     * 检查服务器是否可用
     */
    suspend fun checkServer(): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val url = URL("$SERVER_URL/health")
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 5000
            connection.readTimeout = 5000
            
            val responseCode = connection.responseCode
            connection.disconnect()
            
            isServerAvailable = responseCode == 200
            Result.success(isServerAvailable)
        } catch (e: Exception) {
            e.printStackTrace()
            isServerAvailable = false
            Result.failure(e)
        }
    }
    
    /**
     * 转录音频文件
     * 
     * @param audioFile 音频文件（WAV格式）
     * @return 转录结果
     */
    suspend fun transcribe(audioFile: File): Result<String> = withContext(Dispatchers.IO) {
        try {
            android.util.Log.e("HTTP_CLIENT", "HTTP: Starting transcribe")
            android.util.Log.e("HTTP_CLIENT", "File: ${audioFile.name}, Size: ${audioFile.length()}")
            android.util.Log.e("HTTP_CLIENT", "Server: $SERVER_URL")
            
            println("HttpWhisperClient: 开始转录 ${audioFile.absolutePath}")
            
            // 检查服务器
            if (!isServerAvailable) {
                val checkResult = checkServer()
                if (checkResult.isFailure) {
                    return@withContext Result.failure(
                        Exception("无法连接到服务器: $SERVER_URL\n请确保服务器已启动")
                    )
                }
            }
            
            // 创建HTTP连接
            android.util.Log.e("HTTP_CLIENT", "HTTP: Creating connection...")
            val url = URL("$SERVER_URL/transcribe")
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.doInput = true
            connection.doOutput = true
            connection.connectTimeout = 60000  // 60秒超时
            connection.readTimeout = 60000
            
            // 设置请求头
            val boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
            connection.setRequestProperty(
                "Content-Type",
                "multipart/form-data; boundary=$boundary"
            )
            
            // 写入文件数据 - 使用OutputStream直接写入二进制数据
            android.util.Log.e("HTTP_CLIENT", "HTTP: Writing data...")
            connection.outputStream.use { output ->
                // 写入boundary头部
                output.write("--$boundary\r\n".toByteArray())
                output.write("Content-Disposition: form-data; name=\"audio\"; filename=\"${audioFile.name}\"\r\n".toByteArray())
                output.write("Content-Type: audio/wav\r\n\r\n".toByteArray())
                
                // 写入音频文件数据
                audioFile.inputStream().use { input ->
                    val buffer = ByteArray(8192)
                    var bytesRead: Int
                    while (input.read(buffer).also { bytesRead = it } != -1) {
                        output.write(buffer, 0, bytesRead)
                    }
                }
                
                // 写入boundary结束
                output.write("\r\n--$boundary--\r\n".toByteArray())
            }
            
            android.util.Log.e("HTTP_CLIENT", "HTTP: Data written, reading response...")
            
            // 读取响应
            val response = StringBuilder()
            BufferedReader(InputStreamReader(connection.inputStream)).use { reader ->
                var line: String?
                while (reader.readLine().also { line = it } != null) {
                    response.append(line)
                }
            }
            
            val responseCode = connection.responseCode
            val responseBody = response.toString()
            connection.disconnect()
            
            println("HttpWhisperClient: 响应码=$responseCode")
            println("HttpWhisperClient: 响应长度=${responseBody.length}")
            if (responseBody.isNotEmpty()) {
                println("HttpWhisperClient: 响应=$responseBody")
            }
            
            // 使用Gson解析JSON响应（正确处理Unicode编码）
            val gson = Gson()
            val jsonResponse = gson.fromJson(responseBody, JsonObject::class.java)
            
            println("HttpWhisperClient: JSON解析成功")
            
            if (responseCode == 200) {
                android.util.Log.e("HTTP_CLIENT", "HTTP: Response 200 OK")
                val text = jsonResponse.get("text")?.asString ?: ""
                val error = jsonResponse.get("error")?.asString
                
                if (!error.isNullOrEmpty()) {
                    android.util.Log.e("HTTP_CLIENT", "HTTP: Server error: $error")
                    Result.failure(Exception("服务器错误: $error"))
                } else if (text.isNotEmpty()) {
                    android.util.Log.e("HTTP_CLIENT", "HTTP: Transcription success!")
                    println("HttpWhisperClient: Transcription success: $text")
                    Result.success(text)
                } else {
                    val duration = jsonResponse.get("duration")?.asDouble ?: 0.0
                    val lang = jsonResponse.get("language")?.asString ?: "unknown"
                    Result.failure(Exception("Transcription result is empty. Language: $lang, Duration: ${duration}s"))
                }
            } else {
                val error = jsonResponse.get("error")?.asString ?: "Unknown error"
                Result.failure(Exception(error))
            }
            
        } catch (e: Exception) {
            android.util.Log.e("HTTP_CLIENT", "HttpWhisperClient: Exception!")
            android.util.Log.e("HTTP_CLIENT", "Type: ${e.javaClass.simpleName}")
            android.util.Log.e("HTTP_CLIENT", "Message: ${e.message}")
            e.printStackTrace()
            Result.failure(e)
        }
    }
    
    /**
     * 获取服务器状态
     */
    fun isAvailable(): Boolean = isServerAvailable
    
    /**
     * 获取服务器地址
     */
    fun getServerUrl(): String = SERVER_URL
    
    /**
     * 设置服务器地址
     */
    fun setServerUrl(url: String) {
        // 注意：这个方法需要在companion object中修改SERVER_URL
        println("请在代码中修改 SERVER_URL 为: $url")
    }
}
