"""
Whisper语音识别服务器 - 支持模型切换

功能：
1. 接收音频片段并转录
2. 支持模型热切换
3. 支持多种模型格式 (faster-whisper, ctranslate2)
"""

import os
import time
import tempfile
import json
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

model = None
model_loading = False
current_model_name = None
current_model_type = None

# 可用模型列表配置
AVAILABLE_MODELS = [
    {"name": "base", "path": "base", "type": "faster-whisper", "description": "Faster-Whisper base模型"},
    {"name": "small", "path": "small", "type": "faster-whisper", "description": "Faster-Whisper small模型"},
    {"name": "medium", "path": "medium", "type": "faster-whisper", "description": "Faster-Whisper medium模型"},
    {"name": "large-v2", "path": "large-v2", "type": "faster-whisper", "description": "Faster-Whisper large-v2模型"},
]

# 自定义模型目录
CUSTOM_MODELS_DIR = Path(__file__).parent.parent / "models"

def to_simplified(text):
    """繁体转简体"""
    try:
        import opencc
        converter = opencc.OpenCC('t2s')
        return converter.convert(text)
    except ImportError:
        try:
            import zhconv
            return zhconv.convert(text, 'zh-hans')
        except ImportError:
            return text

def load_model(model_path, model_type="faster-whisper"):
    """
    加载模型
    
    Args:
        model_path: 模型路径或名称
        model_type: 模型类型 (faster-whisper, ctranslate2, huggingface)
    """
    global model, model_loading, current_model_name, current_model_type
    
    if model is not None:
        print(f"正在卸载旧模型: {current_model_name}...")
        del model
        model = None
    
    model_loading = True
    current_model_name = model_path
    current_model_type = model_type
    
    try:
        print(f"正在加载模型: {model_path} (类型: {model_type})...")
        start_time = time.time()
        
        if model_type in ["ctranslate2", "faster-whisper"]:
            from faster_whisper import WhisperModel
            model = WhisperModel(
                model_path,
                device="cpu",
                compute_type="int8"
            )
        elif model_type == "huggingface":
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
            import torch
            
            print("使用 transformers 加载模型...")
            
            model_obj = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_path,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True
            )
            processor = AutoProcessor.from_pretrained(model_path)
            
            model = {
                'type': 'transformers',
                'model': model_obj,
                'processor': processor
            }
        else:
            from faster_whisper import WhisperModel
            model = WhisperModel(
                model_path,
                device="cpu",
                compute_type="int8"
            )
        
        elapsed = time.time() - start_time
        print(f"✓ 模型加载完成，耗时: {elapsed:.2f}秒")
        
    except Exception as e:
        print(f"✗ 模型加载失败: {e}")
        import traceback
        traceback.print_exc()
        model_loading = False
        current_model_name = None
        current_model_type = None
        raise e
    
    model_loading = False

def scan_custom_models():
    """扫描自定义模型目录"""
    custom_models = []
    
    print(f"\n{'='*50}")
    print(f"扫描自定义模型目录: {CUSTOM_MODELS_DIR}")
    print(f"{'='*50}")
    
    if not CUSTOM_MODELS_DIR.exists():
        print(f"自定义模型目录不存在!")
        return custom_models
    
    for model_dir in CUSTOM_MODELS_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        
        model_bin = model_dir / "model.bin"
        safetensors = model_dir / "model.safetensors"
        pytorch_bin = model_dir / "pytorch_model.bin"
        config_json = model_dir / "config.json"
        
        print(f"\n检查目录: {model_dir.name}")
        print(f"  - config.json exists: {config_json.exists()}")
        print(f"  - model.bin exists: {model_bin.exists()}")
        print(f"  - model.safetensors exists: {safetensors.exists()}")
        print(f"  - pytorch_model.bin exists: {pytorch_bin.exists()}")
        
        if not config_json.exists():
            print(f"  -> 跳过 (无config.json)")
            continue
        
        if model_bin.exists():
            custom_models.append({
                "name": model_dir.name,
                "path": str(model_dir.absolute()),
                "type": "ctranslate2",
                "description": f"CTranslate2模型: {model_dir.name}"
            })
            print(f"  -> 添加为CTranslate2模型")
        elif safetensors.exists() or pytorch_bin.exists():
            custom_models.append({
                "name": model_dir.name,
                "path": str(model_dir.absolute()),
                "type": "huggingface",
                "description": f"HuggingFace格式模型: {model_dir.name}"
            })
            print(f"  -> 添加为HuggingFace模型")
        else:
            print(f"  -> 跳过 (无模型文件)")
    
    print(f"\n找到 {len(custom_models)} 个自定义模型")
    print(f"{'='*50}\n")
    
    return custom_models

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    global model, model_loading, current_model_name
    
    return jsonify({
        'status': 'ok',
        'model_loaded': model is not None,
        'model_loading': model_loading,
        'current_model': current_model_name
    })

@app.route('/models', methods=['GET'])
def get_models():
    """获取可用模型列表"""
    global current_model_name, current_model_type
    
    all_models = AVAILABLE_MODELS.copy()
    all_models.extend(scan_custom_models())
    
    return jsonify({
        'success': True,
        'current_model': current_model_name,
        'current_model_type': current_model_type,
        'models': all_models
    })

