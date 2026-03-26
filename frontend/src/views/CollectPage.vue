<template>
  <div class="collect-page">
    <!-- 任务和用户信息 -->
    <el-card class="task-user-info" style="margin-bottom: 20px;">
      <template #header>
        <div class="card-header">
          <span>任务和用户信息</span>
        </div>
      </template>
      <div class="task-user-content">
        <div class="form-item">
          <label>当前用户：</label>
          <span class="user-info">{{ currentUser.username }}</span>
        </div>
        <div class="form-item">
          <label>选择任务：</label>
          <el-select 
            v-model="selectedTaskId" 
            placeholder="请选择任务"
            @change="handleTaskChange"
            style="width: 200px"
          >
            <el-option
              v-for="task in taskList"
              :key="task.task_id"
              :label="task.task_name"
              :value="task.task_id"
            />
          </el-select>
        </div>
      </div>
    </el-card>

    <!-- 语料包选择 -->
    <el-card class="pack-selector">
      <template #header>
        <div class="card-header">
          <span>选择语料包</span>
          <el-button type="primary" size="small" @click="showImportDialog = true">
            导入语料包
          </el-button>
        </div>
      </template>
      <el-select 
        v-model="selectedPackId" 
        placeholder="请选择语料包"
        @change="handlePackChange"
        style="width: 100%"
      >
        <el-option
          v-for="pack in packList"
          :key="pack.pack_id"
          :label="`${pack.pack_id} (${pack.sentence_count}句)`"
          :value="pack.pack_id"
        />
      </el-select>
      
      <div v-if="progress" class="progress-info">
        <el-progress 
          :percentage="progress.percentage" 
          :status="progress.percentage === 100 ? 'success' : ''"
        />
        <div class="progress-details">
          <p>总进度: {{ progress.completed }} / {{ progress.total }} ({{ progress.percentage }}%)</p>
          <p>未录制: {{ unrecordedSentences.length }} 句</p>
          <p>已录制: {{ progress.completed }} 句</p>
        </div>
      </div>
    </el-card>

    <!-- 语料包导入对话框 -->
    <el-dialog 
      v-model="showImportDialog" 
      title="导入语料包"
      width="500px"
    >
      <el-form>
        <el-form-item label="选择CSV文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".csv"
            :on-change="handleFileChange"
            :on-exceed="handleExceed"
            drag
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              将文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                只能上传CSV文件，且不超过10MB
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showImportDialog = false">取消</el-button>
          <el-button type="primary" @click="importScriptPack" :loading="importing">
            导入
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 录音区域 -->
    <el-card v-if="currentSentence" class="recording-area">
      <template #header>
        <div class="card-header">
          <span>当前句子 ({{ currentSentenceIndex + 1 }} / {{ sentences.length }})</span>
        </div>
      </template>

      <!-- 句子展示 -->
      <div class="sentence-display">
        <div class="sentence-text">
          <h2>{{ currentSentence.text_target }}</h2>
          <p class="mandarin-gloss">{{ currentSentence.text_mandarin_gloss }}</p>
          <div class="status-tags">
            <el-tag v-if="currentSentence.category" size="small" type="info">
              {{ currentSentence.category }}
            </el-tag>
            <el-tag :type="getRecordingStatusType()" size="small">
              {{ getRecordingStatusText() }}
            </el-tag>
            <el-tag :type="getAnnotationStatusType()" size="small">
              {{ getAnnotationStatusText() }}
            </el-tag>
          </div>
        </div>
      </div>

      <!-- 录音控制 -->
      <div class="recording-controls">
        <div class="volume-meter">
          <div 
            class="volume-bar" 
            :style="{ width: (volumeLevel * 100) + '%' }"
            :class="{ 'recording': isRecording }"
          ></div>
        </div>
        
        <div class="recording-info">
          <p v-if="isRecording" class="recording-status">
            <el-icon class="is-loading"><Loading /></el-icon>
            正在录音... {{ formatDuration(recordingDuration) }}
          </p>
          <p v-else-if="lastRecordingDuration" class="last-duration">
            上次录音: {{ formatDuration(lastRecordingDuration) }}
          </p>
          
          <div v-if="unrecordedSentences.length > 0" class="unrecorded-selector">
            <el-select 
              v-model="selectedUnrecordedSentence" 
              placeholder="选择未录制的句子"
              @change="jumpToUnrecordedSentence"
              style="width: 100%"
            >
              <el-option
                v-for="sentence in unrecordedSentences"
                :key="sentence.sentence_id"
                :label="`${sentence.sentence_id}: ${sentence.text_target}`"
                :value="sentence.sentence_id"
              />
            </el-select>
          </div>
        </div>

        <div class="button-group">
          <el-button 
            @click="handlePrevSentence"
            :disabled="isRecording || uploading || currentSentenceIndex === 0"
            size="large"
          >
            <el-icon><ArrowLeft /></el-icon>
            上一句
          </el-button>
          
          <!-- 试听按钮 -->
          <el-button 
            v-if="currentSentence && getRecordingStatusText() === '已录制'"
            type="info" 
            size="large"
            @click="playRecording"
            :disabled="isRecording || uploading"
          >
            <el-icon><VideoPlay /></el-icon>
            试听
          </el-button>
          
          <el-button 
            v-if="!isRecording"
            type="primary" 
            size="large"
            @mousedown="handleStartRecording"
            @mouseup="handleStopRecording"
            @mouseleave="handleStopRecording"
            @touchstart="handleStartRecording"
            @touchend="handleStopRecording"
            :loading="uploading"
          >
            <el-icon><Microphone /></el-icon>
            按住说话
          </el-button>
          
          <el-button 
            v-else
            type="danger" 
            size="large"
            @click="handleStopRecording"
          >
            <el-icon><VideoPause /></el-icon>
            停止录音
          </el-button>

          <el-button 
            @click="handleNextSentence"
            :disabled="isRecording || uploading || currentSentenceIndex === sentences.length - 1"
            size="large"
          >
            下一句
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- 质检提示 -->
      <div v-if="qualityCheck.warnings.length > 0" class="quality-warnings">
        <el-alert
          v-for="(warning, index) in qualityCheck.warnings"
          :key="index"
          :title="warning"
          type="warning"
          :closable="false"
          style="margin-bottom: 10px"
        />
      </div>
    </el-card>

    <!-- 空状态 -->
    <el-empty v-else description="请先选择语料包" />

    <!-- 完成提示 -->
    <el-dialog
      v-model="showCompleteDialog"
      title="采集完成"
      width="400px"
    >
      <p>恭喜！您已完成 {{ selectedPackId }} 语料包的采集。</p>
      <template #footer>
        <el-button @click="showCompleteDialog = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Microphone, VideoPause, VideoPlay, Loading, ArrowLeft, ArrowRight, UploadFilled } from '@element-plus/icons-vue'
