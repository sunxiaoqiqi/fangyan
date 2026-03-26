"""
更新数据库结构，添加新字段
"""
from pathlib import Path
import sqlite3

# 获取数据库文件路径
BASE_DIR = Path(__file__).parent
DATABASE_PATH = BASE_DIR / 'voice_collector.db'

# 连接到SQLite数据库
conn = sqlite3.connect(DATABASE_PATH)
cursor = conn.cursor()

# 检查in_evaluation_set字段是否存在
cursor.execute("PRAGMA table_info(recordings)")
columns = [column[1] for column in cursor.fetchall()]

if 'in_evaluation_set' not in columns:
    # 添加in_evaluation_set字段
    cursor.execute("ALTER TABLE recordings ADD COLUMN in_evaluation_set INTEGER DEFAULT 0")
    print("添加了in_evaluation_set字段")
else:
    print("in_evaluation_set字段已存在")

# 提交更改并关闭连接
conn.commit()
conn.close()

print("数据库更新完成")