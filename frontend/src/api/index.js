import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000  // 增加超时时间到60秒
})

// 请求拦截器，添加认证token
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器，处理401错误
api.interceptors.response.use(
  response => {
    return response
  },
  error => {
    if (error.response && error.response.status === 401) {
      // 清除token并跳转到登录页
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 语料包相关API
export const scriptPackAPI = {
  // 获取语料包列表
  getPackList(taskId) {
    return api.get('/script-pack/list', {
      params: { task_id: taskId }
    })
  },
  
  // 获取指定语料包
  getPack(packId, taskId) {
    return api.get(`/script-pack/${packId}`, {
      params: { task_id: taskId }
    })
  },
  
  // 获取单个句子
  getSentence(packId, sentenceId, taskId) {
    return api.get(`/script-pack/${packId}/sentence/${sentenceId}`, {
      params: { task_id: taskId }
    })
  }
}

// 录音上传API
export const collectAPI = {
  // 上传录音
  uploadRecording(formData) {
    return api.post('/collect/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  
  // 获取说话人录音记录
  getRecordings(speakerId) {
    return api.get(`/recordings/${speakerId}`)
  },
  
  // 获取进度
  getProgress(speakerId, packId, taskId) {
    return api.get(`/recordings/${speakerId}/progress/${packId}`, {
      params: { task_id: taskId }
    })
  },
  
  // 切换评估集状态
  toggleEvaluationSet(speakerId, sentenceId, taskId) {
    return api.post('/recordings/evaluation-set', {
      speaker_id: speakerId,
      sentence_id: sentenceId,
      task_id: taskId
    })
  }
}

export default api



