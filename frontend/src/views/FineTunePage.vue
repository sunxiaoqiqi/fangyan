<template>
  <div class="fine-tune-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Whisper 模型微调</span>
          <div class="header-info">
            <el-tooltip
              content="最佳模型选择逻辑：\n1. 优先考虑 WER（词错误率），选择 WER 最低的模型\n2. 其次考虑验证损失，选择验证损失最低的模型\n3. 训练过程中会记录每一轮的训练损失、验证损失、WER 和 CER\n4. 训练结束后，使用最佳模型进行评估集的评估"
              placement="bottom"
              effect="dark"
              :show-after="300"
            >
              <el-button type="info" size="small" circle>
                <el-icon><QuestionFilled /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
      </template>

      <!-- 数据选择 -->
      <div class="section">
        <h3>1. 选择微调数据</h3>
        <el-checkbox-group v-model="selectedDataTypes" class="data-types">
          <el-checkbox label="recorded">已录制数据</el-checkbox>
          <el-checkbox label="transcribed">已标注数据</el-checkbox>
          <el-checkbox label="reviewed">已审核数据</el-checkbox>
        </el-checkbox-group>
        
        <div v-if="selectedDataTypes.length > 0" class="data-filters">
          <el-select v-model="selectedTaskId" placeholder="选择任务" style="width: 200px; margin-right: 10px">
            <el-option
              v-for="task in taskList"
              :key="task.task_id"
              :label="task.task_name"
              :value="task.task_id"
            />
          </el-select>
          <el-select v-model="selectedPackId" placeholder="选择语料包" style="width: 200px; margin-right: 10px">
            <el-option
              v-for="pack in packList"
              :key="pack.pack_id"
              :label="`${pack.pack_id} (${pack.sentence_count}句)`"
              :value="pack.pack_id"
            />
          </el-select>
          <el-button type="primary" @click="loadDataPreview">加载数据预览</el-button>
        </div>
      </div>

      <!-- 数据预览 -->
      <div v-if="dataPreview.length > 0" class="section">
        <h3>数据预览</h3>
        <div class="data-stats">
          <el-tag type="info" size="large">
            共 {{ totalDataCount }} 条数据
          </el-tag>
          <el-tag v-if="dataPreview.length < totalDataCount" type="warning" size="large">
            显示前 {{ dataPreview.length }} 条
          </el-tag>
        </div>
        <el-table :data="dataPreview" stripe style="width: 100%">
          <el-table-column prop="sentence_id" label="句子ID" width="120" />
          <el-table-column prop="task_id" label="任务ID" width="120" />
          <el-table-column prop="text_target" label="目标文本" show-overflow-tooltip />
          <el-table-column prop="text_transcript" label="转写文本" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)">
                {{ getStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <div class="data-stats">
          <p>共 {{ dataPreview.length }} 条数据</p>
        </div>
      </div>

      <!-- 参数设置 -->
      <div class="section">
        <h3>2. 设置微调参数</h3>
        <el-form :model="fineTuneParams" label-width="120px">
          <el-form-item label="模型类型">
            <el-select v-model="fineTuneParams.model_type" style="width: 200px">
              <el-option label="Whisper Small" value="small" />
              <el-option label="Whisper Medium" value="medium" />
              <el-option label="Whisper Large" value="large" />
            </el-select>
          </el-form-item>
          <el-form-item label="微调类型">
            <el-radio-group v-model="fineTuneParams.fine_tune_type">
              <el-radio label="full">全微调</el-radio>
              <el-radio label="lora">LoRA 微调</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="学习率">
            <el-input-number v-model="fineTuneParams.learning_rate" :min="0.00001" :max="0.01" :step="0.00001" />
          </el-form-item>
          <el-form-item label="训练轮数">
            <el-input-number v-model="fineTuneParams.epochs" :min="1" :max="100" :step="1" />
          </el-form-item>
          <el-form-item label="批次大小">
            <el-input-number v-model="fineTuneParams.batch_size" :min="1" :max="64" :step="1" />
          </el-form-item>
          <el-form-item label="验证比例">
            <el-input-number v-model="fineTuneParams.validation_split" :min="0.01" :max="0.5" :step="0.01" />
          </el-form-item>
        </el-form>
      </div>

      <!-- 开始微调 -->
      <div class="section">
        <h3>3. 开始微调</h3>
        <el-form :model="fineTuneForm" label-width="120px">
          <el-form-item label="微调事件名称">
            <el-input v-model="fineTuneForm.task_name" placeholder="请输入微调事件名称"></el-input>
          </el-form-item>
        </el-form>
        <el-button type="primary" size="large" @click="startFineTuning" :loading="isLoading">
          <el-icon><Refresh /></el-icon>
          开始微调
        </el-button>
        <el-button size="large" @click="resetForm">
          重置
        </el-button>
      </div>

      <!-- 微调状态 -->
      <div v-if="fineTuneStatus" class="section">
        <h3>微调状态</h3>
        <el-card v-if="fineTuneStatus.status === 'running'" type="warning" :body-style="{ padding: '20px' }">
          <div class="status-content">
            <el-icon class="is-loading"><Loading /></el-icon>
            <p>微调正在进行中...</p>
            <p>当前进度: {{ fineTuneStatus.progress }}%</p>
            <p>当前轮次: {{ fineTuneStatus.current_epoch }} / {{ fineTuneStatus.total_epochs }}</p>
          </div>
        </el-card>
        <el-card v-else-if="fineTuneStatus.status === 'completed'" type="success" :body-style="{ padding: '20px' }">
          <div class="status-content">
            <el-icon><Check /></el-icon>
            <p>微调完成！</p>
            <p>模型保存路径: {{ fineTuneStatus.model_path }}</p>
            <p>训练时间: {{ fineTuneStatus.training_time }}秒</p>
            <el-button type="primary" @click="downloadModel">下载模型</el-button>
          </div>
        </el-card>
        <el-card v-else-if="fineTuneStatus.status === 'failed'" type="danger" :body-style="{ padding: '20px' }">
          <div class="status-content">
            <el-icon><Close /></el-icon>
            <p>微调失败</p>
            <p>错误信息: {{ fineTuneStatus.error_message }}</p>
          </div>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Loading, Check, Close, QuestionFilled } from '@element-plus/icons-vue'
import { scriptPackAPI } from '../api'
import api from '../api'

// 数据
const packList = ref([])
const taskList = ref([])
const selectedDataTypes = ref([])
const selectedTaskId = ref('')
const selectedPackId = ref('')
const dataPreview = ref([])
const totalDataCount = ref(0)  // 添加总数据量变量
const isLoading = ref(false)
const fineTuneStatus = ref(null)

// 微调参数（CPU优化：使用更小的模型和更少的epoch）
const fineTuneParams = ref({
  model_type: 'tiny',  // 使用tiny模型，比small快很多
  fine_tune_type: 'full',  // 默认使用全微调
  learning_rate: 0.0001,
  epochs: 3,  // 减少epoch数量
  batch_size: 4,  // 减小batch_size
  validation_split: 0.1
})

// 微调表单
const fineTuneForm = ref({
  task_name: ''
})

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
const loadPackList = async () => {
  try {
    const res = await scriptPackAPI.getPackList()
    if (res.data && res.data.packs) {
      packList.value = res.data.packs
    }
  } catch (error) {
    ElMessage.error('加载语料包列表失败: ' + error.message)
  }
}

// 加载数据预览
const loadDataPreview = async () => {
  if (!selectedDataTypes.value.length) {
    ElMessage.warning('请至少选择一种数据类型')
    return
  }

  isLoading.value = true
  try {
    const res = await api.get('/fine-tune/data-preview', {
      params: {
        data_types: selectedDataTypes.value.join(','),
        task_id: selectedTaskId.value,
        pack_id: selectedPackId.value
      }
    })
    dataPreview.value = res.data.data
    totalDataCount.value = res.data.total || 0  // 保存总数据量
  } catch (error) {
    ElMessage.error('加载数据预览失败: ' + error.message)
  } finally {
    isLoading.value = false
  }
}

// 开始微调
const startFineTuning = async () => {
  if (!selectedDataTypes.value.length) {
    ElMessage.warning('请至少选择一种数据类型')
    return
  }

  console.log('开始微调，fineTuneForm:', fineTuneForm.value)
  console.log('开始微调，task_name:', fineTuneForm.value.task_name)

  isLoading.value = true
  try {
    const requestData = {
      data_types: selectedDataTypes.value,
      task_id: selectedTaskId.value,
      pack_id: selectedPackId.value,
      params: fineTuneParams.value,
      task_name: fineTuneForm.value.task_name,
      fine_tune_type: fineTuneParams.value.fine_tune_type
    }
    console.log('发送微调请求:', requestData)
    
    const res = await api.post('/fine-tune/start', requestData)
    
    if (res.data.success) {
      ElMessage.success('微调任务已启动')
      // 轮询微调状态
      pollFineTuneStatus(res.data.task_id)
    }
  } catch (error) {
    ElMessage.error('启动微调失败: ' + error.message)
  } finally {
    isLoading.value = false
  }
}

// 轮询微调状态
const pollFineTuneStatus = (taskId) => {
  const interval = setInterval(async () => {
    try {
      const res = await api.get(`/fine-tune/status/${taskId}`)
      fineTuneStatus.value = res.data
      
      if (res.data.status === 'completed' || res.data.status === 'failed') {
        clearInterval(interval)
      }
    } catch (error) {
      console.error('获取微调状态失败:', error)
      clearInterval(interval)
    }
  }, 3000)
}

// 下载模型
const downloadModel = () => {
  if (fineTuneStatus.value && fineTuneStatus.value.model_path) {
    window.open(`/api/fine-tune/download/${fineTuneStatus.value.task_id}`, '_blank')
  }
}

// 重置表单
const resetForm = () => {
  selectedDataTypes.value = []
  selectedTaskId.value = ''
  selectedPackId.value = ''
  dataPreview.value = []
  fineTuneStatus.value = null
  fineTuneParams.value = {
    model_type: 'small',
    fine_tune_type: 'full',  // 默认使用全微调
    learning_rate: 0.0001,
    epochs: 10,
    batch_size: 8,
    validation_split: 0.1
  }
  fineTuneForm.value = {
    task_name: ''
  }
}

// 获取状态类型
const getStatusType = (status) => {
  const map = {
    'pending': 'info',
    'transcribed': 'warning',
    'reviewed': 'success',
    'rejected': 'danger'
  }
  return map[status] || 'info'
}

// 获取状态文本
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
})
</script>

<style scoped>
.fine-tune-page {
  max-width: 1000px;
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

.data-types {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.data-filters {
  margin-top: 20px;
}

.data-stats {
  margin-top: 10px;
  text-align: right;
  color: #666;
}

.status-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.status-content .el-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.status-content p {
  margin: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>