"""
辰溪话语音采集系统 - FastAPI 后端
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import aiofiles
import uuid
import os
from pathlib import Path
from typing import Optional
import csv
import json
import glob
from datetime import datetime

# 导入数据库和音频转换
from database import init_db, get_db, Recording, Speaker
from audio_converter import convert_webm_to_wav, get_audio_duration

app = FastAPI(title="辰溪话语音采集API", version="1.0.0")

# 注册认证路由
from api_auth import router as auth_router
app.include_router(auth_router, prefix="/api")

# 注册标注路由
from api_transcribe import router as transcribe_router
app.include_router(transcribe_router, prefix="/api")

# 注册微调路由
from api_fine_tune import router as fine_tune_router
app.include_router(fine_tune_router, prefix="/api")

# 注册音频服务路由
from api_audio import router as audio_router
app.include_router(audio_router, prefix="/api")

# CORS配置（允许前端跨域）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置路径
BASE_DIR = Path(__file__).parent
RECORDINGS_DIR = BASE_DIR / "recordings"
RECORDINGS_DIR.mkdir(exist_ok=True)
CSV_FILE = BASE_DIR.parent / "辰溪话_朗读语料包v1_480句.csv"

# 初始化数据库
init_db()

# 内存缓存语料包数据
script_packs_cache = {}


def load_script_packs(task_id=None):
    """加载CSV语料包并组织为JSON格式"""
    global script_packs_cache
    
    # 为不同任务使用不同的缓存
    cache_key = task_id or 'default'
    if cache_key in script_packs_cache:
        print(f"[CACHE] 使用缓存的语料包数据 (任务: {task_id})")
        return script_packs_cache[cache_key]
    
    # 根据任务ID选择不同的CSV文件
    csv_file = CSV_FILE
    if task_id:
        # 尝试使用任务特定的CSV文件
        # 首先尝试带原始文件名的版本（例如 task_id_辰溪话_朗读语料包v2 .csv）
        task_csv_files = []
        # 查找所有以task_id_开头的CSV文件
        for file in os.listdir(BASE_DIR.parent):
            if file.startswith(f"{task_id}_") and file.endswith('.csv'):
                task_csv_files.append(BASE_DIR.parent / file)
        
        if task_csv_files:
            # 选择最新的文件
            csv_file = sorted(task_csv_files, key=os.path.getmtime, reverse=True)[0]
            print(f"[LOAD] 使用任务特定的CSV文件: {csv_file}")
        else:
            # 尝试使用简单的任务ID命名的文件
            task_csv_file = BASE_DIR.parent / f"{task_id}.csv"
            if task_csv_file.exists():
                csv_file = task_csv_file
                print(f"[LOAD] 使用任务特定的CSV文件: {csv_file}")
    
    # 检查CSV文件是否存在
    print(f"[LOAD] 开始加载CSV文件: {csv_file}")
    print(f"[LOAD] 文件绝对路径: {csv_file.absolute()}")
    print(f"[LOAD] 文件存在: {csv_file.exists()}")
    
    if not csv_file.exists():
        error_msg = f"语料包文件不存在: {csv_file}\n请确保CSV文件位于项目根目录"
        print(f"[ERROR] {error_msg}")
        raise FileNotFoundError(error_msg)
    
    packs = {}
    
    try:
        print(f"[LOAD] 打开CSV文件...")
        # 尝试不同编码打开文件
        encodings = ['utf-8-sig', 'gbk', 'gb2312', 'utf-8']
        
        for encoding in encodings:
            try:
                with open(csv_file, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    # 清理表头中的BOM和空白字符
                    if reader.fieldnames:
                        reader.fieldnames = [field.strip().lstrip('\ufeff') for field in reader.fieldnames]
                    print(f"[LOAD] 成功以 {encoding} 编码打开文件")
                    print(f"[LOAD] CSV表头: {reader.fieldnames}")
                    
                    if not reader.fieldnames:
                        raise ValueError("CSV文件没有表头")
                    
                    row_count = 0
                    for row in reader:
                        row_count += 1
                        pack_id = row.get('pack_id', '').strip()
                        if not pack_id:
                            print(f"[WARN] 第{row_count}行缺少pack_id，跳过")
                            continue
                        
                        if pack_id not in packs:
                            packs[pack_id] = []
                        
                        packs[pack_id].append({
                            'sentence_id': row.get('sentence_id', '').strip(),
                            'category': row.get('category', '').strip(),
                            'text_target': row.get('text_target', '').strip(),
                            'text_mandarin_gloss': row.get('text_mandarin_gloss', '').strip(),
                            'notes': row.get('notes', '').strip()
                        })
                    
                    if row_count == 0:
                        raise ValueError("CSV文件为空或格式不正确")
                    
                    print(f"[SUCCESS] 成功加载语料包: {len(packs)} 个包, 共 {row_count} 句")
                    for pack_id, sentences in packs.items():
                        print(f"  - {pack_id}: {len(sentences)} 句")
                    
                    # 缓存结果
                    script_packs_cache[cache_key] = packs
                    return packs
            except UnicodeDecodeError:
                print(f"[WARN] 尝试以 {encoding} 编码打开失败，继续尝试")
                continue
        
        # 所有编码都失败
        raise ValueError("无法以任何支持的编码打开CSV文件")
                
    except ValueError as e:
        error_msg = f"CSV文件格式错误: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise ValueError(error_msg)
    except Exception as e:
        import traceback
        error_msg = f"读取CSV文件失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        print(f"[ERROR] 详细错误: {traceback.format_exc()}")
        raise ValueError(error_msg)
    
    # 缓存结果
    script_packs_cache[cache_key] = packs
    return packs


@app.get("/")
async def root():
    """健康检查"""
    return {
        "message": "辰溪话语音采集API", 
        "status": "running",
        "csv_file": str(CSV_FILE),
        "csv_exists": CSV_FILE.exists()
    }

@app.get("/api/health")
async def health_check():
    """详细的健康检查"""
    csv_status = "存在" if CSV_FILE.exists() else "不存在"
    return {
        "status": "ok",
        "csv_file_path": str(CSV_FILE),
        "csv_file_exists": CSV_FILE.exists(),
        "csv_status": csv_status,
        "recordings_dir": str(RECORDINGS_DIR),
        "recordings_dir_exists": RECORDINGS_DIR.exists()
    }


@app.get("/api/script-pack/list")
async def get_script_pack_list(task_id: Optional[str] = None):
    """获取语料包列表"""
    try:
        print(f"[API] 收到请求: /api/script-pack/list")
        print(f"[API] 任务ID: {task_id}")
        
        packs = load_script_packs(task_id)
        
        if not packs:
            error_msg = "语料包数据为空，请检查CSV文件"
            print(f"[ERROR] {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)
        
        result = {
            "packs": [
                {
                    "pack_id": pack_id,
                    "sentence_count": len(sentences),
                    "categories": list(set(s['category'] for s in sentences))
                }
                for pack_id, sentences in packs.items()
            ]
        }
        
        print(f"[API] 成功返回 {len(result['packs'])} 个语料包")
        return result
        
    except FileNotFoundError as e:
        error_msg = f"CSV文件未找到: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise HTTPException(status_code=404, detail=error_msg)
    except ValueError as e:
        error_msg = f"CSV文件格式错误: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        import traceback
        error_msg = f"加载语料包失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        print(f"[ERROR] 详细错误: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/api/script-pack/import")
async def import_script_pack(
    file: UploadFile = File(...),
    task_id: str = Form(...)
):
    """导入语料包CSV文件"""
    global script_packs_cache
    
    print(f"[API] 收到语料包导入请求")
    print(f"[API] 任务ID: {task_id}")
    print(f"[API] 文件名: {file.filename}")
    
    # 验证文件扩展名
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="只支持CSV文件")
    
    # 保存上传的文件
    import_file_path = BASE_DIR.parent / f"{task_id}_{file.filename}"
    try:
        async with aiofiles.open(import_file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        print(f"[API] 文件已保存到: {import_file_path}")
    except Exception as e:
        error_msg = f"保存文件失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)
    
    # 清除缓存以重新加载
    cache_key = task_id or 'default'
    if cache_key in script_packs_cache:
        del script_packs_cache[cache_key]
        print(f"[API] 已清除缓存: {cache_key}")
    
    # 验证CSV文件格式
    try:
        packs = load_script_packs(task_id)
        total_sentences = sum(len(sentences) for sentences in packs.values())
        print(f"[API] 成功导入语料包: {len(packs)} 个包, 共 {total_sentences} 句")
        
        return {
            "success": True,
            "message": f"成功导入语料包: {len(packs)} 个包, 共 {total_sentences} 句",
            "packs": [
                {
                    "pack_id": pack_id,
                    "sentence_count": len(sentences)
                }
                for pack_id, sentences in packs.items()
            ]
        }
    except Exception as e:
        error_msg = f"导入语料包失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/api/script-pack/{pack_id}")
async def get_script_pack(pack_id: str, task_id: Optional[str] = None):
    """获取指定语料包的句子列表"""
    packs = load_script_packs(task_id)
    
    if pack_id not in packs:
        raise HTTPException(status_code=404, detail=f"语料包 {pack_id} 不存在")
    
    return {
        "pack_id": pack_id,
        "sentences": packs[pack_id],
        "total": len(packs[pack_id])
    }


@app.get("/api/script-pack/{pack_id}/sentence/{sentence_id}")
async def get_sentence(pack_id: str, sentence_id: str, task_id: Optional[str] = None):
    """获取单个句子信息"""
    packs = load_script_packs(task_id)
    
    if pack_id not in packs:
        raise HTTPException(status_code=404, detail=f"语料包 {pack_id} 不存在")
    
    sentence = next(
        (s for s in packs[pack_id] if s['sentence_id'] == sentence_id),
        None
    )
    
    if not sentence:
        raise HTTPException(status_code=404, detail=f"句子 {sentence_id} 不存在")
    
    return sentence


@app.post("/api/collect/upload")
async def upload_recording(
    audio: UploadFile = File(...),
    speaker_id: str = Form(...),
    task_id: str = Form(...),  # 添加任务ID
    pack_id: str = Form(...),
    sentence_id: str = Form(...),
    text_target: str = Form(...),
    duration_ms: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """上传录音文件（支持覆盖）"""
    
    # 检查是否已存在相同speaker_id + task_id + sentence_id的录音
    existing_recording = db.query(Recording).filter(
        Recording.speaker_id == speaker_id,
        Recording.task_id == task_id,  # 添加任务ID条件
        Recording.sentence_id == sentence_id
    ).first()
    
    is_update = existing_recording is not None
    
    if is_update:
        # 覆盖模式：使用现有的recording_id
        recording_id = existing_recording.recording_id
        print(f"[UPLOAD] 覆盖现有录音: {recording_id}")
        
        # 删除旧文件
        if existing_recording.audio_path_webm and Path(existing_recording.audio_path_webm).exists():
            try:
                os.remove(existing_recording.audio_path_webm)
            except:
                pass
        if existing_recording.audio_path_wav and Path(existing_recording.audio_path_wav).exists():
            try:
                os.remove(existing_recording.audio_path_wav)
            except:
                pass
    else:
        # 新增模式：生成新的recording_id
        recording_id = f"{speaker_id}_{sentence_id}_{uuid.uuid4().hex[:8]}"
        print(f"[UPLOAD] 新增录音: {recording_id}")
    
    # 保存webm文件
    audio_filename_webm = f"{recording_id}.webm"
    audio_path_webm = RECORDINGS_DIR / audio_filename_webm
    
    try:
        # 保存原始音频文件
        async with aiofiles.open(audio_path_webm, 'wb') as f:
            content = await audio.read()
            await f.write(content)
        
        # 获取文件大小
        file_size = os.path.getsize(audio_path_webm)
        
        # 获取音频时长
        if duration_ms is None:
            duration_seconds = get_audio_duration(str(audio_path_webm))
            duration_ms = int(duration_seconds * 1000)
        
        # 转换为wav格式
        audio_path_wav = None
        try:
            wav_filename = f"{recording_id}.wav"
            audio_path_wav_full = RECORDINGS_DIR / wav_filename
            convert_webm_to_wav(str(audio_path_webm), str(audio_path_wav_full))
            audio_path_wav = str(audio_path_wav_full)
            print(f"[UPLOAD] 音频转换成功: {audio_path_wav}")
        except Exception as e:
            print(f"[WARN] 音频转换失败（可继续）: {e}")
            # 转换失败不影响上传，只是没有wav文件
        
        # 确保说话人存在
        speaker = db.query(Speaker).filter(Speaker.speaker_id == speaker_id).first()
        if not speaker:
            speaker = Speaker(speaker_id=speaker_id)
            db.add(speaker)
            db.commit()
        
        # 保存或更新录音记录
        if is_update:
            # 更新现有记录
            existing_recording.audio_path_webm = str(audio_path_webm)
            existing_recording.audio_path_wav = audio_path_wav
            existing_recording.file_size = file_size
            existing_recording.duration_ms = duration_ms
            existing_recording.status = "pending"  # 重新上传后重置状态
            existing_recording.text_target = text_target
            existing_recording.updated_at = datetime.now()
            recording = existing_recording
        else:
            # 创建新记录
            recording = Recording(
                recording_id=recording_id,
                speaker_id=speaker_id,
                task_id=task_id,  # 添加任务ID
                pack_id=pack_id,
                sentence_id=sentence_id,
                audio_path_webm=str(audio_path_webm),
                audio_path_wav=audio_path_wav,
                text_target=text_target,
                file_size=file_size,
                duration_ms=duration_ms,
                status="pending"
            )
            db.add(recording)
        
        db.commit()
        db.refresh(recording)
        
        # 获取下一句
        packs = load_script_packs()
        current_pack = packs.get(pack_id, [])
        current_index = next(
            (i for i, s in enumerate(current_pack) if s['sentence_id'] == sentence_id),
            -1
        )
        
        next_sentence = None
        if current_index >= 0 and current_index < len(current_pack) - 1:
            next_sentence = current_pack[current_index + 1]
        
        return {
            "success": True,
            "recording_id": recording_id,
            "message": "覆盖成功" if is_update else "上传成功",
            "is_update": is_update,
            "next_sentence": next_sentence,
            "is_pack_complete": current_index == len(current_pack) - 1,
            "has_wav": audio_path_wav is not None
        }
        
    except Exception as e:
        import traceback
        error_msg = f"上传失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        print(f"[ERROR] {traceback.format_exc()}")
        
        # 如果出错，删除已保存的文件
        if audio_path_webm.exists():
            try:
                os.remove(audio_path_webm)
            except:
                pass
        
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/api/recordings/{speaker_id}")
async def get_speaker_recordings(speaker_id: str, db: Session = Depends(get_db)):
    """获取说话人的录音记录"""
    recordings_query = db.query(Recording).filter(Recording.speaker_id == speaker_id)
    recordings_list = recordings_query.all()
    
    recordings = [
        {
            "recording_id": r.recording_id,
            "pack_id": r.pack_id,
            "task_id": r.task_id,  # 添加任务ID
            "sentence_id": r.sentence_id,
            "status": r.status,
            "duration_ms": r.duration_ms,
            "has_wav": r.audio_path_wav is not None,
            "audio_path_wav": r.audio_path_wav,
            "audio_path_webm": r.audio_path_webm,
            "in_evaluation_set": r.in_evaluation_set,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None
        }
        for r in recordings_list
    ]
    
    return {
        "speaker_id": speaker_id,
        "recordings": recordings,
        "total": len(recordings)
    }


@app.get("/api/recordings/{speaker_id}/progress/{pack_id}")
async def get_progress(speaker_id: str, pack_id: str, task_id: Optional[str] = None, db: Session = Depends(get_db)):
    """获取说话人在指定包中的采集进度"""
    packs = load_script_packs(task_id)
    
    if pack_id not in packs:
        raise HTTPException(status_code=404, detail=f"语料包 {pack_id} 不存在")
    
    total_sentences = len(packs[pack_id])
    
    # 从数据库获取已完成的句子（添加任务ID条件）
    query = db.query(Recording).filter(
        Recording.speaker_id == speaker_id,
        Recording.pack_id == pack_id,
        Recording.status != 'rejected'
    )
    
    # 如果提供了任务ID，添加任务ID条件
    if task_id:
        query = query.filter(Recording.task_id == task_id)
    
    completed_recordings = query.all()
    completed = [r.sentence_id for r in completed_recordings]
    
    return {
        "speaker_id": speaker_id,
        "task_id": task_id,
        "pack_id": pack_id,
        "completed": len(completed),
        "total": total_sentences,
        "percentage": round(len(completed) / total_sentences * 100, 1) if total_sentences > 0 else 0,
        "completed_sentences": completed
    }


@app.post("/api/recordings/evaluation-set")
async def toggle_evaluation_set(
    speaker_id: str = Form(...),
    sentence_id: str = Form(...),
    task_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """切换句子的评估集状态"""
    try:
        # 查找对应的录音记录
        recording = db.query(Recording).filter(
            Recording.speaker_id == speaker_id,
            Recording.sentence_id == sentence_id,
            Recording.task_id == task_id
        ).first()
        
        if not recording:
            raise HTTPException(status_code=404, detail="录音记录不存在")
        
        # 切换评估集状态
        recording.in_evaluation_set = not recording.in_evaluation_set
        db.commit()
        db.refresh(recording)
        
        return {
            "success": True,
            "message": f"已{'添加到' if recording.in_evaluation_set else '移出'}评估集",
            "in_evaluation_set": recording.in_evaluation_set
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"切换评估集状态失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

