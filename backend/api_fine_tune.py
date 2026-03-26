from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel
import os
import uuid
import asyncio
from datetime import datetime
import json
import csv
from pathlib import Path

from database import get_db, Recording, FineTuneHistory

router = APIRouter(prefix="/fine-tune", tags=["fine-tune"])

# CSV 文件路径
CSV_FILE = Path(__file__).parent.parent / "朗读语料包v2.csv"

def load_script_packs(task_id=None):
    """加载CSV语料包并获取语料包信息"""
    # 根据任务ID选择不同的CSV文件
    csv_file = CSV_FILE
    if task_id:
        # 尝试使用任务特定的CSV文件
        task_csv_files = []
        for file in csv_file.parent.iterdir():
            if file.name.startswith(f"{task_id}_") and file.name.endswith('.csv'):
                task_csv_files.append(file)
        
        if task_csv_files:
            csv_file = sorted(task_csv_files, key=os.path.getmtime, reverse=True)[0]
        else:
            task_csv_file = csv_file.parent / f"{task_id}.csv"
            if task_csv_file.exists():
                csv_file = task_csv_file
    
    # 读取CSV文件获取语料包信息
    pack_info = {}
    if csv_file.exists():
        encodings = ['utf-8-sig', 'gbk', 'gb2312', 'utf-8']
        for encoding in encodings:
            try:
                with open(csv_file, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    if reader.fieldnames:
                        reader.fieldnames = [field.strip().lstrip('\ufeff') for field in reader.fieldnames]
                    
                    for row in reader:
                        pack_id = row.get('pack_id', '').strip()
                        if pack_id and pack_id not in pack_info:
                            # 使用pack_id作为名称，如果CSV中有其他名称字段可以在这里修改
                            pack_info[pack_id] = pack_id
                    break
            except UnicodeDecodeError:
                continue
    
    return pack_info

# 微调任务存储
fine_tune_tasks = {}


class EvaluateRequest(BaseModel):
    """评估请求模型"""
    model_path: str
    test_data: List[Dict[str, str]]  # ["audio_path": "...", "text": "..."]
    use_evaluation_set: bool = False  # 是否使用评估集
    task_id: Optional[str] = None  # 任务ID（当使用评估集时需要）
    speaker_id: Optional[str] = None  # 说话人ID（当使用评估集时需要）

class FineTuneTask:
    def __init__(self, task_id, data_types, pack_id, params, task_name=None, recording_task_id=None, fine_tune_type="full"):
        self.task_id = task_id
        self.data_types = data_types
        self.pack_id = pack_id
        self.params = params
        self.task_name = task_name  # 微调事件名称
        self.recording_task_id = recording_task_id  # 录音记录所属的任务ID
        self.fine_tune_type = fine_tune_type  # 微调类型：full 或 lora
        self.status = "pending"
        self.progress = 0
        self.current_epoch = 0
        self.total_epochs = params.get("epochs", 10)
        self.model_path = None
        self.training_time = None
        self.error_message = None
        self.start_time = datetime.now()

@router.get("/data-preview")
async def get_data_preview(
    data_types: str,
    pack_id: Optional[str] = None,
    task_id: Optional[str] = None,  # 添加任务ID参数
    db: Session = Depends(get_db)
):
    """获取微调数据预览"""
    try:
        # 数据类型映射：前端传递的类型 -> 数据库状态
        data_type_mapping = {
            "recorded": ["pending"],  # 已录制数据对应pending状态
            "transcribed": ["transcribed"],  # 已标注数据
            "reviewed": ["reviewed"]  # 已审核数据
        }
        
        data_type_list = data_types.split(",")
        
        # 将前端的数据类型转换为数据库状态
        status_list = []
        for dt in data_type_list:
            if dt in data_type_mapping:
                status_list.extend(data_type_mapping[dt])
        
        query = db.query(Recording)
        if task_id:
            query = query.filter(Recording.task_id == task_id)  # 添加任务ID过滤
        if pack_id and pack_id.strip():  # 只有当pack_id不为空时才添加过滤
            query = query.filter(Recording.pack_id == pack_id)
        if status_list:  # 使用转换后的状态列表
            query = query.filter(Recording.status.in_(status_list))
        
        # 先获取总数
        total_count = query.count()
        
        # 获取预览数据（限制50条）
        recordings = query.limit(50).all()
        
        data = [
            {
                "sentence_id": r.sentence_id,
                "text_target": r.text_target,
                "text_transcript": r.text_transcript,
                "status": r.status,
                "task_id": r.task_id  # 添加任务ID
            }
            for r in recordings
        ]
        
        return {
            "data": data,
            "total": total_count  # 返回总数据量
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据预览失败: {str(e)}")

@router.post("/start")
async def start_fine_tuning(
    data_types: List[str] = Body(...),
    pack_id: Optional[str] = Body(None),
    params: dict = Body(None),
    task_name: Optional[str] = Body(None),  # 微调事件名称
    task_id: Optional[str] = Body(None),  # 录音记录所属的任务ID
    fine_tune_type: str = Body("full"),  # 微调类型：full 或 lora
    db: Session = Depends(get_db)
):
    """开始微调任务"""
    try:
        # 生成微调任务ID
        fine_tune_task_id = str(uuid.uuid4())
        
        print(f"[START FINE-TUNE] 接收到的 task_name: {task_name}")
        
        # 创建微调任务（传递task_name和recording_task_id）
        task = FineTuneTask(fine_tune_task_id, data_types, pack_id, params or {}, task_name, task_id, fine_tune_type)
        fine_tune_tasks[fine_tune_task_id] = task
        
        # 异步执行微调
        asyncio.create_task(perform_fine_tuning(task, db))
        
        return {
            "success": True,
            "task_id": fine_tune_task_id,
            "message": "微调任务已启动"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动微调任务失败: {str(e)}")

@router.get("/status/{task_id}")
async def get_fine_tune_status(task_id: str):
    """获取微调任务状态"""
    task = fine_tune_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return {
        "task_id": task.task_id,
        "task_name": task.task_name,  # 微调事件名称
        "fine_tune_type": task.fine_tune_type,  # 微调类型
        "status": task.status,
        "progress": task.progress,
        "current_epoch": task.current_epoch,
        "total_epochs": task.total_epochs,
        "model_path": task.model_path,
        "training_time": task.training_time,
        "error_message": task.error_message
    }

@router.get("/download/{task_id}")
async def download_model(task_id: str):
    """下载微调后的模型"""
    task = fine_tune_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    if not task.model_path or not os.path.exists(task.model_path):
        raise HTTPException(status_code=404, detail="模型文件不存在")
    
    # 这里应该返回文件流，暂时返回路径
    return {
        "success": True,
        "model_path": task.model_path
    }


@router.post("/evaluate")
async def evaluate_model(
    request: EvaluateRequest,
    db: Session = Depends(get_db)
):
    """评估模型性能"""
    try:
        from whisper_fine_tune import WhisperFineTuner
        
        # 提取基础模型名称
        import re
        model_match = re.search(r'openai/whisper-(\w+)', WhisperFineTuner.__init__.__defaults__[0])
        base_model = model_match.group(0) if model_match else "openai/whisper-small"
        
        # 创建微调器并加载模型
        tuner = WhisperFineTuner(model_name=base_model)
        tuner.load_model(request.model_path)
        
        # 计算 CER
        total_cer = 0.0
        results = []
        
        # 检查是否使用评估集
        if request.use_evaluation_set:
            if not request.task_id or not request.speaker_id:
                raise HTTPException(status_code=400, detail="使用评估集时需要提供任务ID和说话人ID")
            
            # 从数据库获取评估集数据
            evaluation_recordings = db.query(Recording).filter(
                Recording.speaker_id == request.speaker_id,
                Recording.task_id == request.task_id,
                Recording.in_evaluation_set == True,
                Recording.status != "rejected"
            ).all()
            
            if not evaluation_recordings:
                raise HTTPException(status_code=404, detail="评估集为空")
            
            # 使用评估集数据
            for recording in evaluation_recordings:
                audio_path = recording.audio_path_wav or recording.audio_path_webm
                reference_text = recording.text_target
                
                if not audio_path or not reference_text:
                    continue
                
                actual_audio_path = audio_path
                if not os.path.exists(audio_path):
                    print(f"音频文件不存在: {audio_path}")
                    results.append({
                        "audio_path": audio_path,
                        "reference": reference_text,
                        "prediction": "",
                        "cer": 1.0,
                        "error": "音频文件不存在"
                    })
                    total_cer += 1.0
                    continue
                
                try:
                    # 转录音频
                    print(f"开始转录: {actual_audio_path}")
                    result = tuner.transcribe(actual_audio_path)
                    prediction = result["text"]
                    print(f"转录结果: {prediction}")
                    
                    # 计算 CER
                    cer = calculate_cer(reference_text, prediction)
                    print(f"CER: {cer}")
                    total_cer += cer
                    
                    results.append({
                        "audio_path": audio_path,
                        "reference": reference_text,
                        "prediction": prediction,
                        "cer": cer
                    })
                except Exception as e:
                    print(f"转录失败: {e}")
                    results.append({
                        "audio_path": audio_path,
                        "reference": reference_text,
                        "prediction": "",
                        "cer": 1.0,
                        "error": str(e)
                    })
                    total_cer += 1.0
        else:
            # 使用传入的测试数据
            for item in request.test_data:
                audio_path = item.get("audio_path")
                reference_text = item.get("text")
                
                if not audio_path or not reference_text:
                    continue
                
                print(f"处理测试数据: audio_path={audio_path}, reference_text={reference_text}")
                
                # 检查audio_path是文件路径还是录音ID
                actual_audio_path = audio_path
                if not os.path.exists(audio_path):
                    # 尝试从数据库中查询录音ID对应的音频文件路径
                    try:
                        print(f"尝试从数据库查询录音ID: {audio_path}")
                        recording = db.query(Recording).filter(Recording.recording_id == audio_path).first()
                        if recording:
                            print(f"找到录音: {recording.recording_id}")
                            # 优先使用wav文件
                            if recording.audio_path_wav and os.path.exists(recording.audio_path_wav):
                                actual_audio_path = recording.audio_path_wav
                                print(f"使用wav文件: {actual_audio_path}")
                            elif recording.audio_path_webm and os.path.exists(recording.audio_path_webm):
                                actual_audio_path = recording.audio_path_webm
                                print(f"使用webm文件: {actual_audio_path}")
                        else:
                            print(f"未找到录音ID: {audio_path}")
                    except Exception as e:
                        print(f"查询录音ID失败: {e}")
                else:
                    print(f"使用直接路径: {actual_audio_path}")
                
                if not os.path.exists(actual_audio_path):
                    print(f"音频文件不存在: {actual_audio_path}")
                    results.append({
                        "audio_path": audio_path,
                        "reference": reference_text,
                        "prediction": "",
                        "cer": 1.0,
                        "error": "音频文件不存在"
                    })
                    total_cer += 1.0
                    continue
                
                try:
                    # 转录音频
                    print(f"开始转录: {actual_audio_path}")
                    result = tuner.transcribe(actual_audio_path)
                    prediction = result["text"]
                    print(f"转录结果: {prediction}")
                    
                    # 计算 CER
                    cer = calculate_cer(reference_text, prediction)
                    print(f"CER: {cer}")
                    total_cer += cer
                    
                    results.append({
                        "audio_path": audio_path,
                        "reference": reference_text,
                        "prediction": prediction,
                        "cer": cer
                    })
                except Exception as e:
                    print(f"转录失败: {e}")
                    results.append({
                        "audio_path": audio_path,
                        "reference": reference_text,
                        "prediction": "",
                        "cer": 1.0,
                        "error": str(e)
                    })
                    total_cer += 1.0
        
        # 计算平均 CER
        avg_cer = total_cer / len(results) if results else 0.0
        
        return {
            "success": True,
            "avg_cer": avg_cer,
            "results": results
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"评估模型失败: {str(e)}")


def calculate_cer(reference, hypothesis):
    """
    计算字符错误率 (Character Error Rate)
    使用动态规划计算编辑距离
    """
    import numpy as np
    
    # 计算编辑距离
    def edit_distance(s1, s2):
        m, n = len(s1), len(s2)
        dp = np.zeros((m+1, n+1), dtype=int)
        
        for i in range(m+1):
            dp[i][0] = i
        for j in range(n+1):
            dp[0][j] = j
        
        for i in range(1, m+1):
            for j in range(1, n+1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = min(
                        dp[i-1][j] + 1,    # 删除
                        dp[i][j-1] + 1,    # 插入
                        dp[i-1][j-1] + 1   # 替换
                    )
        return dp[m][n]
    
    # 计算 CER
    edit_dist = edit_distance(reference, hypothesis)
    cer = edit_dist / max(len(reference), 1)
    return cer


@router.get("/models")
async def get_models():
    """获取可用的模型列表"""
    try:
        models = []
        
        # 添加已完成的微调任务
        for task_id, task in fine_tune_tasks.items():
            if task.status == "completed" and task.model_path:
                # 使用微调事件名称或task_id作为模型名称
                display_name = task.task_name if task.task_name else f"微调任务_{task_id[:8]}"
                models.append({
                    "name": f"{display_name}",
                    "path": task.model_path,
                    "task_id": task_id,
                    "task_name": task.task_name,
                    "is_custom": True
                })
        
        # 添加models目录下的模型文件
        model_dir = os.path.join(os.path.dirname(__file__), "..", "models")
        if os.path.exists(model_dir):
            for item in os.listdir(model_dir):
                item_path = os.path.join(model_dir, item)
                if os.path.isdir(item_path):
                    # 检查目录中是否包含模型文件
                    has_model = False
                    for file in os.listdir(item_path):
                        if file.endswith(".safetensors") or file.endswith(".pt"):
                            has_model = True
                            break
                    if has_model:
                        # 使用目录名作为模型名称
                        models.append({
                            "name": f"自定义模型: {item}",
                            "path": item_path,
                            "is_custom": True
                        })
        
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")

async def perform_fine_tuning(task: FineTuneTask, db: Session):
    """执行微调任务"""
    try:
        task.status = "running"
        
        # 导入Whisper微调模块
        from whisper_fine_tune import WhisperFineTuner
        
        # 数据类型映射
        data_type_mapping = {
            "recorded": ["pending"],
            "transcribed": ["transcribed"],
            "reviewed": ["reviewed"]
        }
        
        status_list = []
        for dt in task.data_types:
            if dt in data_type_mapping:
                status_list.extend(data_type_mapping[dt])
        
        # 直接使用标注页面已经划分好的数据集
        # 从数据库中获取录音记录，包括 in_evaluation_set 字段
        # 构建查询条件
        query = db.query(Recording)
        if task.recording_task_id:
            query = query.filter(Recording.task_id == task.recording_task_id)
            print(f"[FINE-TUNE] 过滤任务ID: {task.recording_task_id}")
        if task.pack_id:
            # 限制pack_id长度，避免数据库错误
            limited_pack_id = task.pack_id[:5]  # 限制为5个字符
            query = query.filter(Recording.pack_id == limited_pack_id)
            print(f"[FINE-TUNE] 过滤语料包ID: {limited_pack_id} (原始: {task.pack_id})")
        if status_list:
            query = query.filter(Recording.status.in_(status_list))
            print(f"[FINE-TUNE] 过滤状态: {status_list}")
        
        # 执行查询
        recordings_with_evaluation = query.all()
        print(f"[FINE-TUNE] 数据库查询结果: {len(recordings_with_evaluation)} 条记录")
        
        if not recordings_with_evaluation:
            raise ValueError(f"没有找到符合条件的录音记录。请检查任务ID、语料包ID和数据类型选择是否正确。")
        
        # 按 dataset_split 字段划分数据集
        # 训练集: dataset_split = 'train'
        # 验证集: dataset_split = 'val'
        # 评估集: dataset_split = 'eval'
        train_recordings = [r for r in recordings_with_evaluation if r.dataset_split == 'train']
        val_recordings = [r for r in recordings_with_evaluation if r.dataset_split == 'val']
        test_recordings = [r for r in recordings_with_evaluation if r.dataset_split == 'eval']
        
        print(f"[FINE-TUNE] 数据集划分:")
        print(f"  训练集: {len(train_recordings)} 条")
        print(f"  验证集: {len(val_recordings)} 条")
        print(f"  评估集: {len(test_recordings)} 条")
        
        if not train_recordings and not val_recordings:
            raise ValueError("训练集和验证集为空，请确保有数据被标记为训练集或验证集。")
        
        # 准备训练集数据
        train_audio = []
        train_texts = []
        train_pack = []
        for r in train_recordings:
            audio_path = r.audio_path_wav or r.audio_path_webm
            if audio_path and os.path.exists(audio_path):
                # 限制pack_id长度，避免数据库错误
                pack_id = (r.pack_id or "default")[:5]  # 限制为5个字符
                train_audio.append(audio_path)
                train_texts.append(r.text_target)
                train_pack.append(pack_id)
            else:
                print(f"[FINE-TUNE] 跳过无效音频: {audio_path}")
        
        # 准备验证集数据
        val_audio = []
        val_texts = []
        val_pack = []
        for r in val_recordings:
            audio_path = r.audio_path_wav or r.audio_path_webm
            if audio_path and os.path.exists(audio_path):
                # 限制pack_id长度，避免数据库错误
                pack_id = (r.pack_id or "default")[:5]  # 限制为5个字符
                val_audio.append(audio_path)
                val_texts.append(r.text_target)
                val_pack.append(pack_id)
            else:
                print(f"[FINE-TUNE] 跳过无效验证音频: {audio_path}")
        
        # 准备评估集数据
        test_audio = []
        test_texts = []
        test_pack = []
        for r in test_recordings:
            audio_path = r.audio_path_wav or r.audio_path_webm
            if audio_path and os.path.exists(audio_path):
                # 限制pack_id长度，避免数据库错误
                pack_id = (r.pack_id or "default")[:5]  # 限制为5个字符
                test_audio.append(audio_path)
                test_texts.append(r.text_target)
                test_pack.append(pack_id)
            else:
                print(f"[FINE-TUNE] 跳过无效评估音频: {audio_path}")
        
        # 构建pack_info_by_id
        pack_info_by_id = {}
        for r in train_recordings:
            pack_id = (r.pack_id or "default")[:5]  # 限制为5个字符
            if pack_id not in pack_info_by_id:
                pack_info_by_id[pack_id] = pack_id
        
        print(f"[FINE-TUNE] 最终数据集:")
        print(f"  训练集: {len(train_audio)} 条")
        print(f"  验证集: {len(val_audio)} 条")
        print(f"  评估集: {len(test_audio)} 条")
        print(f"  语料包数量: {len(pack_info_by_id)} 个")
        
        if not train_audio:
            raise ValueError("训练数据为空，请确保选择的数据包含有效的音频文件。")
        
        # 创建微调器
        model_type = task.params.get("model_type", "small")
        model_name = f"openai/whisper-{model_type}"
        
        print(f"[FINE-TUNE] 创建WhisperFineTuner，task_name={task.task_name}")
        
        tuner = WhisperFineTuner(
            model_name=model_name,
            output_dir="models",
            task_name=task.task_name,  # 传递微调事件名称
            fine_tune_type=task.fine_tune_type  # 传递微调类型
        )
        
        # 执行微调
        task.progress = 10
        print(f"[FINE-TUNE] 开始微调，模型: {model_name}")
        
        # 调用微调方法，传递训练集、验证集和评估集
        result = await asyncio.to_thread(
            tuner.fine_tune,
            train_audio_paths=train_audio,
            train_texts=train_texts,
            eval_audio_paths=val_audio,
            eval_texts=val_texts,
            test_audio_paths=test_audio,
            test_texts=test_texts,
            pack_ids=train_pack,
            test_pack_ids=test_pack,
            epochs=task.params.get("epochs", 3),
            batch_size=task.params.get("batch_size", 8),
            learning_rate=task.params.get("learning_rate", 1e-5),
            warmup_steps=task.params.get("warmup_steps", 500),
            gradient_accumulation_steps=task.params.get("gradient_accumulation_steps", 1),
            eval_steps=task.params.get("eval_steps", 100),
            save_steps=task.params.get("save_steps", 500),
            logging_steps=task.params.get("logging_steps", 50),
            pack_info=pack_info_by_id
        )
        
        # 提取训练结果
        model_path = result.get("model_path") if isinstance(result, dict) else result
        total_epochs = result.get("total_epochs", task.total_epochs) if isinstance(result, dict) else task.total_epochs
        best_epoch = result.get("best_epoch", 0) if isinstance(result, dict) else 0
        best_val_loss = result.get("best_val_loss") if isinstance(result, dict) else None
        best_wer = result.get("best_wer") if isinstance(result, dict) else None
        best_cer = result.get("best_cer") if isinstance(result, dict) else None
        epoch_reports = result.get("epoch_reports", []) if isinstance(result, dict) else []
        stop_reason = result.get("stop_reason", "正常结束") if isinstance(result, dict) else "正常结束"
        test_wer = result.get("test_wer") if isinstance(result, dict) else None
        test_cer = result.get("test_cer") if isinstance(result, dict) else None
        test_wer_details = result.get("test_wer_details") if isinstance(result, dict) else None
        test_cer_details = result.get("test_cer_details") if isinstance(result, dict) else None
        test_pack_stats = result.get("test_pack_stats") if isinstance(result, dict) else None
        
        # 训练完成
        task.status = "completed"
        task.progress = 100
        task.model_path = model_path
        task.training_time = int((datetime.now() - task.start_time).total_seconds())
        
        print(f"[FINE-TUNE] 微调完成，模型路径: {model_path}")
        print(f"[FINE-TUNE] 训练时间: {task.training_time}秒")
        
        # 保存微调记录到数据库
        db = next(get_db())
        try:
            history_record = FineTuneHistory(
                task_id=task.task_id,
                task_name=task.task_name,
                status="completed",
                params_json=json.dumps(task.params),
                data_count=len(train_audio),  # 使用训练数据的数量
                total_epochs=total_epochs,
                best_epoch=best_epoch,
                best_val_loss=best_val_loss,
                best_wer=best_wer,
                best_cer=best_cer,
                training_time=task.training_time,
                stop_reason=stop_reason,
                model_path=model_path,
                epoch_reports_json=json.dumps(epoch_reports) if epoch_reports else None,
                test_wer=test_wer,
                test_cer=test_cer,
                test_wer_details_json=json.dumps(test_wer_details) if test_wer_details else None,
                test_cer_details_json=json.dumps(test_cer_details) if test_cer_details else None,
                test_pack_stats_json=json.dumps(test_pack_stats) if test_pack_stats else None
            )
            db.add(history_record)
            db.commit()
            print(f"[FINE-TUNE] 微调记录已保存到数据库，ID: {history_record.id}")
        except Exception as e:
            print(f"[ERROR] 保存微调记录失败: {str(e)}")
            db.rollback()
        finally:
            db.close()
            
    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        print(f"[ERROR] 微调任务失败: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # 保存失败的微调记录到数据库
        db = next(get_db())
        try:
            history_record = FineTuneHistory(
                task_id=task.task_id,
                task_name=task.task_name,
                status="failed",
                error_message=str(e),
                params_json=json.dumps(task.params),
                data_count=0,
                training_time=int((datetime.now() - task.start_time).total_seconds())
            )
            db.add(history_record)
            db.commit()
        except Exception as db_error:
            print(f"[ERROR] 保存失败微调记录失败: {str(db_error)}")
            db.rollback()
        finally:
            db.close()


@router.get("/history")
async def get_fine_tune_history(db: Session = Depends(get_db)):
    """获取微调历史记录"""
    try:
        history = db.query(FineTuneHistory).order_by(FineTuneHistory.created_at.desc()).all()
        return {
            "history": [
                {
                    "id": h.id,
                    "task_id": h.task_id,
                    "task_name": h.task_name,
                    "status": h.status,
                    "error_message": h.error_message,
                    "params": json.loads(h.params_json) if h.params_json else None,
                    "data_count": h.data_count,
                    "total_epochs": h.total_epochs,
                    "best_epoch": h.best_epoch,
                    "best_val_loss": h.best_val_loss,
                    "best_wer": h.best_wer,
                    "training_time": h.training_time,
                    "stop_reason": h.stop_reason,
                    "model_path": h.model_path,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                    "updated_at": h.updated_at.isoformat() if h.updated_at else None
                }
                for h in history
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取微调历史失败: {str(e)}")


@router.get("/history/{history_id}")
async def get_fine_tune_history_detail(history_id: int, db: Session = Depends(get_db)):
    """获取微调历史详情"""
    try:
        history = db.query(FineTuneHistory).filter(FineTuneHistory.id == history_id).first()
        if not history:
            raise HTTPException(status_code=404, detail="微调记录不存在")
        
        return {
            "id": history.id,
            "task_id": history.task_id,
            "task_name": history.task_name,
            "status": history.status,
            "error_message": history.error_message,
            "params": json.loads(history.params_json) if history.params_json else None,
            "data_count": history.data_count,
            "total_epochs": history.total_epochs,
            "best_epoch": history.best_epoch,
            "best_val_loss": history.best_val_loss,
            "best_wer": history.best_wer,
            "best_cer": history.best_cer,
            "training_time": history.training_time,
            "stop_reason": history.stop_reason,
            "model_path": history.model_path,
            "epoch_reports": json.loads(history.epoch_reports_json) if history.epoch_reports_json else [],
            "test_wer": history.test_wer,
            "test_cer": history.test_cer,
            "test_wer_details": json.loads(history.test_wer_details_json) if history.test_wer_details_json else [],
            "test_cer_details": json.loads(history.test_cer_details_json) if history.test_cer_details_json else [],
            "test_pack_stats": json.loads(history.test_pack_stats_json) if history.test_pack_stats_json else {},
            "created_at": history.created_at.isoformat() if history.created_at else None,
            "updated_at": history.updated_at.isoformat() if history.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取微调历史详情失败: {str(e)}")


class ConvertModelRequest(BaseModel):
    """模型转换请求模型"""
    model_path: str
    quantization_type: str = "q4_0"


@router.post("/convert")
async def convert_model(request: ConvertModelRequest):
    """转换模型为ggml格式并量化"""
    try:
        from model_converter import ModelConverter
        
        converter = ModelConverter()
        
        # 执行转换
        result = converter.convert_to_ggml(
            request.model_path
        )
        
        # 尝试量化
        try:
            quantized_result = converter.quantize_model(
                result,
                quantization_type=request.quantization_type
            )
            return {
                "success": True,
                "message": "模型转换和量化成功",
                "result": {
                    "ggml_model": result,
                    "quantized_model": quantized_result,
                    "quantization_type": request.quantization_type
                }
            }
        except Exception as e:
            # 如果量化失败，仍然返回转换成功的结果
            return {
                "success": True,
                "message": "模型转换成功，量化失败",
                "result": {
                    "ggml_model": result,
                    "quantized_model": None,
                    "quantization_type": request.quantization_type,
                    "quantization_error": str(e)
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型转换失败: {str(e)}")


@router.get("/check-whisper-cpp")
async def check_whisper_cpp():
    """检查whisper.cpp是否可用"""
    try:
        from model_converter import ModelConverter
        
        converter = ModelConverter()
        
        return {
            "success": True,
            "whisper_cpp_path": str(converter.whisper_cpp_path) if converter.whisper_cpp_path else None,
            "has_convert_script": bool(converter.convert_script and converter.convert_script.exists()),
            "has_quantize_tool": bool(converter.quantize_script and converter.quantize_script.exists()),
            "ready": bool(converter.whisper_cpp_path and converter.convert_script and converter.quantize_script)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查whisper.cpp失败: {str(e)}")


class ConvertCTranslate2Request(BaseModel):
    """CTranslate2模型转换请求模型"""
    model_path: str
    compute_type: str = "int8"


@router.post("/convert-ctranslate2")
async def convert_to_ctranslate2(request: ConvertCTranslate2Request):
    """将Hugging Face格式的Whisper模型转换为CTranslate2格式"""
    try:
        import subprocess
        import sys
        import shutil
        
        model_path = Path(request.model_path)
        if not model_path.exists():
            raise HTTPException(status_code=400, detail=f"模型路径不存在: {model_path}")
        
        output_name = model_path.name + "-ct2"
        output_dir = Path(__file__).parent.parent / "models" / output_name
        
        if output_dir.exists():
            shutil.rmtree(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n{'='*50}")
        print(f"开始转换模型为CTranslate2格式")
        print(f"输入: {model_path}")
        print(f"输出: {output_dir}")
        print(f"计算类型: {request.compute_type}")
        print(f"{'='*50}")
        
        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, WhisperForConditionalGeneration
            from transformers.models.whisper import WhisperProcessor
        except ImportError:
            raise HTTPException(status_code=500, detail="transformers库未安装，请运行: pip install transformers")
        
        compute_type_map = {
            "int8": "int8",
            "int8_float16": "int8_float16",
            "float16": "float16",
            "float32": "float32"
        }
        
        hf_compute_type = compute_type_map.get(request.compute_type, "int8")
        
        try:
            from ctransformers import AutoModelForCausalLM
            print("ctransformers库已安装，尝试使用它进行转换...")
            
            converter_code = f'''
import sys
from ctransformers import AutoModelForCausalLM

model = AutoModelForCausalLM.from_pretrained(
    "{model_path}",
    model_type="whisper",
    gpu_layers=0
)

model.save("{output_dir}")
print("转换完成!")
'''
            
            result = subprocess.run(
                [sys.executable, "-c", converter_code],
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                print("CTranslate2转换成功!")
                return {
                    "success": True,
                    "message": "模型转换为CTranslate2成功",
                    "output_path": str(output_dir),
                    "compute_type": request.compute_type,
                    "note": "请确保转换后的模型包含model.bin文件"
                }
            else:
                print(f"ctransformers转换失败: {{result.stderr}}")
                raise Exception(result.stderr)
                
        except ImportError:
            print("ctransformers未安装，尝试手动复制模型文件...")
            
            import shutil
            shutil.copytree(model_path, output_dir, dirs_exist_ok=True)
            
            return {
                "success": True,
                "message": "模型文件已复制到models目录，请手动使用transformers-cli转换为CTranslate2格式",
                "output_path": str(output_dir),
                "compute_type": request.compute_type,
                "manual_steps": [
                    "1. 安装ctransformers: pip install ctransformers",
                    f"2. 使用命令转换: ctransformers-convert --model {model_path} --output {output_dir}",
                    "3. 或者在Whisper服务器中直接加载HuggingFace格式模型"
                ]
            }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"CTranslate2转换失败: {str(e)}")