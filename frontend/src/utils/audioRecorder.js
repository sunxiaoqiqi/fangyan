/**
 * 音频录音管理器
 */
export class AudioRecorder {
  constructor() {
    this.mediaRecorder = null
    this.audioChunks = []
    this.stream = null
    this.audioContext = null
    this.analyser = null
    this.isRecording = false
    this.startTime = null
  }

  /**
   * 开始录音
   */
  async startRecording() {
    try {
      // 获取麦克风权限
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,  // Whisper推荐16kHz
          channelCount: 1,    // 单声道
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      })

      // 创建AudioContext用于实时音量检测
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)()
      this.analyser = this.audioContext.createAnalyser()
      this.analyser.fftSize = 256
      const microphone = this.audioContext.createMediaStreamSource(this.stream)
      microphone.connect(this.analyser)

      // 创建MediaRecorder
      const options = {
        mimeType: 'audio/webm;codecs=opus'
      }
      
      // 检查浏览器支持
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options.mimeType = 'audio/webm'
      }

      this.mediaRecorder = new MediaRecorder(this.stream, options)
      this.audioChunks = []
      
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data)
        }
      }

      this.mediaRecorder.start()
      this.isRecording = true
      this.startTime = Date.now()
      
      return true
    } catch (error) {
      console.error('录音启动失败:', error)
      throw new Error('无法访问麦克风，请检查权限设置')
    }
  }

  /**
   * 停止录音
   */
  async stopRecording() {
    return new Promise((resolve, reject) => {
      if (!this.mediaRecorder || !this.isRecording) {
        reject(new Error('未在录音状态'))
        return
      }

      this.mediaRecorder.onstop = () => {
        const blob = new Blob(this.audioChunks, { type: 'audio/webm' })
        const duration = Date.now() - this.startTime
        
        // 停止所有音频轨道
        if (this.stream) {
          this.stream.getTracks().forEach(track => track.stop())
        }
        
        this.isRecording = false
        this.audioChunks = []
        
        resolve({
          blob,
          duration,
          mimeType: this.mediaRecorder.mimeType
        })
      }

      this.mediaRecorder.onerror = (error) => {
        reject(error)
      }

      this.mediaRecorder.stop()
    })
  }

  /**
   * 获取实时音量（0-1）
   */
  getVolumeLevel() {
    if (!this.analyser) return 0

    const dataArray = new Uint8Array(this.analyser.frequencyBinCount)
    this.analyser.getByteFrequencyData(dataArray)
    
    const average = dataArray.reduce((a, b) => a + b) / dataArray.length
    return average / 255  // 归一化到 0-1
  }

  /**
   * 检查录音质量
   */
  async checkQuality(blob, duration) {
    const quality = {
      duration: duration / 1000,  // 转换为秒
      isValid: true,
      warnings: []
    }

    // 时长检查
    if (quality.duration < 0.3) {
      quality.isValid = false
      quality.warnings.push('录音时长过短（至少0.3秒）')
    } else if (quality.duration > 30) {
      quality.warnings.push('录音时长较长（建议不超过30秒）')
    }

    // 文件大小检查
    if (blob.size < 1000) {
      quality.isValid = false
      quality.warnings.push('录音文件过小，可能无效')
    }

    return quality
  }

  /**
   * 取消录音
   */
  cancelRecording() {
    if (this.mediaRecorder && this.isRecording) {
      this.mediaRecorder.stop()
    }
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop())
    }
    this.isRecording = false
    this.audioChunks = []
  }
}