import { scriptPackAPI, collectAPI } from '../api'
import api from '../api'
import { AudioRecorder } from '../utils/audioRecorder'

// 数据
const packList = ref([])
const selectedPackId = ref('')
const sentences = ref([])
const currentSentenceIndex = ref(0)
const currentSentence = ref(null)
const progress = ref(null)
const sentenceStatus = ref({})
const unrecordedSentences = ref([])
const selectedUnrecordedSentence = ref('')

// 任务和用户相关
const currentUser = ref({})
const taskList = ref([])
const selectedTaskId = ref('')

// 录音相关
const audioRecorder = new AudioRecorder()
const isRecording = ref(false)
const recordingDuration = ref(0)
const lastRecordingDuration = ref(0)
const volumeLevel = ref(0)
let volumeCheckInterval = null
let durationInterval = null
const uploading = ref(false)
const qualityCheck = ref({ warnings: [] })

// UI状态
const showCompleteDialog = ref(false)
const showImportDialog = ref(false)
const importing = ref(false)
const uploadRef = ref(null)
const selectedFile = ref(null)

// 获取说话人ID（使用登录用户ID）
const getSpeakerId = () => {
  const userStr = localStorage.getItem('user')
  if (userStr) {
    const user = JSON.parse(userStr)
    return user.user_id
  }
  // 降级方案：如果未登录，使用随机ID
  let speakerId = localStorage.getItem('speaker_id')
  if (!speakerId) {
    speakerId = 'spk_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
    localStorage.setItem('speaker_id', speakerId)
  }
  return speakerId
}

