# Android语音输入法 - HTTP API方案

## 🎯 方案概述

使用HTTP API调用faster-whisper进行语音识别：
- **服务器端**: Python + Flask + faster-whisper
- **客户端**: Android应用通过HTTP调用

## ✅ 优势

1. **无需编译Native库** - 不需要编译whisper.cpp或ctranslate2
2. **性能强大** - 利用PC的强大算力
3. **模型随时更新** - 服务器端可以轻松更换模型
4. **开发简单** - 纯HTTP通信，Android原生支持

## 📁 文件说明

### backend/whisper_server.py
Python HTTP服务器，使用faster-whisper进行语音识别。

### app/.../HttpWhisperClient.kt
Android HTTP客户端，调用服务器API进行语音识别。

## 🚀 使用步骤

### 1. 启动服务器

在PC上运行：

```bash
cd E:\project\31fangyan\backend
python whisper_server.py
```

确保已安装依赖：
```bash
pip install flask faster-whisper
```

### 2. 修改Android代码

编辑 `HttpWhisperClient.kt`，修改服务器地址：

```kotlin
private const val SERVER_URL = "http://10.0.0.1:5000"  // 修改为你的PC IP
```

### 3. 修改VoiceInputMethodService

将 `PyTorchWhisperModel` 替换为 `HttpWhisperClient`：

```kotlin
// 替换import
import com.example.shurufa.inference.PyTorchWhisperModel
// 改为
import com.example.shurufa.inference.HttpWhisperClient

// 修改初始化
private var whisperClient: HttpWhisperClient? = null

// 在onStartInput中
whisperClient = HttpWhisperClient(this)

// 在转录时调用
val result = whisperClient?.transcribe(audioFile)
```

## ⚙️ 配置

### 服务器配置

在 `whisper_server.py` 中修改：

```python
model_name = "base"  # tiny/base/small/medium/large
```

模型大小和性能：
- tiny: 39MB, 最快
- base: 145MB, 平衡 ⭐推荐
- small: 244MB, 最准确

### 网络配置

1. 确保PC和Android设备在同一网络
2. 关闭PC防火墙（或开放5000端口）
3. 使用PC的局域网IP（如192.168.1.x）

## 📱 使用流程

1. **启动服务器** (PC)
   ```bash
   python whisper_server.py
   ```

2. **启动Android应用**

3. **录音并转录**
   - 应用自动调用HTTP API
   - 服务器使用faster-whisper转录
   - 返回转录结果

## 🔧 故障排除

### 连接失败

1. 检查PC防火墙
2. 确认IP地址正确
3. 确保在同一网络

### 转录失败

1. 检查服务器日志
2. 确认音频格式正确（WAV）
3. 检查网络延迟

## 📊 性能

| 项目 | 性能 |
|------|------|
| 转录速度 | 0.5-2秒 |
| 模型大小 | 39-244MB |
| 网络依赖 | 需要局域网 |

## ⚠️ 注意事项

1. **网络要求** - 需要PC和Android在同一网络
2. **延迟** - 网络延迟会影响响应速度
3. **离线不可用** - 需要PC服务器运行

## 🎯 适用场景

✅ 开发测试  
✅ 有稳定网络环境  
✅ 需要高质量识别  

❌ 离线环境  
❌ 需要实时性很强的场景  

---

**状态**: 方案已准备就绪，可以开始实施！
