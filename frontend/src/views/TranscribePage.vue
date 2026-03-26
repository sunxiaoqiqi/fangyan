<template>
  <div class="transcribe-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>标注工作台</span>
          <div class="header-actions">
            <el-select
              v-model="filterTask"
              placeholder="选择任务"
              style="width: 160px; margin-right: 10px"
              @change="handleTaskChange"
            >
              <el-option label="全部任务" value="" />
              <el-option v-for="task in taskList" :key="task.task_id" :label="task.task_name" :value="task.task_id" />
            </el-select>
            <el-select
              v-model="filterPack"
              placeholder="选择语料包"
              style="width: 160px; margin-right: 10px"
              @change="loadRecordings"
            >
              <el-option label="全部语料包" value="" />
              <el-option v-for="pack in packList" :key="pack.pack_id" :label="`${pack.pack_id}`" :value="pack.pack_id" />
            </el-select>
            <el-select
              v-model="filterDataset"
              placeholder="选择数据性质"
              style="width: 140px; margin-right: 10px"
              @change="loadRecordings"
            >
              <el-option label="全部性质" value="" />
              <el-option label="训练集" value="train" />
              <el-option label="验证集" value="val" />
              <el-option label="评估集" value="eval" />
            </el-select>
            <el-select
              v-model="filterStatus"
              placeholder="选择状态"
              style="width: 140px; margin-right: 10px"
              @change="loadRecordings"
            >
              <el-option label="全部状态" value="" />
              <el-option label="待标注" value="pending" />
              <el-option label="已标注" value="transcribed" />
              <el-option label="已审核" value="reviewed" />
              <el-option label="已拒绝" value="rejected" />
            </el-select>
            <el-button @click="loadRecordings" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <!-- 统计信息 + 数据集比例设置 -->
      <div class="stats-and-split">
        <div class="stats-bar">
          <el-statistic title="待标注" :value="stats.pending" />
          <el-statistic title="已标注" :value="stats.transcribed" />
          <el-statistic title="已审核" :value="stats.reviewed" />
          <el-statistic title="完成率" :value="stats.completion_rate" suffix="%" />
        </div>

        <div class="split-settings">
          <div class="split-title">数据集划分（仅在标注页设置）</div>
          <div class="split-inputs">
            <div class="split-item">
              <span>任务</span>
              <el-select v-model="splitTaskId" placeholder="选择任务" style="width: 150px">
                <el-option label="全部任务" value="" />
                <el-option v-for="task in taskList" :key="task.task_id" :label="task.task_name" :value="task.task_id" />
              </el-select>
            </div>
            <div class="split-item">
              <span>训练集</span>
              <el-input-number v-model="splitRatios.train" :min="0" :max="100" /> %
            </div>
            <div class="split-item">
              <span>验证集</span>
              <el-input-number v-model="splitRatios.val" :min="0" :max="100" /> %
            </div>
            <div class="split-item">
              <span>评估集</span>
              <el-input-number v-model="splitRatios.eval" :min="0" :max="100" /> %
            </div>
            <div class="split-item total">
              合计：{{ splitTotal }} %
            </div>
          </div>
          <div class="split-actions">
            <el-button type="primary" size="small" @click="applySplit" :disabled="splitTotal === 0">
              按比例分配（已标注数据）
            </el-button>
            <el-text type="info" size="small">
              说明：只对已标注/已审核的数据设置训练/验证/评估标签，可在下表逐条手动修改。
            </el-text>
          </div>
          <div class="split-summary" v-if="stats.split">
            <el-text size="small">
              当前：训练 {{ stats.split.train }} 条，验证 {{ stats.split.val }} 条，评估 {{ stats.split.eval }} 条
            </el-text>
          </div>
        </div>
      </div>

      <!-- 录音列表 + 批量操作 -->
      <div class="recordings-list">
        <div class="batch-actions">
          <el-button
            type="primary"
            size="small"
            :disabled="selectedRecordings.length === 0"
            @click="batchSetTranscribed"
          >
            批量设为已标注
          </el-button>
          <el-button
            type="success"
            size="small"
            :disabled="selectedRecordings.length === 0"
            @click="openBatchSplitDialog"
          >
            批量修改数据性质
          </el-button>
          <el-text v-if="selectedRecordings.length > 0" size="small" class="selected-tip">
            已选中 {{ selectedRecordings.length }} 条
          </el-text>
        </div>

        <el-table
          :data="recordings"
          stripe
          style="width: 100%"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="40" />
          <el-table-column prop="sentence_id" label="句子ID" width="120" />
          <el-table-column prop="pack_id" label="语料包" width="80" />
          <el-table-column prop="task_name" label="任务" width="120" />
          <el-table-column prop="text_target" label="目标文本" show-overflow-tooltip />
          <el-table-column prop="duration_ms" label="时长" width="100">
            <template #default="{ row }">
              {{ formatDuration(row.duration_ms) }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)">
                {{ getStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="dataset_split" label="数据性质" width="160">
            <template #default="{ row }">
              <el-select
                v-model="row.dataset_split"
                placeholder="未设置"
                size="small"
                style="width: 130px"
                @change="val => updateDatasetSplit(row, val)"
              >
                <el-option label="未设置" :value="null" />
                <el-option label="训练集" value="train" />
                <el-option label="验证集" value="val" />
                <el-option label="评估集" value="eval" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <el-button size="small" @click="openTranscribeDialog(row)">
                {{ row.status === 'pending' ? '标注' : '编辑' }}
              </el-button>
              <el-button 
                v-if="row.status !== 'pending'" 
                size="small" 
                type="warning" 
                @click="resetToPending(row)"
              >
                重置为未标注
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadRecordings"
          @current-change="loadRecordings"
        />
      </div>
    </el-card>

    <!-- 标注对话框 -->
    <el-dialog
      v-model="showTranscribeDialog"
      title="标注录音"
      width="800px"
      @close="resetTranscribeForm"
    >
      <div v-if="currentRecording" class="transcribe-dialog">
        <!-- 音频播放器 -->
        <div class="audio-player">
          <audio
            ref="audioPlayer"
            :src="getAudioUrl(currentRecording.audio_path_wav)"
            controls
            style="width: 100%"
          />
        </div>

        <!-- 目标文本 -->
        <div class="text-section">
          <h4>目标文本（提示文本）：</h4>
          <el-input
            v-model="currentRecording.text_target"
            type="textarea"
            :rows="2"
            readonly
          />
        </div>

        <!-- 转写文本 -->
        <div class="text-section">
          <h4>转写文本：</h4>
          <el-input
            v-model="transcribeForm.text_transcript"
            type="textarea"
            :rows="4"
            placeholder="请根据音频内容填写转写文本..."
            :autosize="{ minRows: 4, maxRows: 8 }"
          />
          <div class="hint">
            <el-text type="info" size="small">
              提示：如果用户读错了，请按实际读音转写；如果是方言词，请按规范写法转写
            </el-text>
          </div>
        </div>

        <!-- 备注 -->
        <div class="text-section">
          <h4>备注（可选）：</h4>
          <el-input
            v-model="transcribeForm.notes"
            type="textarea"
            :rows="2"
            placeholder="备注信息..."
          />
        </div>
      </div>

      <template #footer>
        <el-button @click="showTranscribeDialog = false">取消</el-button>
        <el-button type="danger" @click="handleReject">拒绝</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          提交标注
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量修改数据性质对话框 -->
    <el-dialog
      v-model="batchSplitDialogVisible"
      title="批量修改数据性质"
      width="400px"
    >
      <p style="margin-bottom: 10px;">
        将选中的 {{ selectedRecordings.length }} 条数据的数据性质统一设置为：
      </p>
      <el-select v-model="batchSplitValue" placeholder="请选择" style="width: 100%;">
        <el-option label="训练集" value="train" />
        <el-option label="验证集" value="val" />
        <el-option label="评估集" value="eval" />
        <el-option label="取消设置（置为空）" :value="null" />
      </el-select>
      <template #footer>
        <el-button @click="batchSplitDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmBatchSplit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import api from '../api'

// 数据
const loading = ref(false)
const recordings = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)
const filterStatus = ref('')
const filterTask = ref('')
const filterPack = ref('')
const filterDataset = ref('')
const taskList = ref([])
const packList = ref([])
const stats = ref({
  total: 0,
  pending: 0,
  transcribed: 0,
  reviewed: 0,
  rejected: 0,
  completion_rate: 0,
  split: {
    train: 0,
    val: 0,
    eval: 0
  }
})

// 数据集比例设置（百分比）
const splitRatios = ref({
  train: 80,
  val: 10,
  eval: 10
})

// 数据集划分任务选择
const splitTaskId = ref('')

const splitTotal = computed(() => {
  return splitRatios.value.train + splitRatios.value.val + splitRatios.value.eval
})

// 标注对话框
const showTranscribeDialog = ref(false)
const currentRecording = ref(null)
const audioPlayer = ref(null)
const submitting = ref(false)
const transcribeForm = ref({
  text_transcript: '',
  notes: ''
})

// 批量选择
const selectedRecordings = ref([])

// 加载录音列表
const loadRecordings = async () => {
  loading.value = true
  try {
    const offset = (currentPage.value - 1) * pageSize.value
    const endpoint = filterStatus.value === 'pending' ? '/transcribe/pending' : '/transcribe/list'
    const params = {
      limit: pageSize.value,
      offset: offset
    }
    
    if (filterStatus.value && filterStatus.value !== 'pending') {
      params.status = filterStatus.value
    }
    
    if (filterTask.value) {
      params.task_id = filterTask.value
    }
    
    if (filterPack.value) {
      params.pack_id = filterPack.value
    }
    
    if (filterDataset.value) {
      params.dataset_split = filterDataset.value
    }
    
    console.log('筛选参数:', params)
    console.log('请求端点:', endpoint)
    
    const res = await api.get(endpoint, { params })
    
    console.log('响应数据:', res.data)
    recordings.value = res.data.recordings
    total.value = res.data.total
  } catch (error) {
    console.error('加载录音列表失败:', error)
    ElMessage.error('加载录音列表失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 加载统计信息
const loadStats = async () => {
  try {
    const params = {}
    if (filterTask.value) {
      params.task_id = filterTask.value
    }
    const res = await api.get('/transcribe/stats/summary', { params })
    stats.value = res.data
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

// 加载任务列表
const loadTaskList = async () => {
  try {
    const res = await api.get('/auth/tasks')
    if (res.data && res.data.tasks) {
      taskList.value = res.data.tasks
    }
  } catch (error) {
    console.error('加载任务列表失败:', error)
  }
}

// 加载语料包列表
const loadPackList = async () => {
  try {
    const params = {}
    if (filterTask.value) {
      params.task_id = filterTask.value
    }
    const res = await api.get('/script-pack/list', { params })
    if (res.data && res.data.packs) {
      packList.value = res.data.packs
    }
  } catch (error) {
    console.error('加载语料包列表失败:', error)
  }
}

// 处理任务变化
const handleTaskChange = async (val) => {
  filterPack.value = ''
  await loadPackList()
  await loadRecordings()
}

// 选中变化
const handleSelectionChange = (selection) => {
  selectedRecordings.value = selection
}

// 打开标注对话框
const openTranscribeDialog = async (recording) => {
  try {
    const res = await api.get(`/transcribe/${recording.recording_id}`)
    currentRecording.value = res.data
    transcribeForm.value.text_transcript = res.data.text_transcript || res.data.text_target || ''
    transcribeForm.value.notes = res.data.notes || ''
    showTranscribeDialog.value = true
    
    // 自动播放音频
    setTimeout(() => {
      if (audioPlayer.value) {
        audioPlayer.value.play().catch(e => {
          console.log('自动播放失败（需要用户交互）:', e)
        })
      }
    }, 300)
  } catch (error) {
    ElMessage.error('加载录音详情失败: ' + error.message)
  }
}

// 提交标注
const handleSubmit = async () => {
  if (!transcribeForm.value.text_transcript.trim()) {
    ElMessage.warning('请填写转写文本')
    return
  }

  submitting.value = true
  try {
    const formData = new FormData()
    formData.append('text_transcript', transcribeForm.value.text_transcript)
    if (transcribeForm.value.notes) {
      formData.append('notes', transcribeForm.value.notes)
    }

    await api.post(`/transcribe/${currentRecording.value.recording_id}/transcribe`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    ElMessage.success('标注提交成功！')
    showTranscribeDialog.value = false
    await loadRecordings()
    await loadStats()
  } catch (error) {
    ElMessage.error('提交失败: ' + error.message)
  } finally {
    submitting.value = false
  }
}

// 拒绝录音
const handleReject = async () => {
  try {
    await ElMessageBox.prompt('请输入拒绝原因', '拒绝录音', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputType: 'textarea'
    }).then(async ({ value }) => {
      const formData = new FormData()
      if (value) {
        formData.append('reason', value)
      }

      await api.post(`/transcribe/${currentRecording.value.recording_id}/reject`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      ElMessage.success('已标记为拒绝')
      showTranscribeDialog.value = false
      await loadRecordings()
      await loadStats()
    })
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败: ' + error.message)
    }
  }
}

// 重置为未标注
const resetToPending = async (recording) => {
  try {
    await ElMessageBox.confirm('确定要将此录音重置为未标注状态吗？', '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await api.post(`/transcribe/${recording.recording_id}/reset`)

    ElMessage.success('已重置为未标注状态')
    await loadRecordings()
    await loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败: ' + error.message)
    }
  }
}

// 更新单条记录的数据集性质
const updateDatasetSplit = async (recording, value) => {
  try {
    const formData = new FormData()
    if (value) {
      formData.append('dataset_split', value)
    }
    await api.post(`/transcribe/${recording.recording_id}/dataset_split`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    ElMessage.success('数据性质已更新')
    await loadStats()
  } catch (error) {
    ElMessage.error('更新数据性质失败: ' + error.message)
  }
}

// 一键按比例分配数据集
const applySplit = async () => {
  if (splitTotal.value <= 0) {
    ElMessage.warning('请先设置有效的比例')
    return
  }

  try {
    let message = `将按当前比例（训练 ${splitRatios.value.train}%，验证 ${splitRatios.value.val}%，评估 ${splitRatios.value.eval}%）重新分配`
    if (splitTaskId.value) {
      message += `任务「${taskList.value.find(t => t.task_id === splitTaskId.value)?.task_name || splitTaskId.value}」的`
    } else {
      message += '所有'
    }
    message += '已标注数据的数据性质，是否继续？'

    await ElMessageBox.confirm(
      message,
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const formData = new FormData()
    formData.append('train_ratio', String(splitRatios.value.train))
    formData.append('val_ratio', String(splitRatios.value.val))
    formData.append('eval_ratio', String(splitRatios.value.eval))
    if (splitTaskId.value) {
      formData.append('task_id', splitTaskId.value)
    }

    await api.post('/transcribe/apply_split', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    ElMessage.success('已按比例重新分配数据集性质')
    await loadRecordings()
    await loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('分配失败: ' + (error.message || error))
    }
  }
}

// 批量设为已标注
const batchSetTranscribed = async () => {
  if (selectedRecordings.value.length === 0) return

  try {
    await ElMessageBox.confirm(
      `确定将选中的 ${selectedRecordings.value.length} 条记录设置为“已标注”吗？`,
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const formData = new FormData()
    selectedRecordings.value.forEach(r => {
      formData.append('recording_ids', r.recording_id)
    })
    formData.append('status', 'transcribed')

    await api.post('/transcribe/batch/status', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    ElMessage.success('批量设置成功')
    await loadRecordings()
    await loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('批量设置失败: ' + (error.message || error))
    }
  }
}

// 批量修改数据性质
const batchSplitDialogVisible = ref(false)
const batchSplitValue = ref('train')

const openBatchSplitDialog = () => {
  batchSplitValue.value = 'train'
  batchSplitDialogVisible.value = true
}

const confirmBatchSplit = async () => {
  if (selectedRecordings.value.length === 0) {
    batchSplitDialogVisible.value = false
    return
  }

  try {
    const formData = new FormData()
    selectedRecordings.value.forEach(r => {
      formData.append('recording_ids', r.recording_id)
    })
    if (batchSplitValue.value) {
      formData.append('dataset_split', batchSplitValue.value)
    }

    await api.post('/transcribe/batch/dataset_split', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    ElMessage.success('批量修改数据性质成功')
    batchSplitDialogVisible.value = false
    await loadRecordings()
    await loadStats()
  } catch (error) {
    ElMessage.error('批量修改失败: ' + (error.message || error))
  }
}

// 重置表单
const resetTranscribeForm = () => {
  currentRecording.value = null
  transcribeForm.value = {
    text_transcript: '',
    notes: ''
  }
}

// 获取音频URL
const getAudioUrl = (path) => {
  if (!path) return ''
  // 如果是相对路径，转换为API路径
  if (path.startsWith('http')) {
    return path
  }
  return `/api/audio/${encodeURIComponent(path)}`
}

// 格式化时长
const formatDuration = (ms) => {
  if (!ms) return '0:00'
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

// 状态类型
const getStatusType = (status) => {
  const map = {
    'pending': 'info',
    'transcribed': 'warning',
    'reviewed': 'success',
    'rejected': 'danger'
  }
  return map[status] || 'info'
}

// 状态文本
const getStatusText = (status) => {
  const map = {
    'pending': '待标注',
    'transcribed': '已标注',
    'reviewed': '已审核',
    'rejected': '已拒绝'
  }
  return map[status] || status
}

// 生命周期
onMounted(async () => {
  await loadTaskList()
  await loadPackList()
  await loadStats()
  await loadRecordings()
})
</script>

<style scoped>
.transcribe-page {
  max-width: 1400px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stats-and-split {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.stats-bar {
  flex: 1;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.split-settings {
  flex: 1.4;
  padding: 16px 20px;
  background: #fdfdfd;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.split-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.split-inputs {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px 16px;
}

.split-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.split-item span {
  font-size: 13px;
  color: #606266;
}

.split-item.total {
  margin-left: auto;
  font-size: 13px;
  color: #606266;
}

.split-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
}

.split-summary {
  margin-top: 4px;
}

.recordings-list {
  margin-top: 20px;
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.selected-tip {
  margin-left: 8px;
  color: #909399;
}

.transcribe-dialog {
  padding: 10px 0;
}

.audio-player {
  margin-bottom: 20px;
}

.text-section {
  margin-bottom: 20px;
}

.text-section h4 {
  margin-bottom: 10px;
  color: #606266;
  font-size: 14px;
}

.hint {
  margin-top: 8px;
}

.el-pagination {
  margin-top: 20px;
  justify-content: center;
}
</style>