// 加载用户信息
const loadUserInfo = () => {
  const userStr = localStorage.getItem('user')
  if (userStr) {
    currentUser.value = JSON.parse(userStr)
  }
}

// 加载任务列表
const loadTaskList = async () => {
  try {
    const res = await api.get('/auth/tasks')
    if (res.data && res.data.tasks) {
      taskList.value = res.data.tasks
      // 选择默认任务
      const defaultTask = res.data.tasks.find(task => task.is_default)
      if (defaultTask) {
        selectedTaskId.value = defaultTask.task_id
      }
    }
  } catch (error) {
    console.error('加载任务列表失败:', error)
    ElMessage.error('加载任务列表失败: ' + error.message)
  }
}

// 加载语料包列表
const loadPackList = async (taskId = selectedTaskId.value) => {
  try {
    const res = await scriptPackAPI.getPackList(taskId)
    if (res.data && res.data.packs) {
      packList.value = res.data.packs
      if (packList.value.length === 0) {
        ElMessage.warning('语料包列表为空，请检查CSV文件')
      }
    } else {
      throw new Error('返回数据格式错误')
    }
  } catch (error) {
    console.error('加载语料包列表失败:', error)
    const errorMsg = error.response?.data?.detail || error.message || '未知错误'
    ElMessage.error(`加载语料包列表失败: ${errorMsg}`)
    
    // 提供更详细的错误提示
    if (error.code === 'ECONNREFUSED' || error.message.includes('Network Error')) {
      ElMessage.error('无法连接到后端服务，请确保后端服务已启动（http://localhost:8001）')
    }
  }
}

// 处理任务变化
const handleTaskChange = async (taskId) => {
  // 任务变化时重新加载语料包
  console.log('任务已变更为:', taskId)
  selectedPackId.value = '' // 重置语料包选择
  await loadPackList(taskId)
}

// 加载语料包内容
const loadPack = async (packId) => {
  try {
    const res = await scriptPackAPI.getPack(packId, selectedTaskId.value)
    sentences.value = res.data.sentences
    currentSentenceIndex.value = 0
    updateCurrentSentence()
    await loadProgress()
  } catch (error) {
    ElMessage.error('加载语料包失败: ' + error.message)
  }
}

// 更新当前句子
const updateCurrentSentence = () => {
  if (sentences.value.length > 0 && currentSentenceIndex.value < sentences.value.length) {
    currentSentence.value = sentences.value[currentSentenceIndex.value]
  } else {
    currentSentence.value = null
  }
}

// 加载进度
const loadProgress = async (skipAutoJump = false) => {
  if (!selectedPackId.value) return
  
  try {
    const speakerId = getSpeakerId()
    const res = await collectAPI.getProgress(speakerId, selectedPackId.value, selectedTaskId.value)
    progress.value = res.data
    
    // 如果有已完成记录，跳转到第一个未完成的句子（只在语料包初次加载时执行）
    if (!skipAutoJump && progress.value.completed_sentences && progress.value.completed_sentences.length > 0) {
      const completedSet = new Set(progress.value.completed_sentences)
      const firstIncompleteIndex = sentences.value.findIndex(
        s => !completedSet.has(s.sentence_id)
      )
      if (firstIncompleteIndex >= 0) {
        currentSentenceIndex.value = firstIncompleteIndex
        updateCurrentSentence()
      }
    }
  } catch (error) {
    console.error('加载进度失败:', error)
  }
}

