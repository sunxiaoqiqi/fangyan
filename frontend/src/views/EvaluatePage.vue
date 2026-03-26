<template>
  <div class="evaluate-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>模型评估</span>
        </div>
      </template>

      <!-- Whisper服务器模型切换 -->
      <div class="section">
        <h3>1. Whisper服务器 - 模型切换</h3>
        <div class="model-switch-section">
          <el-row :gutter="20">
            <el-col :span="12">
              <div class="current-model">
                <span class="label">当前模型:</span>
                <el-tag type="success" size="large">{{ whisperServerStatus.current_model || '未加载' }}</el-tag>
                <el-tag v-if="whisperServerStatus.model_loading" type="warning">加载中...</el-tag>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="model-actions">
                <el-button type="primary" @click="refreshWhisperModels" :loading="isLoadingModels">
                  <el-icon><Refresh /></el-icon>
                  刷新模型列表
                </el-button>
              </div>
            </el-col>
          </el-row>
          
          <el-divider />
          
          <div class="model-list">
            <h4>可用模型:</h4>
            <el-table :data="whisperModels" stripe style="width: 100%">
              <el-table-column prop="name" label="模型名称" width="200" />
              <el-table-column prop="type" label="类型" width="150">
                <template #default="{ row }">
                  <el-tag :type="getModelTypeTag(row.type)">
                    {{ row.type }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="描述" />
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button 
                    type="primary" 
                    size="small" 
                    @click="switchWhisperModel(row)"
                    :disabled="row.name === whisperServerStatus.current_model || whisperServerStatus.model_loading"
                  >
                    {{ row.name === whisperServerStatus.current_model ? '当前' : '切换' }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </div>

      <!-- 评估模型选择 -->
      <div class="section">
        <h3>2. 选择评估模型</h3>
        <el-select v-model="selectedModel" placeholder="选择要评估的模型" style="width: 400px">
          <el-option
            v-for="model in modelList"
            :key="model.path"
            :label="model.name"
            :value="model.path"
          />
        </el-select>
      </div>

      <!-- 测试数据 -->
      <div class="section">
        <h3>3. 测试数据</h3>
        <el-upload
          class="upload-demo"
          action=""
          :auto-upload="false"
          :on-change="handleFileChange"
          :multiple="true"
          accept=".wav,.webm"
        >
          <el-button type="primary">
            <el-icon><Upload /></el-icon>
            上传音频文件
          </el-button>
        </el-upload>
        <div v-if="testFiles.length > 0" class="file-list">
          <h4>已上传文件:</h4>
          <el-table :data="testFiles" style="width: 100%">
            <el-table-column prop="name" label="文件名" />
            <el-table-column prop="size" label="大小" width="100" />
            <el-table-column label="参考文本" width="300">
              <template #default="{ row }">
                <el-input v-model="row.text" placeholder="请输入参考文本" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button type="danger" size="small" @click="removeFile(row)">
                  <el-icon><Delete /></el-icon>
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        
        <!-- 手动输入测试数据 -->
        <div class="manual-test">
          <h4>或手动输入测试数据:</h4>
          <el-table :data="manualTestData" style="width: 100%">
            <el-table-column label="音频路径" width="300">
              <template #default="{ row }">
                <el-input v-model="row.audio_path" placeholder="请输入音频文件路径" />
              </template>
            </el-table-column>
            <el-table-column label="参考文本" width="400">
              <template #default="{ row }">
                <el-input v-model="row.text" placeholder="请输入参考文本" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button type="danger" size="small" @click="removeManualTest(row)">
                  <el-icon><Delete /></el-icon>
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button type="primary" size="small" @click="addManualTest">
            <el-icon><Plus /></el-icon>
            添加测试数据
          </el-button>
        </div>
      </div>

      <!-- 开始评估 -->
      <div class="section">
        <h3>4. 开始评估</h3>
        <el-button type="primary" size="large" @click="startEvaluation" :loading="isLoading">
          <el-icon><Refresh /></el-icon>
          开始评估
        </el-button>
        <el-button size="large" @click="resetForm">
          重置
        </el-button>
      </div>

      <!-- 评估结果 -->
      <div v-if="evaluationResult" class="section">
        <h3>评估结果</h3>
        <el-card v-if="evaluationResult.success" type="success" :body-style="{ padding: '20px' }">
          <div class="result-content">
            <h4>平均 CER: {{ (evaluationResult.avg_cer * 100).toFixed(2) }}%</h4>
            <el-table :data="evaluationResult.results" stripe style="width: 100%">
              <el-table-column prop="audio_path" label="音频文件" />
              <el-table-column prop="reference" label="参考文本" show-overflow-tooltip />
              <el-table-column prop="prediction" label="预测文本" show-overflow-tooltip />
              <el-table-column prop="cer" label="CER" width="100">
                <template #default="{ row }">
                  <el-tag :type="getCerType(row.cer)">
                    {{ (row.cer * 100).toFixed(2) }}%
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="error" label="错误信息" v-if="hasErrors" show-overflow-tooltip />
            </el-table>
          </div>
        </el-card>
        <el-card v-else type="danger" :body-style="{ padding: '20px' }">
          <div class="result-content">
            <p>评估失败: {{ evaluationResult.message }}</p>
          </div>
        </el-card>
      </div>

      <!-- 模型转换和量化 -->
      <div class="section">
        <h3>5. 模型转换和量化 (GGML)</h3>
        <div class="convert-section">
          <el-select v-model="convertModelPath" placeholder="选择要转换的模型" style="width: 400px; margin-right: 20px">
            <el-option
              v-for="model in modelList"
              :key="model.path"
              :label="model.name"
              :value="model.path"
            />
          </el-select>
          <el-select v-model="quantizationType" placeholder="选择量化类型" style="width: 200px; margin-right: 20px">
            <el-option label="q4_0" value="q4_0" />
            <el-option label="q4_1" value="q4_1" />
            <el-option label="q5_0" value="q5_0" />
            <el-option label="q5_1" value="q5_1" />
            <el-option label="q8_0" value="q8_0" />
          </el-select>
          <el-button type="primary" @click="startConversion" :loading="isConverting">
            <el-icon><Refresh /></el-icon>
            转换并量化
          </el-button>
        </div>
        
        <!-- 转换结果 -->
        <div v-if="conversionResult" class="result-section">
          <el-card v-if="conversionResult.success" type="success" :body-style="{ padding: '20px' }">
            <div class="result-content">
              <h4>转换和量化成功</h4>
              <div class="conversion-info">
                <p><strong>GGML模型:</strong> {{ conversionResult.result.ggml_model }}</p>
                <p><strong>量化模型:</strong> {{ conversionResult.result.quantized_model }}</p>
                <p><strong>量化类型:</strong> {{ conversionResult.result.quantization_type }}</p>
              </div>
            </div>
          </el-card>
          <el-card v-else type="danger" :body-style="{ padding: '20px' }">
            <div class="result-content">
              <p>转换失败: {{ conversionResult.message }}</p>
            </div>
          </el-card>
        </div>
      </div>

      <!-- 模型转换 CTranslate2 -->
      <div class="section">
        <h3>6. 模型转换 (CTranslate2)</h3>
        <div class="convert-section">
          <el-select v-model="convertModelPath" placeholder="选择要转换的模型" style="width: 400px; margin-right: 20px">
            <el-option
              v-for="model in modelList"
              :key="model.path"
              :label="model.name"
              :value="model.path"
            />
          </el-select>
          <el-select v-model="ct2ComputeType" placeholder="选择计算类型" style="width: 200px; margin-right: 20px">
            <el-option label="int8" value="int8" />
            <el-option label="int8_float16" value="int8_float16" />
            <el-option label="float16" value="float16" />
            <el-option label="float32" value="float32" />
          </el-select>
          <el-button type="success" @click="startCTranslate2Conversion" :loading="isConverting">
            <el-icon><Refresh /></el-icon>
            转换为CTranslate2
          </el-button>
        </div>
        
        <!-- CTranslate2 转换结果 -->
        <div v-if="ct2ConversionResult" class="result-section">
          <el-card v-if="ct2ConversionResult.success" type="success" :body-style="{ padding: '20px' }">
            <div class="result-content">
              <h4>转换成功!</h4>
              <div class="conversion-info">
                <p><strong>输出路径:</strong> {{ ct2ConversionResult.output_path }}</p>
                <p><strong>计算类型:</strong> {{ ct2ConversionResult.compute_type }}</p>
              </div>
              <p style="color: #67c23a; margin-top: 10px;">
                转换后的模型已保存到 models 目录，可以在 Whisper服务器 中切换使用！
              </p>
            </div>
          </el-card>
          <el-card v-else type="danger" :body-style="{ padding: '20px' }">
            <div class="result-content">
              <p>转换失败: {{ ct2ConversionResult.message }}</p>
            </div>
          </el-card>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Upload, Delete, Plus } from '@element-plus/icons-vue'
import api from '../api'

// Whisper服务器相关数据
const whisperServerStatus = ref({
  current_model: null,
  current_model_type: null,
  model_loading: false,
  model_loaded: false
})
const whisperModels = ref([])
const isLoadingModels = ref(false)

// 数据
const modelList = ref([])
const selectedModel = ref('')
const testFiles = ref([])
const manualTestData = ref([])
const isLoading = ref(false)
const evaluationResult = ref(null)

// 模型转换相关数据
const convertModelPath = ref('')
const quantizationType = ref('q4_0')
const isConverting = ref(false)
const conversionResult = ref(null)
const whisperCppStatus = ref(null)

// CTranslate2 转换
const ct2ComputeType = ref('int8')
const ct2ConversionResult = ref(null)

// 计算属性
const hasErrors = computed(() => {
  return evaluationResult.value && evaluationResult.value.results.some(item => item.error)
})

// Whisper服务器 API
const WHISPER_API_BASE = 'http://192.168.1.3:5000'

async function fetchWhisperServerStatus() {
  try {
    const res = await fetch(`${WHISPER_API_BASE}/health`)
    const data = await res.json()
    whisperServerStatus.value = data
  } catch (error) {
    console.error('获取Whisper服务器状态失败:', error)
    ElMessage.error('无法连接到Whisper服务器')
  }
}

async function refreshWhisperModels() {
  isLoadingModels.value = true
  try {
    const res = await fetch(`${WHISPER_API_BASE}/models`)
    const data = await res.json()
    if (data.success) {
      whisperModels.value = data.models
      whisperServerStatus.value.current_model = data.current_model
      whisperServerStatus.value.current_model_type = data.current_model_type
      ElMessage.success('模型列表已刷新')
    }
  } catch (error) {
    console.error('获取模型列表失败:', error)
    ElMessage.error('获取模型列表失败')
  } finally {
    isLoadingModels.value = false
  }
}

async function switchWhisperModel(model) {
  try {
    ElMessage.info(`正在切换到模型: ${model.name}...`)
    const res = await fetch(`${WHISPER_API_BASE}/model/switch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model_name: model.path,
        model_type: model.type
      })
    })
    const data = await res.json()
    if (data.success) {
      whisperServerStatus.value.current_model = data.current_model
      whisperServerStatus.value.current_model_type = data.current_model_type
      ElMessage.success(data.message)
      await refreshWhisperModels()
    } else {
      ElMessage.error(data.message)
    }
  } catch (error) {
    console.error('切换模型失败:', error)
    ElMessage.error('切换模型失败')
  }
}

// 加载模型列表
const loadModelList = async () => {
  try {
    const res = await api.get('/fine-tune/models')
    if (res.data && res.data.models) {
      modelList.value = res.data.models
    }
  } catch (error) {
    console.error('加载模型列表失败:', error)
    ElMessage.error('加载模型列表失败: ' + error.message)
  }
}

// 检查whisper.cpp状态
const checkWhisperCppStatus = async () => {
  try {
    const res = await api.get('/fine-tune/check-whisper-cpp')
    if (res.data && res.data.success) {
      whisperCppStatus.value = res.data
      if (!res.data.ready) {
        ElMessage.warning('whisper.cpp未就绪，请确保已克隆并编译whisper.cpp')
      }
    }
  } catch (error) {
    console.error('检查whisper.cpp状态失败:', error)
  }
}

// 处理文件上传
const handleFileChange = (file) => {
  testFiles.value.push({
    name: file.name,
    size: formatFileSize(file.size),
    path: file.raw,
    text: ''
  })
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / 1048576).toFixed(2) + ' MB'
}

// 移除文件
const removeFile = (row) => {
  const index = testFiles.value.findIndex(file => file.name === row.name)
  if (index !== -1) {
    testFiles.value.splice(index, 1)
  }
}

// 添加手动测试数据
const addManualTest = () => {
  manualTestData.value.push({
    audio_path: '',
    text: ''
  })
}

// 移除手动测试数据
const removeManualTest = (row) => {
  const index = manualTestData.value.indexOf(row)
  if (index !== -1) {
    manualTestData.value.splice(index, 1)
  }
}

// 开始评估
const startEvaluation = async () => {
  if (!selectedModel.value) {
    ElMessage.warning('请选择要评估的模型')
    return
  }

  const testData = []
  
  for (const item of testFiles.value) {
    if (item.text && item.path) {
      try {
        const formData = new FormData()
        formData.append('audio', item.path)
        formData.append('speaker_id', 'eval_speaker')
        formData.append('task_id', 'evaluation')
        formData.append('pack_id', 'eval_pack')
        formData.append('sentence_id', 'eval_sentence_' + Date.now())
        formData.append('text_target', item.text)
        
        const uploadRes = await api.post('/collect/upload', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        })
        
        if (uploadRes.data.success) {
          testData.push({
            audio_path: uploadRes.data.recording_id,
            text: item.text
          })
        }
      } catch (error) {
        console.error('上传音频文件失败:', error)
        ElMessage.error('上传音频文件失败: ' + error.message)
      }
    }
  }
  
  manualTestData.value.forEach(item => {
    if (item.audio_path && item.text) {
      testData.push({
        audio_path: item.audio_path,
        text: item.text
      })
    }
  })

  if (testData.length === 0) {
    ElMessage.warning('请至少添加一条测试数据')
    return
  }

  isLoading.value = true
  try {
    const res = await api.post('/fine-tune/evaluate', {
      model_path: selectedModel.value,
      test_data: testData
    })
    
    if (res.data.success) {
      evaluationResult.value = res.data
      ElMessage.success('评估完成')
    } else {
      evaluationResult.value = res.data
      ElMessage.error('评估失败: ' + res.data.message)
    }
  } catch (error) {
    console.error('评估失败:', error)
    ElMessage.error('评估失败: ' + error.message)
  } finally {
    isLoading.value = false
  }
}

// 重置表单
const resetForm = () => {
  selectedModel.value = ''
  testFiles.value = []
  manualTestData.value = []
  evaluationResult.value = null
}

// 开始模型转换和量化 (GGML)
const startConversion = async () => {
  if (!convertModelPath.value) {
    ElMessage.warning('请选择要转换的模型')
    return
  }

  isConverting.value = true
  try {
    const res = await api.post('/fine-tune/convert', {
      model_path: convertModelPath.value,
      quantization_type: quantizationType.value
    })
    
    if (res.data.success) {
      conversionResult.value = res.data
      ct2ConversionResult.value = null
      ElMessage.success('模型转换和量化成功')
    } else {
      conversionResult.value = res.data
      ElMessage.error('转换失败: ' + res.data.message)
    }
  } catch (error) {
    console.error('转换失败:', error)
    ElMessage.error('转换失败: ' + error.message)
  } finally {
    isConverting.value = false
  }
}

// 开始 CTranslate2 转换
const startCTranslate2Conversion = async () => {
  if (!convertModelPath.value) {
    ElMessage.warning('请选择要转换的模型')
    return
  }

  isConverting.value = true
  try {
    const res = await api.post('/fine-tune/convert-ctranslate2', {
      model_path: convertModelPath.value,
      compute_type: ct2ComputeType.value
    })
    
    if (res.data.success) {
      ct2ConversionResult.value = res.data
      conversionResult.value = null
      ElMessage.success('CTranslate2转换成功')
    } else {
      ct2ConversionResult.value = res.data
      ElMessage.error('转换失败: ' + res.data.message)
    }
  } catch (error) {
    console.error('CTranslate2转换失败:', error)
    ElMessage.error('CTranslate2转换失败: ' + error.message)
  } finally {
    isConverting.value = false
  }
}

// 获取模型类型标签颜色
const getModelTypeTag = (type) => {
  if (type === 'faster-whisper') return 'success'
  if (type === 'ctranslate2') return 'primary'
  if (type === 'huggingface') return 'warning'
  return 'info'
}

// 获取 CER 类型
const getCerType = (cer) => {
  if (cer < 0.1) return 'success'
  if (cer < 0.3) return 'warning'
  return 'danger'
}

// 生命周期
onMounted(async () => {
  await loadModelList()
  await checkWhisperCppStatus()
  await fetchWhisperServerStatus()
  await refreshWhisperModels()
  addManualTest()
})
</script>

<style scoped>
.evaluate-page {
  max-width: 1200px;
  margin: 0 auto;
}

.section {
  margin-bottom: 30px;
  padding: 20px;
  background: #f9f9f9;
  border-radius: 8px;
}

.card-header {
  font-size: 18px;
  font-weight: bold;
}

.model-switch-section {
  padding: 10px;
}

.current-model {
  display: flex;
  align-items: center;
  gap: 10px;
}

.current-model .label {
  font-weight: bold;
}

.model-actions {
  display: flex;
  justify-content: flex-end;
}

.model-list {
  margin-top: 20px;
}

.model-list h4 {
  margin-bottom: 10px;
}

.convert-section {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.result-section {
  margin-top: 20px;
}

.result-content {
  line-height: 1.8;
}

.conversion-info {
  background: #f0f9ff;
  padding: 15px;
  border-radius: 4px;
  margin-top: 10px;
}

.conversion-info p {
  margin: 5px 0;
}

.manual-test {
  margin-top: 20px;
}

.manual-test h4 {
  margin-bottom: 10px;
}

.file-list {
  margin-top: 20px;
}

.file-list h4 {
  margin-bottom: 10px;
}
</style>
