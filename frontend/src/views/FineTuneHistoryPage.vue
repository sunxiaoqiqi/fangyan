<template>
  <div class="fine-tune-history-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>微调记录</span>
          <el-button type="primary" @click="loadHistory">刷新</el-button>
        </div>
      </template>

      <el-table :data="historyList" stripe style="width: 100%">
        <el-table-column prop="task_name" label="微调事件名称" width="150" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_epochs" label="总轮数" width="80" />
        <el-table-column prop="best_epoch" label="最佳轮数" width="80" />
        <el-table-column prop="best_val_loss" label="最佳Val Loss" width="120">
          <template #default="{ row }">
            {{ row.best_val_loss ? row.best_val_loss.toFixed(4) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="best_wer" label="最佳WER" width="100">
          <template #default="{ row }">
            {{ row.best_wer ? row.best_wer.toFixed(4) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="training_time" label="训练时间" width="120">
          <template #default="{ row }">
            {{ formatDuration(row.training_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="stop_reason" label="停止原因" width="100" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row)">查看详情</el-button>
            <el-button size="small" type="primary" @click="downloadModel(row)" v-if="row.status === 'completed'">下载模型</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="微调详情" width="80%">
      <div v-if="currentDetail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="微调事件名称">{{ currentDetail.task_name }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(currentDetail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentDetail.status)">
              {{ getStatusText(currentDetail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="训练时间">{{ formatDuration(currentDetail.training_time) }}</el-descriptions-item>
          <el-descriptions-item label="总轮数">{{ currentDetail.total_epochs }}</el-descriptions-item>
          <el-descriptions-item label="最佳轮数">{{ currentDetail.best_epoch }}</el-descriptions-item>
          <el-descriptions-item label="最佳Val Loss">{{ currentDetail.best_val_loss ? currentDetail.best_val_loss.toFixed(4) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="最佳WER">{{ currentDetail.best_wer ? currentDetail.best_wer.toFixed(4) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="最佳CER">{{ currentDetail.best_cer ? currentDetail.best_cer.toFixed(4) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="停止原因">{{ currentDetail.stop_reason }}</el-descriptions-item>
          <el-descriptions-item label="模型路径">{{ currentDetail.model_path }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin-top: 20px;">训练参数</h4>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="模型类型">{{ currentDetail.params?.model_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="微调类型">{{ currentDetail.params?.fine_tune_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="学习率">{{ currentDetail.params?.learning_rate || '-' }}</el-descriptions-item>
          <el-descriptions-item label="批次大小">{{ currentDetail.params?.batch_size || '-' }}</el-descriptions-item>
          <el-descriptions-item label="验证比例">{{ currentDetail.params?.validation_split || '-' }}</el-descriptions-item>
          <el-descriptions-item label="数据量">{{ currentDetail.data_count || '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin-top: 20px;">训练报告</h4>
        <el-table :data="currentDetail.epoch_reports" stripe style="width: 100%">
          <el-table-column prop="epoch" label="Epoch" width="80" />
          <el-table-column prop="train_loss" label="Train Loss" width="120">
            <template #default="{ row }">
              {{ row.train_loss ? row.train_loss.toFixed(4) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="val_loss" label="Val Loss" width="120">
            <template #default="{ row }">
              {{ row.val_loss ? row.val_loss.toFixed(4) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="wer" label="WER" width="100">
            <template #default="{ row }">
              {{ row.wer ? row.wer.toFixed(4) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="cer" label="CER" width="100">
            <template #default="{ row }">
              {{ row.cer ? row.cer.toFixed(4) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="learning_rate" label="学习率" width="120">
            <template #default="{ row }">
              {{ row.learning_rate ? row.learning_rate.toExponential(6) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="is_best" label="是否最佳" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_best ? 'success' : 'info'">
                {{ row.is_best ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <h4 style="margin-top: 20px;">评估集WER报告</h4>
        <div v-if="currentDetail.test_wer !== undefined" style="margin-bottom: 10px;">
          <el-tag type="primary" size="large">
            评估集WER: {{ currentDetail.test_wer ? currentDetail.test_wer.toFixed(4) : '-' }}
          </el-tag>
          <el-tag type="info" size="large" style="margin-left: 10px;">
            评估集CER: {{ currentDetail.test_cer ? currentDetail.test_cer.toFixed(4) : '-' }}
          </el-tag>
        </div>
        
        <!-- 按语料包统计 -->
        <h4 style="margin-top: 20px;">按语料包统计</h4>
        <el-table v-if="currentDetail.test_pack_stats && Object.keys(currentDetail.test_pack_stats).length > 0" :data="packStatsList" stripe style="width: 100%">
          <el-table-column prop="pack_name" label="语料包" min-width="150" />
          <el-table-column prop="total" label="样本数" width="100" />
          <el-table-column prop="avg_wer" label="平均WER" width="120">
            <template #default="{ row }">
              {{ row.avg_wer ? row.avg_wer.toFixed(4) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="avg_cer" label="平均CER" width="120">
            <template #default="{ row }">
              {{ row.avg_cer ? row.avg_cer.toFixed(4) : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="showPackDetails(row.pack_id)">
                查看详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-else-if="currentDetail.test_wer !== undefined" class="empty-state">
          评估集为空或无评估数据
        </div>
        
        <!-- 详细数据 -->
        <h4 style="margin-top: 20px;">详细评估数据</h4>
        <el-table v-if="currentDetail.test_wer_details && currentDetail.test_wer_details.length > 0" :data="currentDetail.test_wer_details" stripe style="width: 100%">
          <el-table-column prop="index" label="序号" width="80" />
          <el-table-column prop="pack_name" label="语料包" width="150" />
          <el-table-column prop="label" label="真实文本" min-width="200" />
          <el-table-column prop="prediction" label="预测文本" min-width="200" />
          <el-table-column prop="wer" label="WER" width="100">
            <template #default="{ row }">
              {{ row.wer ? row.wer.toFixed(4) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="cer" label="CER" width="100">
            <template #default="{ row }">
              {{ row.cer ? row.cer.toFixed(4) : '-' }}
            </template>
          </el-table-column>
        </el-table>
        <div v-else-if="currentDetail.test_wer !== undefined" class="empty-state">
          评估集为空或无评估数据
        </div>
      </div>
    </el-dialog>
    
    <!-- 语料包详情对话框 -->
    <el-dialog v-model="packDetailsDialogVisible" :title="`语料包详情 - ${currentPackName}`" width="80%">
      <el-table v-if="currentPackDetails && currentPackDetails.length > 0" :data="currentPackDetails" stripe style="width: 100%">
        <el-table-column prop="index" label="序号" width="80" />
        <el-table-column prop="label" label="真实文本" min-width="200" />
        <el-table-column prop="prediction" label="预测文本" min-width="200" />
        <el-table-column prop="wer" label="WER" width="100">
          <template #default="{ row }">
            {{ row.wer ? row.wer.toFixed(4) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="cer" label="CER" width="100">
          <template #default="{ row }">
            {{ row.cer ? row.cer.toFixed(4) : '-' }}
          </template>
        </el-table-column>
      </el-table>
      <div v-else class="empty-state">
        无数据
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const historyList = ref([])
const detailDialogVisible = ref(false)
const currentDetail = ref(null)
const packDetailsDialogVisible = ref(false)
const currentPackDetails = ref(null)
const currentPackName = ref('')

// 计算语料包统计列表
const packStatsList = computed(() => {
  if (!currentDetail.value || !currentDetail.value.test_pack_stats) {
    return []
  }
  const stats = currentDetail.value.test_pack_stats
  return Object.keys(stats).map(pack_id => {
    const pack = stats[pack_id]
    return {
      pack_id,
      pack_name: pack.pack_name,
      total: pack.total,
      avg_wer: pack.total > 0 ? pack.wer_sum / pack.total : 0,
      avg_cer: pack.total > 0 ? pack.cer_sum / pack.total : 0
    }
  })
})

// 查看语料包详情
const showPackDetails = (pack_id) => {
  if (!currentDetail.value || !currentDetail.value.test_pack_stats) {
    return
  }
  const pack = currentDetail.value.test_pack_stats[pack_id]
  if (pack) {
    currentPackName.value = pack.pack_name
    currentPackDetails.value = pack.details
    packDetailsDialogVisible.value = true
  }
}

const loadHistory = async () => {
  try {
    const res = await api.get('/fine-tune/history')
    if (res.data && res.data.history) {
      historyList.value = res.data.history
    }
  } catch (error) {
    ElMessage.error('加载微调记录失败: ' + error.message)
  }
}

const viewDetail = async (row) => {
  try {
    const res = await api.get(`/fine-tune/history/${row.id}`)
    if (res.data) {
      currentDetail.value = res.data
      detailDialogVisible.value = true
    }
  } catch (error) {
    ElMessage.error('加载微调详情失败: ' + error.message)
  }
}

const downloadModel = (row) => {
  if (row.model_path) {
    window.open(`/api/fine-tune/download/${row.id}`, '_blank')
  }
}

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const formatDuration = (seconds) => {
  if (!seconds) return '-'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  return `${hours}小时${minutes}分钟${secs}秒`
}

const getStatusType = (status) => {
  const map = {
    'running': 'warning',
    'completed': 'success',
    'failed': 'danger'
  }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = {
    'running': '运行中',
    'completed': '已完成',
    'failed': '失败'
  }
  return map[status] || status
}

onMounted(async () => {
  await loadHistory()
})
</script>

<style scoped>
.fine-tune-history-page {
  max-width: 1400px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-state {
  padding: 20px;
  text-align: center;
  color: #999;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-top: 10px;
}
</style>
