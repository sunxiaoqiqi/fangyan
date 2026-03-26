"""
数据库模型和连接
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pathlib import Path
import os

BASE_DIR = Path(__file__).parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'voice_collector.db'}"

# 创建数据库引擎
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Speaker(Base):
    """说话人表"""
    __tablename__ = "speakers"
    
    speaker_id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    device_info = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON格式的额外信息


class Recording(Base):
    """录音表"""
    __tablename__ = "recordings"
    
    recording_id = Column(String, primary_key=True, index=True)
    speaker_id = Column(String, index=True)
    task_id = Column(String, index=True)  # 任务ID（如：辰溪话）
    pack_id = Column(String, index=True)
    sentence_id = Column(String, index=True)
    
    # 文件路径
    audio_path_webm = Column(String)  # 原始webm文件
    audio_path_wav = Column(String, nullable=True)  # 转换后的wav文件
    
    # 元数据
    text_target = Column(Text)  # 目标文本（提示文本）
    text_transcript = Column(Text, nullable=True)  # 转写文本（标注后）
    duration_ms = Column(Integer, nullable=True)
    file_size = Column(Integer, nullable=True)
    
    # 状态
    status = Column(String, default="pending")  # pending, transcribed, reviewed, rejected
    quality_score = Column(Float, nullable=True)
    
    # 标注相关
    transcribed_by = Column(String, nullable=True)  # 标注员ID
    reviewed_by = Column(String, nullable=True)  # 审核员ID
    notes = Column(Text, nullable=True)  # 备注
    
    # 数据集划分：train / val / eval / None
    dataset_split = Column(String, nullable=True, index=True)
    
    # 是否用于评估
    in_evaluation_set = Column(Boolean, default=False, index=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DatasetSnapshot(Base):
    """数据集快照表"""
    __tablename__ = "dataset_snapshots"
    
    snapshot_id = Column(String, primary_key=True)
    snapshot_name = Column(String, unique=True)
    description = Column(Text, nullable=True)
    recording_count = Column(Integer, default=0)
    total_duration_seconds = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    metadata_json = Column(Text, nullable=True)


class ModelVersion(Base):
    """模型版本表"""
    __tablename__ = "model_versions"
    
    version_id = Column(String, primary_key=True)
    version_name = Column(String, unique=True)
    snapshot_id = Column(String, nullable=True)  # 关联的数据集快照
    model_path = Column(String, nullable=True)
    config_json = Column(Text, nullable=True)
    
    # 评测指标
    cer = Column(Float, nullable=True)  # 字符错误率
    wer = Column(Float, nullable=True)  # 词错误率
    
    # 状态
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    user_id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)  # 加密存储的密码
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Task(Base):
    """任务表"""
    __tablename__ = "tasks"
    
    task_id = Column(String, primary_key=True, index=True)
    task_name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class FineTuneHistory(Base):
    """微调记录表"""
    __tablename__ = "fine_tune_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, index=True)  # 微调任务ID
    task_name = Column(String, nullable=True)  # 微调事件名称
    
    # 状态
    status = Column(String, default="running")  # running, completed, failed
    error_message = Column(Text, nullable=True)
    
    # 训练参数
    params_json = Column(Text, nullable=True)  # JSON格式的训练参数
    data_count = Column(Integer, default=0)  # 数据量
    
    # 训练结果
    total_epochs = Column(Integer, default=0)
    best_epoch = Column(Integer, default=0)
    best_val_loss = Column(Float, nullable=True)
    best_wer = Column(Float, nullable=True)
    best_cer = Column(Float, nullable=True)  # 最佳CER
    training_time = Column(Integer, default=0)  # 训练时间（秒）
    stop_reason = Column(String, nullable=True)  # 停止原因：正常结束/早停
    
    # 模型路径
    model_path = Column(String, nullable=True)
    
    # 训练报告（JSON格式）
    epoch_reports_json = Column(Text, nullable=True)
    test_wer = Column(Float, nullable=True)  # 评估集WER
    test_wer_details_json = Column(Text, nullable=True)  # 评估集WER详细信息
    test_cer = Column(Float, nullable=True)  # 评估集CER
    test_cer_details_json = Column(Text, nullable=True)  # 评估集CER详细信息
    test_pack_stats_json = Column(Text, nullable=True)  # 按语料包统计
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)
    print(f"[DB] 数据库初始化完成: {DATABASE_URL}")
    
    # 初始化默认数据
    db = SessionLocal()
    try:
        # 检查是否已有管理员用户
        admin_user = db.query(User).filter(User.username == "1").first()
        if not admin_user:
            # 创建管理员用户，密码为123（实际应用中应该使用加密密码）
            import uuid
            admin_user = User(
                user_id=str(uuid.uuid4()),
                username="1",
                password="123",  # 实际应用中应该使用bcrypt加密
                is_admin=True
            )
            db.add(admin_user)
            print("[DB] 已创建默认管理员用户: username=1, password=123")
        
        # 检查是否已有默认任务
        default_task = db.query(Task).filter(Task.task_name == "辰溪话").first()
        if not default_task:
            # 创建默认任务
            default_task = Task(
                task_id=str(uuid.uuid4()),
                task_name="辰溪话",
                description="辰溪话语音采集任务",
                is_default=True
            )
            db.add(default_task)
            print("[DB] 已创建默认任务: 辰溪话")
        
        db.commit()
    except Exception as e:
        print(f"[DB] 初始化默认数据失败: {str(e)}")
        db.rollback()
    finally:
        db.close()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



