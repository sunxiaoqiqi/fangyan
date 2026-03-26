"""
音频文件服务API
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pathlib import Path
from database import Recording, get_db
from sqlalchemy.orm import Session
from fastapi import Depends
import os
import uuid
import soundfile as sf
from transformers import WhisperProcessor, WhisperForConditionalGeneration

router = APIRouter(prefix="/audio", tags=["音频"])

BASE_DIR = Path(__file__).parent
RECORDINGS_DIR = BASE_DIR / "recordings"

# 本地模型路径配置（优先使用本地模型）
LOCAL_MODEL_PATH = BASE_DIR.parent / "models" / "whisper-small"
REMOTE_MODEL_NAME = "openai/whisper-small"

# 模型缓存
model_cache = {}
processor_cache = None
models_initialized = False

# 初始化默认模型和处理器
def init_models():
    global processor_cache, models_initialized
    if models_initialized:
        return
    
    try:
        # 优先尝试从本地加载模型
        if LOCAL_MODEL_PATH.exists():
            print(f"[INIT] 从本地加载Whisper模型: {LOCAL_MODEL_PATH}")
            if processor_cache is None:
                print("[INIT] 加载本地Whisper处理器...")
                processor_cache = WhisperProcessor.from_pretrained(str(LOCAL_MODEL_PATH))
                print("[INIT] 本地Whisper处理器加载成功")
            
            if "default" not in model_cache:
                print("[INIT] 加载本地Whisper模型...")
                model_cache["default"] = WhisperForConditionalGeneration.from_pretrained(str(LOCAL_MODEL_PATH))
                print("[INIT] 本地Whisper模型加载成功")
        else:
            # 本地模型不存在，尝试从远程下载
            print(f"[INIT] 本地模型不存在: {LOCAL_MODEL_PATH}")
            print(f"[INIT] 尝试从Hugging Face下载模型...")
            
            if processor_cache is None:
                print("[INIT] 加载Whisper处理器...")
                processor_cache = WhisperProcessor.from_pretrained(REMOTE_MODEL_NAME)
                print("[INIT] Whisper处理器加载成功")
            
            if "default" not in model_cache:
                print("[INIT] 加载默认Whisper模型...")
                model_cache["default"] = WhisperForConditionalGeneration.from_pretrained(REMOTE_MODEL_NAME)
                print("[INIT] 默认Whisper模型加载成功")
        
        models_initialized = True
    except Exception as e:
        print(f"[INIT] 模型加载失败: {str(e)}")
        print("[INIT] 提示：请手动下载模型到以下目录:")
        print(f"[INIT]   {LOCAL_MODEL_PATH}")
        print("[INIT] 或访问: https://huggingface.co/openai/whisper-small")
        models_initialized = True


@router.get("/models")
async def get_models():
    """获取可用的模型列表"""
    try:
        model_dir = BASE_DIR.parent / "models"
        models = []
        
        print(f"[DEBUG] 模型目录: {model_dir}")
        print(f"[DEBUG] 模型目录是否存在: {model_dir.exists()}")
        
        # 检查models目录是否存在
        if model_dir.exists():
            # 遍历models目录下的子目录（每个目录代表一个模型）
            for item in model_dir.iterdir():
                print(f"[DEBUG] 检查项目: {item}, 是否为目录: {item.is_dir()}")
                if item.is_dir():
                    # 跳过checkpoint目录，只显示最终模型
                    if item.name.startswith('checkpoint-'):
                        print(f"[DEBUG]   跳过checkpoint目录: {item.name}")
                        continue
                    
                    # 检查目录中是否包含模型文件
                    has_model = False
                    for file in item.iterdir():
                        print(f"[DEBUG]   检查文件: {file.name}, 后缀: {file.suffix}")
                        if file.is_file() and (file.suffix == ".safetensors" or file.suffix == ".pt"):
                            has_model = True
                            break
                    
                    if has_model:
                        models.append({
                            "name": f"自定义模型: {item.name}",
                            "path": str(item)
                        })
                        print(f"[DEBUG]   添加模型: {item.name}")
        
        print(f"[DEBUG] 找到 {len(models)} 个模型")
        return {"models": models}
    except Exception as e:
        print(f"[ERROR] 获取模型列表失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")


@router.get("/{file_path:path}")
async def get_audio_file(file_path: str, db: Session = Depends(get_db)):
    """获取音频文件（用于播放）"""
    try:
        # URL解码
        import urllib.parse
        decoded_path = urllib.parse.unquote(file_path)
        
        # 构建完整路径
        audio_path = RECORDINGS_DIR / decoded_path
        
        # 安全检查：确保文件在recordings目录内
        try:
            audio_path.resolve().relative_to(RECORDINGS_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="非法路径")
        
        if not audio_path.exists():
            raise HTTPException(status_code=404, detail="音频文件不存在")
        
        # 确定媒体类型
        media_type = "audio/webm"
        if audio_path.suffix == ".wav":
            media_type = "audio/wav"
        elif audio_path.suffix == ".mp3":
            media_type = "audio/mpeg"
        
        return FileResponse(
            str(audio_path),
            media_type=media_type,
            filename=audio_path.name
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取音频文件失败: {str(e)}")


@router.post("/transcribe")
async def transcribe_audio(
    audio_file: UploadFile = File(...),
    model_path: str = Form("default"),
    language: str = Form("zh")
):
    """使用Whisper模型转录音频"""
    try:
        # 保存上传的音频
        # 根据音频类型设置正确的扩展名
        if audio_file.content_type == 'audio/webm':
            temp_path = BASE_DIR / f"temp_{uuid.uuid4()}.webm"
        else:
            temp_path = BASE_DIR / f"temp_{uuid.uuid4()}.wav"
        
        # 读取音频文件
        audio_data = await audio_file.read()
        
        # 保存为临时文件
        with open(temp_path, "wb") as f:
            f.write(audio_data)
        
        print(f"[DEBUG] 音频文件保存成功: {temp_path}")
        print(f"[DEBUG] 音频文件大小: {len(audio_data)} bytes")
        print(f"[DEBUG] 音频文件类型: {audio_file.content_type}")
        
        # 初始化模型（如果还没初始化）
        init_models()
        
        # 检查模型是否可用
        if model_path == "default" and "default" not in model_cache:
            raise HTTPException(
                status_code=503, 
                detail="默认模型未加载。请确保网络连接正常，或使用本地模型。"
            )
        
        # 使用缓存的处理器
        print("[DEBUG] 使用缓存的Whisper处理器...")
        processor = processor_cache
        
        # 使用缓存的模型
        print("[DEBUG] 使用缓存的Whisper模型...")
        if model_path == "default":
            if "default" not in model_cache:
                raise HTTPException(
                    status_code=503,
                    detail="默认Whisper模型未加载。请检查网络连接。"
                )
            model = model_cache["default"]
        else:
            # 安全检查：确保模型路径在models目录内
            model_dir = BASE_DIR.parent / "models"
            model_full_path = Path(model_path)
            try:
                model_full_path.resolve().relative_to(model_dir.resolve())
            except ValueError:
                raise HTTPException(status_code=403, detail="非法模型路径")
            
            if not model_full_path.exists():
                raise HTTPException(status_code=404, detail="模型文件不存在")
            
            # 检查模型是否在缓存中
            cache_key = str(model_full_path)
            if cache_key not in model_cache:
                print(f"[DEBUG] 加载自定义模型: {model_full_path}")
                # 从模型目录加载模型
                model_cache[cache_key] = WhisperForConditionalGeneration.from_pretrained(str(model_full_path))
                print("[DEBUG] 自定义模型加载成功")
            else:
                print(f"[DEBUG] 使用缓存的自定义模型: {model_full_path}")
            
            model = model_cache[cache_key]
        print("[DEBUG] Whisper模型加载成功")
        
        # 预处理音频
        print("[DEBUG] 开始预处理音频...")
        try:
            # 尝试直接读取音频
            audio, sample_rate = sf.read(str(temp_path))
            print(f"[DEBUG] 音频读取成功: 采样率={sample_rate}, 长度={len(audio)}")
        except Exception as e:
            print(f"[ERROR] 直接读取音频失败: {str(e)}")
            # 如果直接读取失败，尝试使用ffmpeg转换
            print("[DEBUG] 尝试使用ffmpeg转换音频...")
            import subprocess
            import os
            
            # 创建转换后的临时文件
            converted_path = BASE_DIR / f"temp_{uuid.uuid4()}.wav"
            
            # 使用ffmpeg转换音频
            try:
                subprocess.run([
                    'ffmpeg', '-i', str(temp_path),
                    '-ar', '16000', '-ac', '1', '-f', 'wav',
                    str(converted_path)
                ], check=True, capture_output=True)
                
                # 读取转换后的音频
                audio, sample_rate = sf.read(str(converted_path))
                print(f"[DEBUG] 音频转换并读取成功: 采样率={sample_rate}, 长度={len(audio)}")
                
                # 清理转换后的文件
                if converted_path.exists():
                    os.remove(converted_path)
            except Exception as e:
                print(f"[ERROR] 音频转换失败: {str(e)}")
                # 清理临时文件
                if temp_path.exists():
                    os.remove(temp_path)
                raise HTTPException(status_code=500, detail=f"音频处理失败: {str(e)}")
        
        input_features = processor(audio, sampling_rate=sample_rate, return_tensors="pt").input_features
        print(f"[DEBUG] 音频预处理成功: 输入特征形状={input_features.shape}")
        
        # 生成转录
        print("[DEBUG] 开始生成转录...")
        predicted_ids = model.generate(input_features, language=language)
        transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
        print(f"[DEBUG] 转录成功: {transcription}")
        
        # 清理临时文件
        os.remove(temp_path)
        print("[DEBUG] 临时文件清理成功")
        
        return {"transcription": transcription}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] 转录失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"转录失败: {str(e)}")

