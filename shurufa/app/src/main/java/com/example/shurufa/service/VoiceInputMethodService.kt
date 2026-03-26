package com.example.shurufa.service

import android.inputmethodservice.InputMethodService
import android.view.KeyEvent
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import com.example.shurufa.GlobalScope
import com.example.shurufa.R
import com.example.shurufa.TranscriptionHelper
import com.example.shurufa.scrollToBottom
import com.example.shurufa.audio.VADProcessor
import com.example.shurufa.audio.WavAudioRecorder
import com.example.shurufa.inference.HttpWhisperClient
import com.example.shurufa.input.PinyinConverter
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class VoiceInputMethodService : InputMethodService() {

    private var audioRecorder: WavAudioRecorder? = null
    private var httpWhisperClient: HttpWhisperClient? = null
    private var pinyinConverter: PinyinConverter? = null

    private var isRecording = false
    private var recordingJob: Job? = null
    private var isStopping = false

    private lateinit var voiceInputButton: Button
    private lateinit var transcriptionText: TextView
    private lateinit var transcriptionResultText: TextView

    private var isUpperCase = false
    private var isSymbolMode = false
    private var isChineseMode = false

    private val transcriptionResult = StringBuilder()
    private var pendingTranscriptionJobs = 0

    private var currentPinyin = StringBuilder()
    private var currentCandidates = mutableListOf<String>()
    private var candidatePage = 0
    private var selectedCandidateIndex = -1

    override fun onCreate() {
        super.onCreate()
        pinyinConverter = PinyinConverter(this)
    }

    override fun onCreateInputView(): View {
        return createKeyboardView()
    }
    
    private fun createVoiceInputView(): View {
        val inputView = layoutInflater.inflate(R.layout.voice_input_view, null)
        
        voiceInputButton = inputView.findViewById(R.id.btn_voice_input)
        transcriptionText = inputView.findViewById(R.id.transcription_text)
        transcriptionResultText = inputView.findViewById(R.id.transcription_result_text)
        
        voiceInputButton.setOnClickListener {
            startVoiceInput()
        }
        
        inputView.findViewById<Button>(R.id.btn_keyboard_input)?.setOnClickListener {
            setInputView(createKeyboardView())
        }
        
        initVoiceComponents()
        
        return inputView
    }
    
    private fun createKeyboardView(): View {
        val inputView = layoutInflater.inflate(R.layout.keyboard_view, null)

        voiceInputButton = inputView.findViewById(R.id.btn_voice_input)

        voiceInputButton.setOnClickListener {
            val voiceView = createVoiceInputView()
            setInputView(voiceView)
        }

        inputView.findViewById<Button>(R.id.btn_lang_toggle)?.setOnClickListener {
            isChineseMode = !isChineseMode
            isUpperCase = false
            isSymbolMode = false
            updateKeyboardLayout(inputView)
            updateCandidateBar(inputView)
        }

        inputView.findViewById<Button>(R.id.btn_symbols)?.setOnClickListener {
            isSymbolMode = !isSymbolMode
            if (isSymbolMode) {
                isChineseMode = false
            }
            updateKeyboardLayout(inputView)
            updateCandidateBar(inputView)
        }

        inputView.findViewById<Button>(R.id.btn_shift)?.setOnClickListener {
            isUpperCase = !isUpperCase
            updateKeyboardLayout(inputView)
        }

        inputView.findViewById<Button>(R.id.btn_backspace)?.setOnClickListener {
            handleBackspace(inputView)
        }

        inputView.findViewById<Button>(R.id.btn_space)?.setOnClickListener {
            handleSpace(inputView)
        }

        inputView.findViewById<Button>(R.id.btn_enter)?.setOnClickListener {
            if (isChineseMode && currentPinyin.isNotEmpty()) {
                commitChineseText(inputView)
            }
            currentInputConnection?.sendKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENTER))
            currentInputConnection?.sendKeyEvent(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_ENTER))
        }

        inputView.findViewById<Button>(R.id.btn_more_candidates)?.setOnClickListener {
            candidatePage++
            updateCandidateDisplay(inputView)
        }

        setupCandidateButtons(inputView)
        updateKeyboardLayout(inputView)
        updateCandidateBar(inputView)

        return inputView
    }

    private fun handleBackspace(inputView: View) {
        if (isChineseMode && currentPinyin.isNotEmpty()) {
            currentPinyin.deleteCharAt(currentPinyin.length - 1)
            updateCandidateBar(inputView)
        } else {
            currentInputConnection?.deleteSurroundingText(1, 0)
        }
    }

    private fun handleSpace(inputView: View) {
        if (isChineseMode && currentPinyin.isNotEmpty()) {
            if (currentCandidates.isNotEmpty()) {
                val selectedCandidate = if (selectedCandidateIndex >= 0 && selectedCandidateIndex < currentCandidates.size) {
                    currentCandidates[selectedCandidateIndex]
                } else {
                    currentCandidates.getOrNull(0) ?: ""
                }
                if (selectedCandidate.isNotEmpty()) {
                    currentInputConnection?.commitText(selectedCandidate, 1)
                }
            }
            currentPinyin.clear()
            currentCandidates.clear()
            selectedCandidateIndex = -1
            candidatePage = 0
            updateCandidateBar(inputView)
        } else {
            currentInputConnection?.commitText(" ", 1)
        }
    }

    private fun commitChineseText(inputView: View) {
        if (currentPinyin.isNotEmpty()) {
            if (currentCandidates.isNotEmpty()) {
                val selectedCandidate = if (selectedCandidateIndex >= 0 && selectedCandidateIndex < currentCandidates.size) {
                    currentCandidates[selectedCandidateIndex]
                } else {
                    currentCandidates.getOrNull(0) ?: ""
                }
                if (selectedCandidate.isNotEmpty()) {
                    currentInputConnection?.commitText(selectedCandidate, 1)
                }
            }
            currentPinyin.clear()
            currentCandidates.clear()
            selectedCandidateIndex = -1
            candidatePage = 0
            updateCandidateBar(inputView)
        }
    }

    private fun setupCandidateButtons(inputView: View) {
        val candidateIds = listOf(
            R.id.candidate_1, R.id.candidate_2, R.id.candidate_3,
            R.id.candidate_4, R.id.candidate_5
        )

        candidateIds.forEachIndexed { index, buttonId ->
            inputView.findViewById<Button>(buttonId)?.setOnClickListener {
                selectCandidate(index, inputView)
            }
        }
    }

    private fun selectCandidate(index: Int, inputView: View) {
        val globalIndex = candidatePage * 5 + index
        if (globalIndex < currentCandidates.size) {
            selectedCandidateIndex = globalIndex
            val candidate = currentCandidates[globalIndex]
            currentInputConnection?.commitText(candidate, 1)
            currentPinyin.clear()
            currentCandidates.clear()
            selectedCandidateIndex = -1
            candidatePage = 0
            updateCandidateBar(inputView)
        }
    }

    private fun updateCandidateBar(inputView: View) {
        val candidateBar = inputView.findViewById<LinearLayout>(R.id.candidate_bar)
        val pinyinDisplay = inputView.findViewById<TextView>(R.id.pinyin_display)

        if (isChineseMode) {
            candidateBar?.visibility = View.VISIBLE
            pinyinDisplay?.text = if (currentPinyin.isNotEmpty()) currentPinyin.toString() else ""
            updateCandidateDisplay(inputView)
        } else {
            candidateBar?.visibility = View.GONE
        }

        inputView.findViewById<Button>(R.id.btn_lang_toggle)?.text = if (isChineseMode) "英文" else "中/英"
    }

    private fun updateCandidateDisplay(inputView: View) {
        if (!isChineseMode || currentPinyin.isEmpty()) {
            return
        }

        currentCandidates = pinyinConverter?.getCandidates(currentPinyin.toString())?.toMutableList() ?: mutableListOf()

        val candidateIds = listOf(
            R.id.candidate_1, R.id.candidate_2, R.id.candidate_3,
            R.id.candidate_4, R.id.candidate_5
        )

        candidateIds.forEachIndexed { index, buttonId ->
            val button = inputView.findViewById<Button>(buttonId)
            val globalIndex = candidatePage * 5 + index
            if (globalIndex < currentCandidates.size) {
                button?.text = currentCandidates[globalIndex]
                button?.visibility = View.VISIBLE
            } else {
                button?.text = ""
                button?.visibility = View.INVISIBLE
            }
        }
    }

    private fun handlePinyinInput(letter: String, inputView: View) {
        if (!isChineseMode) {
            currentInputConnection?.commitText(letter, 1)
            return
        }

        currentPinyin.append(letter.lowercase())
        updateCandidateBar(inputView)
    }

    private fun updateKeyboardLayout(inputView: View) {
        val upperLetters = mapOf(
            R.id.btn_q to "Q", R.id.btn_w to "W", R.id.btn_e to "E",
            R.id.btn_r to "R", R.id.btn_t to "T", R.id.btn_y to "Y",
            R.id.btn_u to "U", R.id.btn_i to "I", R.id.btn_o to "O",
            R.id.btn_p to "P", R.id.btn_a to "A", R.id.btn_s to "S",
            R.id.btn_d to "D", R.id.btn_f to "F", R.id.btn_g to "G",
            R.id.btn_h to "H", R.id.btn_j to "J", R.id.btn_k to "K",
            R.id.btn_l to "L", R.id.btn_z to "Z", R.id.btn_x to "X",
            R.id.btn_c to "C", R.id.btn_v to "V", R.id.btn_b to "B",
            R.id.btn_n to "N", R.id.btn_m to "M"
        )

        val lowerLetters = mapOf(
            R.id.btn_q to "q", R.id.btn_w to "w", R.id.btn_e to "e",
            R.id.btn_r to "r", R.id.btn_t to "t", R.id.btn_y to "y",
            R.id.btn_u to "u", R.id.btn_i to "i", R.id.btn_o to "o",
            R.id.btn_p to "p", R.id.btn_a to "a", R.id.btn_s to "s",
            R.id.btn_d to "d", R.id.btn_f to "f", R.id.btn_g to "g",
            R.id.btn_h to "h", R.id.btn_j to "j", R.id.btn_k to "k",
            R.id.btn_l to "l", R.id.btn_z to "z", R.id.btn_x to "x",
            R.id.btn_c to "c", R.id.btn_v to "v", R.id.btn_b to "b",
            R.id.btn_n to "n", R.id.btn_m to "m"
        )

        val pinyinKeys = mapOf(
            R.id.btn_q to "q", R.id.btn_w to "w", R.id.btn_e to "e",
            R.id.btn_r to "r", R.id.btn_t to "t", R.id.btn_y to "y",
            R.id.btn_u to "u", R.id.btn_i to "i", R.id.btn_o to "o",
            R.id.btn_p to "p", R.id.btn_a to "a", R.id.btn_s to "s",
            R.id.btn_d to "d", R.id.btn_f to "f", R.id.btn_g to "g",
            R.id.btn_h to "h", R.id.btn_j to "j", R.id.btn_k to "k",
            R.id.btn_l to "l", R.id.btn_z to "z", R.id.btn_x to "x",
            R.id.btn_c to "c", R.id.btn_v to "v", R.id.btn_b to "b",
            R.id.btn_n to "n", R.id.btn_m to "m"
        )

        val symbols = mapOf(
            R.id.btn_q to "1", R.id.btn_w to "2", R.id.btn_e to "3",
            R.id.btn_r to "4", R.id.btn_t to "5", R.id.btn_y to "6",
            R.id.btn_u to "7", R.id.btn_i to "8", R.id.btn_o to "9",
            R.id.btn_p to "0", R.id.btn_a to "@", R.id.btn_s to "#",
            R.id.btn_d to "$", R.id.btn_f to "%", R.id.btn_g to "&",
            R.id.btn_h to "*", R.id.btn_j to "-", R.id.btn_k to "+",
            R.id.btn_l to "=", R.id.btn_z to "(", R.id.btn_x to ")",
            R.id.btn_c to "/", R.id.btn_v to ":", R.id.btn_b to ";",
            R.id.btn_n to ",", R.id.btn_m to "."
        )

        inputView.findViewById<Button>(R.id.btn_symbols)?.text = if (isSymbolMode) "ABC" else "123"
        inputView.findViewById<Button>(R.id.btn_shift)?.alpha = if (isUpperCase) 1.0f else 0.5f

        val buttonMap = when {
            isSymbolMode -> symbols
            isChineseMode -> pinyinKeys
            isUpperCase -> upperLetters
            else -> lowerLetters
        }

        val allButtonIds = setOf(
            R.id.btn_q, R.id.btn_w, R.id.btn_e, R.id.btn_r, R.id.btn_t,
            R.id.btn_y, R.id.btn_u, R.id.btn_i, R.id.btn_o, R.id.btn_p,
            R.id.btn_a, R.id.btn_s, R.id.btn_d, R.id.btn_f, R.id.btn_g,
            R.id.btn_h, R.id.btn_j, R.id.btn_k, R.id.btn_l, R.id.btn_z,
            R.id.btn_x, R.id.btn_c, R.id.btn_v, R.id.btn_b, R.id.btn_n,
            R.id.btn_m
        )

        allButtonIds.forEach { id ->
            val button = inputView.findViewById<Button>(id)
            val keyValue = buttonMap[id] ?: ""
            button?.text = keyValue
            button?.setOnClickListener {
                handleKeyPress(id, keyValue, inputView)
            }
        }
    }

    private fun handleKeyPress(buttonId: Int, keyValue: String, inputView: View) {
        if (isChineseMode) {
            handlePinyinInput(keyValue, inputView)
        } else {
            currentInputConnection?.commitText(keyValue, 1)
        }
    }

    private fun initVoiceComponents() {
        if (audioRecorder == null) {
            audioRecorder = WavAudioRecorder(this)
            httpWhisperClient = HttpWhisperClient(this)
        }
        
        audioRecorder?.setVADCallback(object : WavAudioRecorder.VADCallback {
            override fun onSegmentReady(file: File, durationMs: Long) {
                android.util.Log.e("SERVICE_CB", "=== onSegmentReady ===")
                android.util.Log.e("SERVICE_CB", "File=${file.name}")
                android.util.Log.e("SERVICE_CB", "Dur=${durationMs}ms")
                
                try {
                    transcribeSegment(file, durationMs)
                } catch (e: Exception) {
                    android.util.Log.e("SERVICE_CB", "Transcribe failed: ${e.message}")
                }
            }
            
            override fun onSpeakingStateChanged(isSpeaking: Boolean) {
                android.util.Log.d("SERVICE_CB", "Speaking=$isSpeaking")
                updateSpeakingUI(isSpeaking)
            }
            
            override fun onMaxDurationReached() {
                android.util.Log.e("SERVICE_CB", "MaxDurationReached")
                GlobalScope.scope.launch {
                    transcriptionText.text = "达到最大时长，正在停止..."
                    stopVoiceInput()
                }
            }
            
            override fun onRecordingStateChanged(state: String) {
                android.util.Log.d("SERVICE_CB", "State=$state")
            }
        })
    }
    
    private fun startVoiceInput() {
        if (isRecording) {
            println("正在录音，点击停止")
            stopVoiceInput()
            return
        }
        
        recordingJob?.cancel()
        
        GlobalScope.scope.launch(Dispatchers.Main) {
            transcriptionResultText.text = ""
        }
        
        recordingJob = GlobalScope.scope.launch {
            try {
                println("开始语音输入")
                GlobalScope.scope.launch(Dispatchers.Main) {
                    transcriptionText.text = "正在连接服务器..."
                }
                
                val checkResult = httpWhisperClient?.checkServer()
                if (checkResult?.isFailure == true) {
                    transcriptionText.text = "无法连接服务器，请检查网络"
                    return@launch
                }
                
                transcriptionResult.clear()
                pendingTranscriptionJobs = 0
                isStopping = false
                
                isRecording = true
                voiceInputButton.text = getString(R.string.voice_input_stop)
                transcriptionText.text = "🎤 开始录音..."
                
                val recordingResult = audioRecorder?.startRecording()
                
                if (recordingResult?.isSuccess == true) {
                    println("录音已开始，进入等待循环")
                    
                    while (isRecording) {
                        updateRecordingUI()
                        
                        if (audioRecorder?.getVADProcessor()?.isMaxDurationReached() == true) {
                            println("达到最大时长，自动停止")
                            break
                        }
                        
                        delay(100)
                    }
                    
                    println("等待循环结束 isRecording=$isRecording")
                    
                    if (isRecording) {
                        stopVoiceInput()
                    }
                    
                } else {
                    val error = recordingResult?.exceptionOrNull()?.message ?: "未知错误"
                    println("录音失败: $error")
                    transcriptionText.text = "录音失败: $error"
                    isRecording = false
                    isStopping = false
                    voiceInputButton.text = getString(R.string.voice_input_start)
                }
                
            } catch (e: Exception) {
                e.printStackTrace()
                println("语音输入异常: ${e.message}")
                transcriptionText.text = "录音失败: ${e.message}"
                isRecording = false
                isStopping = false
                voiceInputButton.text = getString(R.string.voice_input_start)
            }
        }
    }
    
    private fun updateRecordingUI() {
        val vad = audioRecorder?.getVADProcessor() ?: return
        
        val duration = vad.recordingDuration.value
        val isSpeaking = vad.isSpeaking.value
        val segmentCount = vad.segmentCount.value
        val remainingSeconds = 60 - (duration / 1000)
        
        val speakingStatus = if (isSpeaking) "🎤 录音中" else "🔇 请说话"
        val segmentInfo = if (segmentCount > 0) " [已发送${segmentCount}段]" else ""
        
        GlobalScope.scope.launch(Dispatchers.Main) {
            transcriptionText.text = "$speakingStatus$segmentInfo\n剩余 ${remainingSeconds}秒"
        }
    }
    
    private fun updateSpeakingUI(isSpeaking: Boolean) {
        val vad = audioRecorder?.getVADProcessor() ?: return
        val segmentCount = vad.segmentCount.value
        val segmentInfo = if (segmentCount > 0) " [已发送${segmentCount}段]" else ""
        
        val status = if (isSpeaking) "🎤 录音中" else "🔇 请说话"
        GlobalScope.scope.launch(Dispatchers.Main) {
            transcriptionText.text = "$status$segmentInfo"
        }
    }
    
    private fun stopVoiceInput() {
        println("stopVoiceInput被调用: isRecording=$isRecording, isStopping=$isStopping")
        
        if (isStopping) {
            println("已经在停止中，直接返回")
            return
        }
        
        isStopping = true
        isRecording = false
        
        try {
            println("停止录音...")
            GlobalScope.scope.launch(Dispatchers.Main) {
                transcriptionText.text = "正在停止..."
                voiceInputButton.text = getString(R.string.voice_input_start)
            }
            
            audioRecorder?.stopRecording()
            
            println("录音已停止，等待转录完成...")
            
            GlobalScope.scope.launch {
                var waitTime = 0
                while (pendingTranscriptionJobs > 0 && waitTime < 30000) {
                    delay(500)
                    waitTime += 500
                    println("等待转录完成... 剩余: $pendingTranscriptionJobs")
                }
                
                if (pendingTranscriptionJobs > 0) {
                    println("转录超时，强制完成")
                    pendingTranscriptionJobs = 0
                }
                
                if (isStopping) {
                    onAllTranscriptionComplete()
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
            println("停止录音异常: ${e.message}")
            isStopping = false
        }
    }
    
    private fun transcribeSegment(file: File, durationMs: Long) {
        pendingTranscriptionJobs++
        
        android.util.Log.e("TRANSCRIBE", "=== transcribeSegment CALLED ===")
        android.util.Log.e("TRANSCRIBE", "File: ${file.name}, Size: ${file.length()} bytes")
        android.util.Log.e("TRANSCRIBE", "Duration: ${durationMs}ms")
        
        TranscriptionHelper.sendForTranscription(
            file = file,
            durationMs = durationMs,
            onSuccess = { text: String ->
                android.util.Log.e("TRANSCRIBE", "=== onSuccess CALLED ===")
                android.util.Log.e("TRANSCRIBE", "Text: $text")
                
                val segmentCount = audioRecorder?.getVADProcessor()?.segmentCount?.value ?: 0
                
                if (text.isNotEmpty()) {
                    transcriptionResult.append(text)
                    
                    android.util.Log.e("TRANSCRIBE", "Updating UI with text: $text")
                    
                    GlobalScope.scope.launch(Dispatchers.Main) {
                        val currentResult = transcriptionResultText.text.toString()
                        val newResult = if (currentResult.isEmpty()) {
                            text
                        } else {
                            "$currentResult\n$text"
                        }
                        transcriptionResultText.text = newResult
                        transcriptionResultText.scrollToBottom()
                    }
                    
                    println("第${segmentCount}段转录成功: $text")
                }
                
                val jobsRemaining = --pendingTranscriptionJobs
                android.util.Log.e("TRANSCRIBE", "Jobs remaining: $jobsRemaining")
                
                if (jobsRemaining == 0 && !isRecording) {
                    android.util.Log.e("TRANSCRIBE", "All transcription complete, calling onAllTranscriptionComplete")
                    onAllTranscriptionComplete()
                }
            },
            onError = { error: String ->
                android.util.Log.e("TRANSCRIBE", "=== onError CALLED ===")
                android.util.Log.e("TRANSCRIBE", "Error: $error")
                
                val segmentCount = audioRecorder?.getVADProcessor()?.segmentCount?.value ?: 0
                println("第${segmentCount}段转录失败: $error")
                
                val jobsRemaining = --pendingTranscriptionJobs
                android.util.Log.e("TRANSCRIBE", "Jobs remaining after error: $jobsRemaining")
                
                if (jobsRemaining == 0 && !isRecording) {
                    android.util.Log.e("TRANSCRIBE", "All transcription complete (with errors), calling onAllTranscriptionComplete")
                    onAllTranscriptionComplete()
                }
            }
        )
    }
    
    private fun onAllTranscriptionComplete() {
        android.util.Log.e("TRANSCRIBE", "=== onAllTranscriptionComplete CALLED ===")
        
        isStopping = false
        
        val finalText = transcriptionResult.toString()
        android.util.Log.e("TRANSCRIBE", "Final text length: ${finalText.length}")
        android.util.Log.e("TRANSCRIBE", "Final text: $finalText")
        
        GlobalScope.scope.launch(Dispatchers.Main) {
            if (finalText.isNotEmpty()) {
                println("全部转录完成: $finalText")
                transcriptionText.text = "转录完成！"
                
                currentInputConnection?.commitText(finalText, 1)
            } else {
                transcriptionText.text = "未识别到语音"
                transcriptionResultText.text = ""
                currentInputConnection?.commitText("", 1)
            }
            
            transcriptionResult.clear()
        }
    }
    
    override fun onStartInput(attribute: EditorInfo?, restarting: Boolean) {
        super.onStartInput(attribute, restarting)

        // 确保不会显示提取视图，这可以避免一些设备上的显示问题
        setExtractViewShown(false)

        if (audioRecorder == null) {
            audioRecorder = WavAudioRecorder(this)
            httpWhisperClient = HttpWhisperClient(this)
        }

        initVoiceComponents()
    }
    
    override fun onFinishInput() {
        super.onFinishInput()
    }
    
    override fun onDestroy() {
        super.onDestroy()
    }
}