@app.route('/model/switch', methods=['POST'])
def switch_model():
    """切换模型"""
    global model, model_loading, current_model_name
    
    if model_loading:
        return jsonify({
            'success': False,
            'message': '模型正在加载中，请稍后'
        }), 400
    
    data = request.get_json()
    model_name = data.get('model_name')
    model_type = data.get('model_type', 'faster-whisper')
    
    if not model_name:
        return jsonify({
            'success': False,
            'message': '请指定模型名称'
        }), 400
    
    if model_name == current_model_name:
        return jsonify({
            'success': True,
            'message': f'当前已是模型: {model_name}',
            'current_model': current_model_name
        })
    
    try:
        print(f"\n{'='*50}")
        print(f"切换模型: {current_model_name} -> {model_name}")
        print(f"模型类型: {model_type}")
        print(f"{'='*50}")
        
        load_model(model_name, model_type)
        
        return jsonify({
            'success': True,
            'message': f'模型已切换为: {model_name}',
            'current_model': model_name,
            'current_model_type': model_type
        })
        
    except Exception as e:
        import traceback
        print(f"✗ 模型切换失败:")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'模型切换失败: {str(e)}'
        }), 500

@app.route('/model/reload', methods=['POST'])
def reload_model():
    """重载当前模型"""
    global current_model_name, current_model_type
    
    if not current_model_name:
        return jsonify({
            'success': False,
            'message': '没有已加载的模型'
        }), 400
    
    try:
        print(f"\n{'='*50}")
        print(f"重载模型: {current_model_name}")
        print(f"{'='*50}")
        
        load_model(current_model_name, current_model_type)
        
        return jsonify({
            'success': True,
            'message': f'模型已重载: {current_model_name}',
            'current_model': current_model_name
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'模型重载失败: {str(e)}'
        }), 500

@app.route('/transcribe', methods=['POST'])
def transcribe():
    """转录音频片段"""
    global model, current_model_name, current_model_type
    
    if model is None:
        return jsonify({'error': '模型未加载', 'text': ''}), 500
    
    if model_loading:
        return jsonify({'error': '模型正在加载中', 'text': ''}), 500
    
    try:
        if 'audio' not in request.files:
            return jsonify({'error': '没有找到音频文件', 'text': ''}), 400
        
        audio_file = request.files['audio']
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
            temp_path = f.name
            audio_file.save(temp_path)
        
        print(f"\n收到音频片段: {temp_path}")
        print(f"文件大小: {os.path.getsize(temp_path)} 字节")
        print(f"使用模型: {current_model_name}")
        
        start_time = time.time()
        
        if isinstance(model, dict) and model.get('type') == 'transformers':
            full_text = transcribe_with_transformers(temp_path, model)
            language = 'zh'
        else:
            segments, info = model.transcribe(
                temp_path,
                language='zh',
                beam_size=5,
                vad_filter=True
            )
            full_text = ''.join([s.text for s in segments])
            language = info.language
        
        try:
            os.remove(temp_path)
        except:
            pass
        
        elapsed = time.time() - start_time
        
        full_text = to_simplified(full_text)
        
        print(f"转录完成，耗时: {elapsed:.2f}秒")
        print(f"结果: {full_text}")
        
        return jsonify({
            'text': full_text,
            'language': language,
            'duration': elapsed
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'text': ''}), 500

def transcribe_with_transformers(audio_path, model_obj):
    """使用 transformers 进行语音识别"""
    import librosa
    import torch
    
    whisper_model = model_obj['model']
    processor = model_obj['processor']
    
    audio_array, sampling_rate = librosa.load(audio_path, sr=16000)
    
    input_features = processor(
        audio_array,
        sampling_rate=sampling_rate,
        return_tensors="pt"
    ).input_features
    
    forced_decoder_ids = processor.get_decoder_prompt_ids(
        language="zh",
        task="transcribe"
    )
    
    generate_kwargs = {
        "max_new_tokens": 300
    }
    
    if forced_decoder_ids is not None:
        generate_kwargs["forced_decoder_ids"] = forced_decoder_ids
    
    with torch.no_grad():
        predicted_ids = whisper_model.generate(
            input_features,
            **generate_kwargs
        )
    
    transcription = processor.batch_decode(
        predicted_ids,
        skip_special_tokens=True
    )[0]
    
    return transcription

if __name__ == '__main__':
    print("=" * 60)
    print("Whisper语音识别服务器 (支持模型切换)")
    print("=" * 60)
    print("接口说明:")
    print("  GET  /health         - 健康检查")
    print("  GET  /models         - 获取可用模型列表")
    print("  POST /model/switch   - 切换模型")
    print("  POST /model/reload   - 重载当前模型")
    print("  POST /transcribe     - 转录音频片段")
    print("=" * 60)
    
    print("\n扫描自定义模型...")
    custom_models = scan_custom_models()
    if custom_models:
        print("找到自定义模型:")
        for m in custom_models:
            print(f"  - {m['name']}: {m['path']}")
    else:
        print("未找到自定义模型")
    
    print("\n加载默认模型 (base)...")
    load_model("base", "faster-whisper")
    
    print("\n服务器启动完成！")
    app.run(host='0.0.0.0', port=5000, debug=False)