// 加载句子状态
const loadSentenceStatus = async () => {
  if (!selectedPackId.value) return
  
  try {
    const speakerId = getSpeakerId()
    const res = await collectAPI.getRecordings(speakerId)
    const recordings = res.data.recordings
    
    // 构建句子状态映射（根据任务ID过滤）
    const statusMap = {}
    recordings.forEach(recording => {
      if (recording.pack_id === selectedPackId.value && 
          (!recording.task_id || recording.task_id === selectedTaskId.value)) {
        statusMap[recording.sentence_id] = {
          recorded: true,
          status: recording.status,
          audio_path_wav: recording.audio_path_wav,
          audio_path_webm: recording.audio_path_webm
        }
      }
    })
    
    sentenceStatus.value = statusMap
    
    // 生成未录制句子列表
    updateUnrecordedSentences()
  } catch (error) {
    console.error('加载句子状态失败:', error)
  }
}

// 更新未录制句子列表
const updateUnrecordedSentences = () => {
  unrecordedSentences.value = sentences.value.filter(sentence => {
    const status = sentenceStatus.value[sentence.sentence_id]
    return !status || !status.recorded
  })
  selectedUnrecordedSentence.value = ''
}

// 跳转到选中的未录制句子
const jumpToUnrecordedSentence = () => {
  if (selectedUnrecordedSentence.value) {
    const index = sentences.value.findIndex(
      s => s.sentence_id === selectedUnrecordedSentence.value
    )
    if (index >= 0) {
      currentSentenceIndex.value = index
      updateCurrentSentence()
    }
  }
}

// 语料包切换
const handlePackChange = async (packId) => {
  if (packId) {
    await loadPack(packId)
    await loadSentenceStatus()
  }
}

// 处理文件选择
const handleFileChange = (file) => {
  selectedFile.value = file.raw
}

// 处理文件超出限制
const handleExceed = (files) => {
  ElMessage.warning('只能上传一个CSV文件')
  uploadRef.value.clearFiles()
}

// 导入语料包
const importScriptPack = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择要导入的CSV文件')
    return
  }

  if (!selectedTaskId.value) {
    ElMessage.warning('请先选择任务')
    return
  }

  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('task_id', selectedTaskId.value)

    const res = await api.post('/script-pack/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    if (res.data.success) {
      ElMessage.success(res.data.message)
      showImportDialog.value = false
      selectedFile.value = null
      uploadRef.value.clearFiles()
      
      // 重新加载语料包列表
      await loadPackList(selectedTaskId.value)
    }
  } catch (error) {
    console.error('导入语料包失败:', error)
    const errorMsg = error.response?.data?.detail || error.message || '未知错误'
    ElMessage.error('导入语料包失败: ' + errorMsg)
  } finally {
    importing.value = false
  }
}

// 开始录音
const handleStartRecording = async (e) => {
  e.preventDefault()
  if (isRecording.value || uploading.value) return

  try {
    await audioRecorder.startRecording()
    isRecording.value = true
    recordingDuration.value = 0
    qualityCheck.value = { warnings: [] }
    
    // 开始音量检测
    const checkVolume = () => {
      if (isRecording.value) {
        volumeLevel.value = audioRecorder.getVolumeLevel()
        requestAnimationFrame(checkVolume)
      }
    }
    checkVolume()
    
    // 开始计时
    durationInterval = setInterval(() => {
      recordingDuration.value += 100
    }, 100)
  } catch (error) {
    ElMessage.error(error.message)
  }
}

// 停止录音
const handleStopRecording = async (e) => {
  e.preventDefault()
  if (!isRecording.value) return

  try {
    // 停止计时
    if (durationInterval) {
      clearInterval(durationInterval)
    }
    
    const result = await audioRecorder.stopRecording()
    isRecording.value = false
    lastRecordingDuration.value = result.duration
    volumeLevel.value = 0
    
    // 质检
    qualityCheck.value = await audioRecorder.checkQuality(result.blob, result.duration)
    
    if (!qualityCheck.value.isValid) {
      ElMessage.warning('录音质量不合格，请重录')
      return
    }
    
    // 上传
    await uploadRecording(result.blob, result.duration)
  } catch (error) {
    ElMessage.error('录音失败: ' + error.message)
    isRecording.value = false
  }
}

