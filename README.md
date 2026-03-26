# 方言输入法 - 31fangyan

基于 Whisper 模型的方言语音输入法系统，支持方言录音采集、模型微调和语音转文字功能。

## 📁 项目结构

```
31fangyan/
├── backend/                    # 后端服务
│   ├── main.py               # FastAPI 主入口
│   ├── api_audio.py          # 语音转文字 API
│   ├── api_database.py       # 数据库 API
│   ├── database.py           # 数据库模型
│   ├── init_empty_db.py      # 初始化空白数据库脚本
│   ├── voice_collector.db   # SQLite 数据库（空）
│   └── recordings/           # 录音文件目录（不上传）
├── frontend/                  # Vue.js 前端
│   ├── src/
│   │   ├── views/           # 页面组件
│   │   │   ├── LoginPage.vue
│   │   │   ├── CollectPage.vue
│   │   │   ├── EvaluatePage.vue
│   │   │   ├── FineTunePage.vue
│   │   │   ├── FineTuneHistoryPage.vue
│   │   │   ├── TestPage.vue
│   │   │   ├── TranscribePage.vue
│   │   │   └── UserManagementPage.vue
│   │   └── main.js
│   └── package.json
├── shurufa/                   # Android 输入法应用
│   ├── app/
│   │   └── src/main/
│   │       ├── java/com/example/shurufa/
│   │       │   ├── MainActivity.kt
│   │       │   ├── VoiceInputMethodService.kt
│   │       │   ├── HttpWhisperClient.kt
│   │       │   ├── audio/
│   │       │   │   ├── AudioRecorder.kt
│   │       │   │   ├── WavAudioRecorder.kt
│   │       │   │   ├── FeatureExtractor.kt
│   │       │   │   └── VADProcessor.kt
│   │       │   └── input/
│   │       │       └── PinyinConverter.kt
│   │       └── res/
│   │           └── layout/
│   │               ├── keyboard_view.xml      # 键盘布局
│   │               └── voice_input_view.xml   # 语音输入界面
│   └── build.gradle.kts
├── models/                    # AI 模型目录
│   ├── whisper-small/        # Whisper Small 模型
│   │   ├── config.json
│   │   ├── model.safetensors
│   │   ├── tokenizer.json
│   │   └── ...
│   └── 正式常德话smalllora/   # 微调后的方言模型
│       ├── config.json
│       ├── model.safetensors
│       └── ...
├── BACKUP/                    # 本地备份（不上传）
│   ├── voice_collector.db.bak
│   └── recordings/
├── .gitignore
└── README.md

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Android Studio（用于构建输入法 APK）

### 1. 克隆项目

```bash
git clone git@github.com:sunxiaoqiqi/fangyan.git
cd fangyan
```

### 2. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 3. 安装前端依赖

```bash
cd frontend
npm install
```

### 4. 下载模型文件

项目使用 Hugging Face 上的 Whisper 模型：

**方式一：使用 Git LFS**
```bash
cd models
git lfs install
git lfs pull
```

**方式二：手动下载**
1. 访问 https://huggingface.co/openai/whisper-small
2. 下载所有文件到 `models/whisper-small/`

### 5. 初始化数据库

```bash
cd backend
python init_empty_db.py
```

### 6. 启动后端服务

```bash
cd backend
python main.py
```

后端服务地址：http://localhost:3000

### 7. 启动前端

```bash
cd frontend
npm run dev
```

前端地址：http://localhost:5173

## 🎯 核心功能

### 1. 方言录音采集

- 用户注册与登录
- 录音任务分配
- 录音质量评估
- 批量音频采集

### 2. 模型微调

- 基于 Whisper Small 微调
- 自定义训练参数
- 训练历史记录
- 模型导出与部署

### 3. 语音转文字

- 实时语音识别
- 支持方言识别
- 音频格式转换
- 批量转录

### 4. Android 输入法

- 语音输入模式
- 方言识别
- 拼音转换
- 实时转录

## 📡 API 接口

### 认证接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/auth/login` | 用户登录 |
| POST | `/api/auth/register` | 用户注册 |
| GET | `/api/auth/current-user` | 获取当前用户 |

### 录音接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/sentences` | 获取句子列表 |
| POST | `/api/recordings` | 上传录音 |
| GET | `/api/recordings` | 获取录音列表 |
| POST | `/api/recordings/evaluate` | 评估录音质量 |

### 训练接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/fine-tune` | 开始微调训练 |
| GET | `/api/fine-tune/history` | 获取训练历史 |
| GET | `/api/fine-tune/status/{job_id}` | 查询训练状态 |

### 语音识别接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/audio/transcribe` | 转录音频文件 |
| GET | `/api/audio/languages` | 获取支持的语言 |

## 🛠️ 技术栈

### 后端

- **FastAPI** - Web 框架
- **SQLAlchemy** - ORM
- **SQLite** - 数据库
- **Transformers** - Hugging Face 工具库
- **faster-whisper** - Whisper 模型推理

### 前端

- **Vue 3** - 前端框架
- **Vite** - 构建工具
- **Vue Router** - 路由管理
- **Axios** - HTTP 客户端

### 移动端

- **Kotlin** - Android 开发语言
- **Jetpack Compose** - UI 框架
- **OkHttp** - 网络请求
- **Silero VAD** - 语音活动检测

## ⚙️ 配置说明

### 后端配置

数据库和其他配置在 `backend/database.py` 中：

```python
DATABASE_URL = "sqlite:///voice_collector.db"
RECORDINGS_DIR = "recordings"
```

### 模型配置

模型路径配置在 `backend/api_audio.py` 中：

```python
LOCAL_MODEL_PATH = BASE_DIR.parent / "models" / "whisper-small"
REMOTE_MODEL_NAME = "openai/whisper-small"
```

### 前端配置

API 地址在 `frontend/src/main.js` 中配置。

## 🔧 开发指南

### 添加新的 API 接口

1. 在 `backend/` 目录下创建或修改 API 文件
2. 使用 `@app.post()` 或 `@app.get()` 装饰器定义路由
3. 返回 JSON 响应

### 修改输入法键盘布局

编辑 `shurufa/app/src/main/res/layout/keyboard_view.xml`

### 添加新的训练参数

修改 `backend/api_fine_tune.py` 中的训练配置

## 📝 注意事项

- **数据库**：`.gitignore` 中配置了 `*.db` 不上传，clone 后需要运行 `init_empty_db.py`
- **录音文件**：`backend/recordings/` 目录不上传，包含原始音频文件
- **备份文件**：`BACKUP/` 目录不上传，包含本地数据备份
- **模型文件**：需要手动下载或使用 Git LFS

## 🔍 故障排除

### 1. 模型加载失败

如果遇到 SSL 错误或网络问题：
1. 检查网络连接
2. 使用代理或 VPN
3. 手动下载模型文件到 `models/whisper-small/`

### 2. 数据库错误

```bash
cd backend
python init_empty_db.py
```

### 3. 前端无法连接后端

检查后端服务是否在 3000 端口运行。

## 📄 许可证

本项目仅供学习和研究使用。

## 👥 贡献者

项目开发者：sunxiaoqiqi

## 📞 联系方式

- GitHub: https://github.com/sunxiaoqiqi/fangyan
