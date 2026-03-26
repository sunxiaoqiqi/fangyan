"""
标注相关API
"""
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from database import get_db, Recording, Task
from datetime import datetime

router = APIRouter(prefix="/transcribe", tags=["标注"])


@router.get("/pending")
async def get_pending_recordings(
    pack_id: Optional[str] = None,
    task_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """获取待标注的录音列表"""
    query = db.query(Recording).filter(Recording.status == "pending")
    
    if pack_id:
        query = query.filter(Recording.pack_id == pack_id)
    
    if task_id:
        query = query.filter(Recording.task_id == task_id)
    
    total = query.count()
    recordings = query.order_by(Recording.created_at.desc()).offset(offset).limit(limit).all()

    # 预取任务名称
    task_ids = {r.task_id for r in recordings if r.task_id}
    tasks_map = {}
    if task_ids:
        tasks = db.query(Task).filter(Task.task_id.in_(task_ids)).all()
        tasks_map = {t.task_id: t.task_name for t in tasks}
    
    return {
        "total": total,
        "recordings": [
            {
                "recording_id": r.recording_id,
                "speaker_id": r.speaker_id,
                "pack_id": r.pack_id,
                "task_id": r.task_id,
                "task_name": tasks_map.get(r.task_id),
                "sentence_id": r.sentence_id,
                "text_target": r.text_target,
                "audio_path_wav": r.audio_path_wav or r.audio_path_webm,
                "duration_ms": r.duration_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "dataset_split": r.dataset_split,
            }
            for r in recordings
        ]
    }


@router.get("/list")
async def get_recordings_list(
    status: Optional[str] = None,
    pack_id: Optional[str] = None,
    task_id: Optional[str] = None,
    dataset_split: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """获取录音列表（支持状态筛选）"""
    query = db.query(Recording)
    
    if status:
        query = query.filter(Recording.status == status)
    
    if pack_id:
        query = query.filter(Recording.pack_id == pack_id)
    
    if task_id:
        query = query.filter(Recording.task_id == task_id)
    
    if dataset_split:
        query = query.filter(Recording.dataset_split == dataset_split)
    
    total = query.count()
    recordings = query.order_by(Recording.created_at.desc()).offset(offset).limit(limit).all()

    # 预取任务名称
    task_ids = {r.task_id for r in recordings if r.task_id}
    tasks_map = {}
    if task_ids:
        tasks = db.query(Task).filter(Task.task_id.in_(task_ids)).all()
        tasks_map = {t.task_id: t.task_name for t in tasks}
    
    return {
        "total": total,
        "recordings": [
            {
                "recording_id": r.recording_id,
                "speaker_id": r.speaker_id,
                "pack_id": r.pack_id,
                "task_id": r.task_id,
                "task_name": tasks_map.get(r.task_id),
                "sentence_id": r.sentence_id,
                "text_target": r.text_target,
                "text_transcript": r.text_transcript,
                "audio_path_wav": r.audio_path_wav or r.audio_path_webm,
                "duration_ms": r.duration_ms,
                "status": r.status,
                "dataset_split": r.dataset_split,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recordings
        ]
    }


@router.get("/{recording_id}")
async def get_recording(recording_id: str, db: Session = Depends(get_db)):
    """获取单个录音详情"""
    recording = db.query(Recording).filter(Recording.recording_id == recording_id).first()
    
    if not recording:
        raise HTTPException(status_code=404, detail="录音不存在")
    
    return {
        "recording_id": recording.recording_id,
        "speaker_id": recording.speaker_id,
        "pack_id": recording.pack_id,
        "sentence_id": recording.sentence_id,
        "text_target": recording.text_target,
        "text_transcript": recording.text_transcript,
        "audio_path_wav": recording.audio_path_wav or recording.audio_path_webm,
        "audio_path_webm": recording.audio_path_webm,
        "duration_ms": recording.duration_ms,
        "status": recording.status,
        "notes": recording.notes,
        "dataset_split": recording.dataset_split,
        "created_at": recording.created_at.isoformat() if recording.created_at else None,
        "updated_at": recording.updated_at.isoformat() if recording.updated_at else None,
    }


@router.post("/{recording_id}/transcribe")
async def submit_transcription(
    recording_id: str,
    text_transcript: str = Form(...),
    transcribed_by: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """提交转写文本"""
    recording = db.query(Recording).filter(Recording.recording_id == recording_id).first()
    
    if not recording:
        raise HTTPException(status_code=404, detail="录音不存在")
    
    recording.text_transcript = text_transcript.strip()
    recording.transcribed_by = transcribed_by
    recording.notes = notes
    recording.status = "transcribed"
    recording.updated_at = datetime.now()
    
    db.commit()
    db.refresh(recording)
    
    return {
        "success": True,
        "recording_id": recording_id,
        "status": recording.status
    }


@router.post("/{recording_id}/reject")
async def reject_recording(
    recording_id: str,
    reason: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """拒绝录音（标记为不合格）"""
    recording = db.query(Recording).filter(Recording.recording_id == recording_id).first()
    
    if not recording:
        raise HTTPException(status_code=404, detail="录音不存在")
    
    recording.status = "rejected"
    recording.notes = reason
    recording.updated_at = datetime.now()
    
    db.commit()
    
    return {
        "success": True,
        "recording_id": recording_id,
        "status": "rejected"
    }


@router.get("/list")
async def get_recordings_list(
    status: Optional[str] = None,
    pack_id: Optional[str] = None,
    task_id: Optional[str] = None,
    dataset_split: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """获取录音列表（支持状态筛选）"""
    query = db.query(Recording)
    
    if status:
        query = query.filter(Recording.status == status)
    
    if pack_id:
        query = query.filter(Recording.pack_id == pack_id)
    
    if task_id:
        query = query.filter(Recording.task_id == task_id)
    
    if dataset_split:
        query = query.filter(Recording.dataset_split == dataset_split)
    
    total = query.count()
    recordings = query.order_by(Recording.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "recordings": [
            {
                "recording_id": r.recording_id,
                "speaker_id": r.speaker_id,
                "pack_id": r.pack_id,
                "sentence_id": r.sentence_id,
                "text_target": r.text_target,
                "text_transcript": r.text_transcript,
                "audio_path_wav": r.audio_path_wav or r.audio_path_webm,
                "duration_ms": r.duration_ms,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in recordings
        ]
    }


@router.post("/{recording_id}/reset")
async def reset_recording(
    recording_id: str,
    db: Session = Depends(get_db)
):
    """将录音重置为未标注状态"""
    recording = db.query(Recording).filter(Recording.recording_id == recording_id).first()
    
    if not recording:
        raise HTTPException(status_code=404, detail="录音不存在")
    
    recording.status = "pending"
    recording.text_transcript = None
    recording.updated_at = datetime.now()
    
    db.commit()
    db.refresh(recording)
    
    return {
        "success": True,
        "recording_id": recording_id,
        "status": recording.status
    }


@router.get("/stats/summary")
async def get_transcription_stats(
    task_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取标注统计"""
    # 基础查询
    base_query = db.query(Recording)
    if task_id:
        base_query = base_query.filter(Recording.task_id == task_id)
    
    total = base_query.count()
    pending = base_query.filter(Recording.status == "pending").count()
    transcribed = base_query.filter(Recording.status == "transcribed").count()
    reviewed = base_query.filter(Recording.status == "reviewed").count()
    rejected = base_query.filter(Recording.status == "rejected").count()

    # 各数据集类型的数量
    train_count = base_query.filter(Recording.dataset_split == "train").count()
    val_count = base_query.filter(Recording.dataset_split == "val").count()
    eval_count = base_query.filter(Recording.dataset_split == "eval").count()

    # 按语料包分组统计
    all_recordings = base_query.all()
    pack_stats = {}
    for r in all_recordings:
        pack_id_val = r.pack_id or "unknown"
        if pack_id_val not in pack_stats:
            pack_stats[pack_id_val] = {
                "total": 0,
                "pending": 0,
                "transcribed": 0,
                "reviewed": 0,
                "rejected": 0,
                "train": 0,
                "val": 0,
                "eval": 0
            }
        pack_stats[pack_id_val]["total"] += 1
        if r.status == "pending":
            pack_stats[pack_id_val]["pending"] += 1
        elif r.status == "transcribed":
            pack_stats[pack_id_val]["transcribed"] += 1
        elif r.status == "reviewed":
            pack_stats[pack_id_val]["reviewed"] += 1
        elif r.status == "rejected":
            pack_stats[pack_id_val]["rejected"] += 1
        
        if r.dataset_split == "train":
            pack_stats[pack_id_val]["train"] += 1
        elif r.dataset_split == "val":
            pack_stats[pack_id_val]["val"] += 1
        elif r.dataset_split == "eval":
            pack_stats[pack_id_val]["eval"] += 1
    
    return {
        "total": total,
        "pending": pending,
        "transcribed": transcribed,
        "reviewed": reviewed,
        "rejected": rejected,
        "completion_rate": round((transcribed + reviewed) / total * 100, 1) if total > 0 else 0,
        "split": {
            "train": train_count,
            "val": val_count,
            "eval": eval_count,
        },
        "by_pack": pack_stats,
    }


@router.post("/apply_split")
async def apply_dataset_split(
    train_ratio: float = Form(...),
    val_ratio: float = Form(...),
    eval_ratio: float = Form(...),
    pack_id: Optional[str] = Form(None),
    task_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    按比例一键分配训练/验证/评估集。
    - 仅对已标注的数据（status in ['transcribed', 'reviewed']）生效
    - 可选按 pack_id 过滤
    """
    if train_ratio < 0 or val_ratio < 0 or eval_ratio < 0:
        raise HTTPException(status_code=400, detail="比例不能为负数")

    total_ratio = train_ratio + val_ratio + eval_ratio
    if total_ratio <= 0:
        raise HTTPException(status_code=400, detail="比例之和必须大于0")

    # 归一化到 1.0
    train_r = train_ratio / total_ratio
    val_r = val_ratio / total_ratio
    eval_r = eval_ratio / total_ratio

    # 选择可参与分配的数据：已标注/已审核
    base_query = db.query(Recording).filter(Recording.status.in_(["transcribed", "reviewed"]))
    if pack_id:
        base_query = base_query.filter(Recording.pack_id == pack_id)
    if task_id:
        base_query = base_query.filter(Recording.task_id == task_id)

    # 获取所有语料包
    all_recordings = base_query.all()
    if len(all_recordings) == 0:
        raise HTTPException(status_code=400, detail="没有可分配的数据（需要先完成标注）")

    # 按语料包分组
    pack_groups = {}
    for r in all_recordings:
        pack_id_val = r.pack_id or "unknown"
        if pack_id_val not in pack_groups:
            pack_groups[pack_id_val] = []
        pack_groups[pack_id_val].append(r)

    # 统计结果
    total_assigned = {"train": 0, "val": 0, "eval": 0}
    pack_results = {}

    # 对每个语料包分别进行比例分配
    for pack_id_val, recordings in pack_groups.items():
        recordings.sort(key=lambda x: x.created_at)
        n = len(recordings)
        
        # 计算各类型数量
        train_n = int(n * train_r)
        val_n = int(n * val_r)
        eval_n = n - train_n - val_n
        
        # 确保至少有一条数据分配给验证集和评估集（如果有数据的话）
        if n >= 3:
            if val_n == 0 and val_ratio > 0:
                val_n = 1
                train_n = max(1, train_n - 1)
            if eval_n == 0 and eval_ratio > 0:
                eval_n = 1
                train_n = max(1, train_n - 1)

        # 遍历分配
        for idx, r in enumerate(recordings):
            if idx < train_n:
                r.dataset_split = "train"
            elif idx < train_n + val_n:
                r.dataset_split = "val"
            else:
                r.dataset_split = "eval"
            r.updated_at = datetime.now()

        total_assigned["train"] += train_n
        total_assigned["val"] += val_n
        total_assigned["eval"] += eval_n
        pack_results[pack_id_val] = {
            "total": n,
            "train": train_n,
            "val": val_n,
            "eval": eval_n
        }

    db.commit()

    return {
        "success": True,
        "total": len(all_recordings),
        "assigned": total_assigned,
        "by_pack": pack_results
    }


@router.post("/{recording_id}/dataset_split")
async def update_dataset_split(
    recording_id: str,
    dataset_split: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    手动修改单条数据的数据集性质。
    dataset_split: train / val / eval / 空（None）
    """
    if dataset_split not in (None, "", "train", "val", "eval"):
        raise HTTPException(status_code=400, detail="无效的数据集类型")

    recording = db.query(Recording).filter(Recording.recording_id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="录音不存在")

    recording.dataset_split = dataset_split or None
    recording.updated_at = datetime.now()
    db.commit()
    db.refresh(recording)

    return {
        "success": True,
        "recording_id": recording_id,
        "dataset_split": recording.dataset_split,
    }


@router.post("/batch/status")
async def batch_update_status(
    recording_ids: List[str] = Form(...),
    status: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    批量更新录音状态（如：批量设为已标注/已审核等）
    """
    if status not in ["pending", "transcribed", "reviewed", "rejected"]:
        raise HTTPException(status_code=400, detail="无效的状态")

    if not recording_ids:
        raise HTTPException(status_code=400, detail="recording_ids 不能为空")

    recordings = db.query(Recording).filter(Recording.recording_id.in_(recording_ids)).all()
    updated = 0
    for r in recordings:
        r.status = status
        r.updated_at = datetime.now()
        updated += 1

    db.commit()

    return {
        "success": True,
        "updated": updated,
        "status": status,
    }


@router.post("/batch/dataset_split")
async def batch_update_dataset_split(
    recording_ids: List[str] = Form(...),
    dataset_split: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    批量更新录音的数据集性质（train / val / eval / None）
    """
    if dataset_split not in (None, "", "train", "val", "eval"):
        raise HTTPException(status_code=400, detail="无效的数据集类型")

    if not recording_ids:
        raise HTTPException(status_code=400, detail="recording_ids 不能为空")

    recordings = db.query(Recording).filter(Recording.recording_id.in_(recording_ids)).all()
    updated = 0
    for r in recordings:
        r.dataset_split = dataset_split or None
        r.updated_at = datetime.now()
        updated += 1

    db.commit()

    return {
        "success": True,
        "updated": updated,
        "dataset_split": dataset_split or None,
    }