// 上传录音
const uploadRecording = async (blob, duration) => {
  if (!currentSentence.value) return

  uploading.value = true
  
  try {
    const speakerId = getSpeakerId()
    const formData = new FormData()
    formData.append('audio', blob, 'recording.webm')
    formData.append('speaker_id', speakerId)
    formData.append('pack_id', selectedPackId.value)
    formData.append('sentence_id', currentSentence.value.sentence_id)
    formData.append('text_target', currentSentence.value.text_target)
    formData.append('duration_ms', duration.toString())
    formData.append('task_id', selectedTaskId.value)

    const res = await collectAPI.uploadRecording(formData)
    
    if (res.data.success) {
        ElMessage.success('上传成功！')
        
        // 更新进度和句子状态（跳过自动跳转）
        await loadProgress(true)
        await loadSentenceStatus()
        
        // 检查是否完成
        if (res.data.is_pack_complete) {
          showCompleteDialog.value = true
        }
        // 不自动进入下一句，保持在当前句子
      }
  } catch (error) {
    ElMessage.error('上传失败: ' + error.message)
  } finally {
    uploading.value = false
  }
}

// 跳过句子
const handleSkip = async () => {
  try {
    await ElMessageBox.confirm('确定要跳过这句吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    currentSentenceIndex.value++
    updateCurrentSentence()
  } catch {
    // 用户取消
  }
}

// 上一句
const handlePrevSentence = () => {
  if (currentSentenceIndex.value > 0) {
    currentSentenceIndex.value--
    updateCurrentSentence()
  }
}

// 下一句
const handleNextSentence = () => {
  if (currentSentenceIndex.value < sentences.value.length - 1) {
    currentSentenceIndex.value++
    updateCurrentSentence()
  }
}

// 试听录音
const playRecording = () => {
  if (!currentSentence.value) return
  
  const status = sentenceStatus.value[currentSentence.value.sentence_id]
  if (!status) {
    ElMessage.warning('未找到录音状态')
    return
  }
  
  // 调试信息
  console.log('录音状态:', status)
  
  // 确保有音频路径
  const audioPath = status.audio_path_wav || status.audio_path_webm
  if (!audioPath) {
    ElMessage.warning('未找到录音文件路径')
    return
  }
  
  // 提取文件名（处理不同格式的路径）
  let fileName = ''
  try {
    fileName = audioPath.split('/').pop().split('\\').pop()
    console.log('提取的文件名:', fileName)
  } catch (error) {
    console.error('提取文件名失败:', error)
    ElMessage.error('处理音频路径失败')
    return
  }
  
  // 构建完整的音频URL（添加时间戳避免缓存）
  const audioUrl = `/api/audio/${fileName}?t=${Date.now()}`
  console.log('音频URL:', audioUrl)
  
  // 创建音频元素并播放
  const audio = new Audio()
  audio.src = audioUrl
  
  // 监听音频事件
  audio.addEventListener('error', (event) => {
    console.error('音频加载错误:', event)
    ElMessage.error('音频加载失败，请检查网络连接')
  })
  
  audio.play().catch(error => {
    console.error('播放失败:', error)
    ElMessage.error('播放失败: ' + error.message)
  })
}

// 格式化时长
const formatDuration = (ms) => {
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

// 获取录制状态类型
const getRecordingStatusType = () => {
  if (!currentSentence.value) return ''
  const status = sentenceStatus.value[currentSentence.value.sentence_id]
  return status && status.recorded ? 'success' : 'info'
}

// 获取录制状态文本
const getRecordingStatusText = () => {
  if (!currentSentence.value) return ''
  const status = sentenceStatus.value[currentSentence.value.sentence_id]
  return status && status.recorded ? '已录制' : '未录制'
}

// 获取标注状态类型
const getAnnotationStatusType = () => {
  if (!currentSentence.value) return ''
  const status = sentenceStatus.value[currentSentence.value.sentence_id]
  if (!status) return 'info'
  switch (status.status) {
    case 'transcribed':
      return 'warning'
    case 'reviewed':
      return 'success'
    case 'rejected':
      return 'danger'
    default:
      return 'info'
  }
}

// 获取标注状态文本
const getAnnotationStatusText = () => {
  if (!currentSentence.value) return ''
  const status = sentenceStatus.value[currentSentence.value.sentence_id]
  if (!status) return '未标注'
  switch (status.status) {
    case 'transcribed':
      return '已标注'
    case 'reviewed':
      return '已审核'
    case 'rejected':
      return '已拒绝'
    default:
      return '未标注'
  }
}



// 生命周期
onMounted(async () => {
  loadUserInfo()
  await loadTaskList()
  await loadPackList()
})

onUnmounted(() => {
  if (isRecording.value) {
    audioRecorder.cancelRecording()
  }
  if (durationInterval) {
    clearInterval(durationInterval)
  }
})
</script>

<style scoped>
.collect-page {
  max-width: 800px;
  margin: 0 auto;
}

.task-user-info {
  margin-bottom: 20px;
}

.task-user-content {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-items: center;
}

.form-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.form-item label {
  font-weight: 500;
  color: #606266;
}

.user-info {
  font-size: 16px;
  color: #409EFF;
  font-weight: 500;
}

.pack-selector {
  margin-bottom: 20px;
}

.progress-info {
  margin-top: 15px;
}

.progress-info .progress-details {
  margin-top: 10px;
}

.progress-info .progress-details p {
  text-align: center;
  color: #666;
  margin: 5px 0;
  font-size: 14px;
}

.recording-area {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sentence-display {
  text-align: center;
  padding: 30px 20px;
  background: #f9f9f9;
  border-radius: 8px;
  margin-bottom: 30px;
}

.sentence-text h2 {
  font-size: 28px;
  color: #333;
  margin-bottom: 15px;
  line-height: 1.6;
}

.mandarin-gloss {
  color: #666;
  font-size: 16px;
  margin-bottom: 10px;
}

.status-tags {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
  justify-content: center;
}

.evaluation-toggle {
  margin-top: 20px;
  text-align: center;
}

.recording-controls {
  margin: 30px 0;
}

.volume-meter {
  width: 100%;
  height: 8px;
  background: #e4e7ed;
  border-radius: 4px;
  margin-bottom: 20px;
  overflow: hidden;
}

.volume-bar {
  height: 100%;
  background: #67c23a;
  transition: width 0.1s;
}

.volume-bar.recording {
  background: #f56c6c;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.recording-info {
  text-align: center;
  margin-bottom: 20px;
  min-height: 24px;
}

.recording-status {
  color: #f56c6c;
  font-weight: 500;
}

.last-duration {
  color: #909399;
}

.unrecorded-selector {
  margin-top: 15px;
}

.button-group {
  display: flex;
  justify-content: center;
  gap: 15px;
}

.button-group .el-button {
  min-width: 120px;
}

.quality-warnings {
  margin-top: 20px;
}

/* 手机端响应式设计 */
@media screen and (max-width: 768px) {
  .task-user-content {
    flex-direction: column;
    align-items: stretch;
    gap: 15px;
  }
  
  .form-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 5px;
  }
  
  .form-item label {
    font-size: 14px;
  }
  
  .sentence-display {
    padding: 20px 15px;
  }
  
  .sentence-text h2 {
    font-size: 20px;
  }
  
  .mandarin-gloss {
    font-size: 14px;
  }
  
  .button-group {
    flex-direction: column;
    gap: 10px;
  }
  
  .button-group .el-button {
    min-width: auto;
    width: 100%;
  }
  
  .status-tags {
    justify-content: center;
  }
}

/* 小屏幕手机 */
@media screen and (max-width: 480px) {
  .sentence-text h2 {
    font-size: 18px;
  }
  
  .mandarin-gloss {
    font-size: 13px;
  }
  
  .progress-info .progress-details p {
    font-size: 12px;
  }
  
  .el-card {
    margin-bottom: 10px;
  }
  
  .el-card__header {
    padding: 10px 15px;
  }
  
  .el-card__body {
    padding: 15px;
  }
}
</style>

