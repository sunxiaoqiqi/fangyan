"""
初始化空白数据库
在新机器上克隆仓库后运行此脚本创建空白数据库
"""

import sqlite3
from pathlib import Path

def init_empty_database():
    """创建空白数据库"""
    db_path = Path(__file__).parent / "voice_collector.db"
    
    # 如果数据库已存在，先删除
    if db_path.exists():
        print(f"数据库已存在: {db_path}")
        response = input("是否删除并创建新数据库? (y/n): ")
        if response.lower() != 'y':
            print("取消操作")
            return
        db_path.unlink()
        print("已删除旧数据库")
    
    # 创建新数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建 users 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 创建 sentences 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sentences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sentence_text TEXT NOT NULL,
            sentence_pinyin TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 创建 recordings 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sentence_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            duration REAL,
            quality_score REAL,
            is_valid INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (sentence_id) REFERENCES sentences(id)
        )
    """)
    
    # 创建 training_logs 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            base_model TEXT,
            epochs INTEGER,
            batch_size INTEGER,
            learning_rate REAL,
            train_samples INTEGER,
            eval_samples INTEGER,
            loss REAL,
            status TEXT,
            model_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    
    print(f"✅ 空白数据库创建成功: {db_path}")
    print("表结构：users, sentences, recordings, training_logs")

def add_sample_data():
    """添加示例数据（可选）"""
    db_path = Path(__file__).parent / "voice_collector.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 添加示例用户
    cursor.execute("""
        INSERT OR IGNORE INTO users (username, password) VALUES 
        ('admin', 'admin123'),
        ('test', 'test123')
    """)
    
    # 添加示例句子
    sample_sentences = [
        ('今天天气真好', 'jīn tiān tiān qì zhēn hǎo'),
        ('我是常德人', 'wǒ shì cháng dé rén'),
        ('吃了饭没有', 'chī le fàn méi yǒu'),
    ]
    
    for text, pinyin in sample_sentences:
        cursor.execute("""
            INSERT OR IGNORE INTO sentences (sentence_text, sentence_pinyin) 
            VALUES (?, ?)
        """, (text, pinyin))
    
    conn.commit()
    conn.close()
    
    print("✅ 示例数据添加成功")

if __name__ == "__main__":
    print("=" * 50)
    print("空白数据库初始化脚本")
    print("=" * 50)
    
    init_empty_database()
    
    # 询问是否添加示例数据
    response = input("\n是否添加示例数据? (y/n): ")
    if response.lower() == 'y':
        add_sample_data()
    
    print("\n" + "=" * 50)
    print("初始化完成！")
    print("=" * 50)
