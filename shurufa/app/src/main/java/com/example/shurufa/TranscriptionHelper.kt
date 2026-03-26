package com.example.shurufa

import android.util.Log
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

object TranscriptionHelper {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    
    private const val SERVER_URL = "http://192.168.1.3:5000"
    
    fun sendForTranscription(
        file: File,
        durationMs: Long,
        onSuccess: (String) -> Unit,
        onError: (String) -> Unit
    ) {
        scope.launch {
            try {
                Log.e("TRANSCRIBE_HELPER", "=== sendForTranscription START ===")
                Log.e("TRANSCRIBE_HELPER", "File: ${file.name}")
                Log.e("TRANSCRIBE_HELPER", "Size: ${file.length()} bytes")
                
                val result = withContext(Dispatchers.IO) {
                    sendAudioToServer(file)
                }
                
                if (result.isSuccess) {
                    Log.e("TRANSCRIBE_HELPER", "SUCCESS: ${result.getOrNull()}")
                    onSuccess(result.getOrNull() ?: "")
                } else {
                    val error = result.exceptionOrNull()?.message ?: "Unknown error"
                    Log.e("TRANSCRIBE_HELPER", "ERROR: $error")
                    onError(error)
                }
            } catch (e: Exception) {
                Log.e("TRANSCRIBE_HELPER", "EXCEPTION: ${e.message}")
                onError(e.message ?: "Unknown error")
            }
        }
    }
    
    private fun sendAudioToServer(audioFile: File): Result<String> {
        return try {
            Log.e("TRANSCRIBE_HELPER", "Creating HTTP connection...")
            
            val url = URL("$SERVER_URL/transcribe")
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.doInput = true
            connection.doOutput = true
            connection.connectTimeout = 60000
            connection.readTimeout = 60000
            
            val boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
            connection.setRequestProperty(
                "Content-Type",
                "multipart/form-data; boundary=$boundary"
            )
            
            Log.e("TRANSCRIBE_HELPER", "Writing data...")
            connection.outputStream.use { output ->
                output.write("--$boundary\r\n".toByteArray())
                output.write("Content-Disposition: form-data; name=\"audio\"; filename=\"${audioFile.name}\"\r\n".toByteArray())
                output.write("Content-Type: audio/wav\r\n\r\n".toByteArray())
                
                audioFile.inputStream().use { input ->
                    val buffer = ByteArray(8192)
                    var bytesRead: Int
                    while (input.read(buffer).also { bytesRead = it } != -1) {
                        output.write(buffer, 0, bytesRead)
                    }
                }
                
                output.write("\r\n--$boundary--\r\n".toByteArray())
            }
            
            Log.e("TRANSCRIBE_HELPER", "Reading response...")
            
            val responseCode = connection.responseCode
            Log.e("TRANSCRIBE_HELPER", "Response code: $responseCode")
            
            val response = StringBuilder()
            connection.inputStream.use { input ->
                val reader = input.bufferedReader()
                var line: String?
                while (reader.readLine().also { line = it } != null) {
                    response.append(line)
                }
            }
            
            val responseText = response.toString()
            Log.e("TRANSCRIBE_HELPER", "Response: $responseText")
            
            if (responseCode == 200) {
                try {
                    val json = JsonParser.parseString(responseText).asJsonObject
                    val text = json.get("text")?.asString ?: ""
                    Log.e("TRANSCRIBE_HELPER", "Parsed text: $text")
                    Result.success(text)
                } catch (e: Exception) {
                    Log.e("TRANSCRIBE_HELPER", "JSON parse error: ${e.message}")
                    Result.failure(Exception("JSON解析失败: ${e.message}"))
                }
            } else {
                Result.failure(Exception("HTTP $responseCode: $responseText"))
            }
        } catch (e: Exception) {
            Log.e("TRANSCRIBE_HELPER", "Exception in sendAudioToServer: ${e.message}")
            e.printStackTrace()
            Result.failure(e)
        }
    }
}
