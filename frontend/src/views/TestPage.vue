<template>
  <div class="test-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>语音转文本测试</span>
        </div>
      </template>

      <!-- 模型选择 -->
      <div class="section">
        <h3>1. 选择模型</h3>
        <el-select v-model="selectedModel" placeholder="选择模型" style="width: 300px">
          <el-option label="默认模型 (Whisper Small)" value="default" />
          <el-option v-for="model in customModels" :key="model.path" :label="model.name" :value="model.path" />
        </el-select>
      </div>

      <!-- 语音录制 -->
      <div class="section">
        <h3>2. 录制语音</h3>
        <div class="recording-area">
          <div class="volume-meter" :class="{ 'recording': isRecording }">
            <div class="volume-bar" :style="{ height: volumeLevel + '%' }"></div>
          </div>
          
          <div class="recording-info">
            <p v-if="isRecording" class="recording-status">
              <el-icon class="is-loading"><Loading /></el-icon>
              正在录音... {{ formatDuration(recordingDuration) }}
            </p>
            <p v-else-if="lastRecordingDuration" class="last-duration">
              上次录音: {{ formatDuration(lastRecordingDuration) }}
            </p>
          </div>

          <div class="button-group">
            <el-button 
              v-if="!isRecording"
              type="primary" 
              size="large"
              @mousedown="handleStartRecording"
              @mouseup="handleStopRecording"
              @mouseleave="handleStopRecording"
              @touchstart="handleStartRecording"
              @touchend="handleStopRecording"
              :disabled="isProcessing"
            >
              <el-icon><Microphone /></el-icon>
              按住说话
            </el-button>
            
            <el-button 
              v-else
              type="danger" 
              size="large"
              @click="handleStopRecording"
              :disabled="isProcessing"
            >
              <el-icon><VideoPause /></el-icon>
              停止录音
            </el-button>
          </div>
        </div>
      </div>

      <!-- 转录结果 -->
      <div v-if="transcription" class="section">
        <h3>3. 转录结果</h3>
        <el-input
          v-model="transcription"
          type="textarea"
          :rows="4"
          readonly
        />
      </div>

      <!-- 处理状态 -->
      <div v-if="isProcessing" class="section processing">
        <el-icon class="is-loading"><Loading /></el-icon>
        <p>正在处理，请稍候...</p>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Microphone, VideoPause, Loading } from '@element-plus/icons-vue'
import api from '../api'
import { AudioRecorder } from '../utils/audioRecorder'

// 数据
const selectedModel = ref('default')
const customModels = ref([])
const isRecording = ref(false)
const isProcessing = ref(false)
const recordingDuration = ref(0)
const lastRecordingDuration = ref(0)
const volumeLevel = ref(0)
const transcription = ref('')

// 录音相关
const audioRecorder = new AudioRecorder()
let recordingTimer = null

// 加载自定义模型
const loadCustomModels = async () => {
  try {
    const res = await api.get('/audio/models')
    customModels.value = res.data.models || []
  } catch (error) {
    console.error('加载自定义模型失败:', error)
  }
}

// 开始录音
const handleStartRecording = async (e) => {
  e.preventDefault()
  
  try {
    await audioRecorder.startRecording()
    isRecording.value = true
    recordingDuration.value = 0
    
    // 开始计时
    recordingTimer = setInterval(() => {
      recordingDuration.value++
    }, 1000)
    
    // 监听音量
    setInterval(() => {
      const level = audioRecorder.getVolumeLevel()
      volumeLevel.value = level * 100
    }, 100)
  } catch (error) {
    ElMessage.error('开始录音失败: ' + error.message)
  }
}

// 停止录音
const handleStopRecording = async () => {
  try {
    if (!isRecording.value) return
    
    isRecording.value = false
    clearInterval(recordingTimer)
    
    const { blob, duration } = await audioRecorder.stopRecording()
    lastRecordingDuration.value = duration
    
    // 上传音频并转录
    await transcribeAudio(blob, duration)
  } catch (error) {
    console.error('停止录音错误:', error)
    // 只在非重复调用时显示错误
    if (isRecording.value) {
      ElMessage.error('停止录音失败: ' + error.message)
    }
  }
}

// 转录音频
const transcribeAudio = async (audioBlob, duration) => {
  isProcessing.value = true
  transcription.value = ''
  
  try {
    const formData = new FormData()
    formData.append('audio_file', audioBlob, 'recording.webm')
    formData.append('model_path', selectedModel.value)
    formData.append('language', 'zh')
    
    const res = await api.post('/audio/transcribe', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    
    transcription.value = res.data.transcription
  } catch (error) {
    ElMessage.error('转录失败: ' + error.message)
  } finally {
    isProcessing.value = false
  }
}

// 格式化时长
const formatDuration = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// 生命周期
onMounted(async () => {
  await loadCustomModels()
})

onUnmounted(() => {
  if (isRecording.value) {
    audioRecorder.stopRecording().catch(() => {})
  }
  if (recordingTimer) {
    clearInterval(recordingTimer)
  }
})
</script>

<style scoped>
.test-page {
  max-width: 800px;
  margin: 0 auto;
}

.section {
  margin-bottom: 30px;
  padding: 20px;
  background: #f9f9f9;
  border-radius: 8px;
}

.section h3 {
  margin-bottom: 20px;
  color: #333;
  font-size: 18px;
}

.recording-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.volume-meter {
  width: 20px;
  height: 150px;
  background: #e0e0e0;
  border-radius: 10px;
  overflow: hidden;
  position: relative;
}

.volume-meter.recording {
  background: #e6f7ff;
}

.volume-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  background: #409eff;
  transition: height 0.1s ease;
}

.recording-info {
  text-align: center;
}

.recording-status {
  color: #409eff;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.last-duration {
  color: #909399;
}

.button-group {
  display: flex;
  gap: 10px;
}

.processing {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 40px;
}

.processing .el-icon {
  font-size: 48px;
  color: #409eff;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>