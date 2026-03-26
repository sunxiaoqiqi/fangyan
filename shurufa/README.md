# 常德话语音输入法 - 安卓项目说明

## 项目概述

本项目是一个基于安卓平台的语音输入法应用，专门用于常德话的语音转文字功能。项目集成了Whisper模型的微调版本，实现了离线语音识别功能。

## 项目结构

```
shurufa/
├── app/
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/com/example/shurufa/
│   │   │   │   ├── audio/
│   │   │   │   │   ├── AudioRecorder.kt          # 音频录制功能
│   │   │   │   │   └── FeatureExtractor.kt       # 特征提取功能
│   │   │   │   ├── inference/
│   │   │   │   │   └── WhisperModel.kt           # ONNX模型推理
│   │   │   │   ├── service/
│   │   │   │   │   └── VoiceInputMethodService.kt # 输入法服务
│   │   │   │   └── MainActivity.kt
│   │   │   ├── res/
│   │   │   │   ├── layout/
│   │   │   │   │   └── voice_input_view.xml      # 输入法UI布局
│   │   │   │   ├── drawable/
│   │   │   │   │   └── ic_mic.xml               # 麦克风图标
│   │   │   │   ├── values/
│   │   │   │   │   └── strings.xml              # 字符串资源
│   │   │   │   └── xml/
│   │   │   │       └── method.xml               # 输入法配置
│   │   │   └── AndroidManifest.xml
│   │   └── build.gradle.kts
│   └── build.gradle.kts
├── convert_model.py                               # 模型转换脚本
└── README.md
```

## 已完成功能

### 1. 音频录制功能 (AudioRecorder.kt)
- 支持麦克风权限检查
- 实时音频录制
- 自动生成临时音频文件
- 录音状态管理

### 2. 特征提取功能 (FeatureExtractor.kt)
- 音频文件加载和处理
- 梅尔频谱特征提取
- FFT计算和频谱分析
- Mel滤波器组应用

### 3. ONNX模型推理 (WhisperModel.kt)
- ONNX Runtime集成
- 模型加载和初始化
- 特征预处理和推理
- 结果解码和文本生成

### 4. 输入法服务 (VoiceInputMethodService.kt)
- 完整的输入法服务实现
- 语音输入UI管理
- 异步音频处理
- 文本插入功能

### 5. UI界面
- 简洁的语音输入界面
- 实时状态显示
- 麦克风图标和按钮
- 转录结果显示

## 技术栈

### 核心依赖
- **ONNX Runtime**: 1.16.3 - 模型推理引擎
- **Media3**: 1.2.0 - 音频处理
- **Kotlin Coroutines**: 1.7.3 - 异步处理
- **Compose**: 现代UI框架

### 开发环境
- **Android SDK**: 24-36
- **Kotlin**: 1.9+
- **Gradle**: 8.0+

## 配置说明

### 1. 权限配置
应用需要以下权限：
- `RECORD_AUDIO` - 录音权限
- `WRITE_EXTERNAL_STORAGE` - 写入存储
- `READ_EXTERNAL_STORAGE` - 读取存储
- `INTERNET` - 网络访问（可选）

### 2. 模型配置
- 模型文件位置：`app/src/main/assets/model_quantized.onnx`
- 模型格式：ONNX INT8量化
- 预期模型大小：~150MB

## 使用说明

### 1. 模型准备
由于Whisper模型的ONNX导出比较复杂，建议使用以下方法之一：

#### 方法1：使用预转换的模型
```bash
# 将预转换的ONNX模型放入assets目录
cp model_quantized.onnx app/src/main/assets/
```

#### 方法2：使用whisper.cpp
```bash
# 使用whisper.cpp的转换工具
cd whisper.cpp
./convert-h5-to-ggml.py model_path
```

#### 方法3：在线API（备用方案）
如果本地模型转换遇到问题，可以暂时使用在线API：
- OpenAI Whisper API
- 百度语音识别API
- 腾讯语音识别API

### 2. 项目构建
```bash
# 构建Debug版本
./gradlew assembleDebug

# 构建Release版本
./gradlew assembleRelease

# 安装到设备
./gradlew installDebug
```

### 3. 输入法启用
1. 安装应用后，进入系统设置
2. 选择"语言和输入法"
3. 启用"语音输入法"
4. 在输入框中选择"语音输入法"作为默认输入法

### 4. 使用语音输入
1. 点击麦克风按钮开始录音
2. 说出常德话内容
3. 等待转录结果显示
4. 文本自动插入到输入框

## 功能特点

### 优势
- **离线运行**: 无需网络连接
- **实时转录**: 快速语音识别
- **常德话优化**: 专门针对常德话训练
- **低延迟**: 本地推理，响应迅速
- **隐私保护**: 数据不上传云端

### 性能优化
- INT8量化减少模型大小
- 异步处理避免UI阻塞
- 音频缓存机制
- 内存管理优化

## 已知问题和解决方案

### 1. 模型转换问题
**问题**: Whisper模型的ONNX导出复杂，需要decoder输入
**解决方案**: 
- 使用whisper.cpp的转换工具
- 或者使用在线API作为备用方案

### 2. 模型文件大小
**问题**: 原始模型文件较大
**解决方案**:
- 使用INT8量化
- 考虑使用更小的模型变体（tiny/base）

### 3. 性能问题
**问题**: 在低端设备上可能性能不足
**解决方案**:
- 降低音频采样率
- 减少特征维度
- 使用更小的模型

## 后续开发建议

### 1. 模型优化
- 尝试不同的量化方法
- 优化模型结构
- 剪枝和蒸馏

### 2. 功能增强
- 添加标点符号预测
- 支持多语言混合
- 实时转录显示
- 语音命令识别

### 3. 用户体验
- 添加声音反馈
- 优化界面设计
- 支持主题切换
- 添加使用教程

### 4. 性能优化
- 使用NNAPI加速
- 优化内存使用
- 减少启动时间
- 批量处理优化

## 测试建议

### 1. 功能测试
- 录音功能测试
- 特征提取测试
- 模型推理测试
- 文本插入测试

### 2. 性能测试
- 不同设备上的运行速度
- 内存使用情况
- 电池消耗测试
- 转录准确率测试

### 3. 兼容性测试
- 不同Android版本
- 不同屏幕尺寸
- 不同设备厂商
- 不同输入场景

## 贡献指南

欢迎贡献代码、报告问题或提出建议。

## 许可证

本项目基于MIT许可证开源。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 项目Issues
- 邮件联系

## 致谢

感谢以下开源项目：
- OpenAI Whisper
- ONNX Runtime
- Android Jetpack
- Kotlin Coroutines

---

**注意**: 本项目目前处于开发阶段，部分功能可能需要进一步优化和完善。建议在实际使用前进行充分测试。