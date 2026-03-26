"""
数据库迁移脚本：为现有录音记录添加task_id字段
"""
from database import engine, get_db, Task
from sqlalchemy import text
import uuid

def migrate_add_task_id():
    """为recordings表添加task_id字段"""
    print("[MIGRATION] 开始添加task_id字段...")
    
    try:
        with engine.connect() as conn:
            # 检查字段是否已存在
            check_sql = text("""
                SELECT COUNT(*) as count 
                FROM pragma_table_info('recordings') 
                WHERE name = 'task_id'
            """)
            result = conn.execute(check_sql)
            field_exists = result.fetchone()[0] > 0
            
            if field_exists:
                print("[MIGRATION] task_id字段已存在，跳过添加")
            else:
                # 添加task_id字段
                alter_sql = text("ALTER TABLE recordings ADD COLUMN task_id VARCHAR")
                conn.execute(alter_sql)
                conn.commit()
                print("[MIGRATION] task_id字段添加成功")
                
    except Exception as e:
        print(f"[ERROR] 添加task_id字段失败: {str(e)}")
        raise

def migrate_update_task_id():
    """为现有录音记录更新task_id为默认任务"""
    print("[MIGRATION] 开始更新现有录音记录的task_id...")
    
    db = next(get_db())
    try:
        # 获取默认任务（辰溪话）
        default_task = db.query(Task).filter(Task.task_name == "辰溪话").first()
        
        if not default_task:
            print("[WARN] 未找到默认任务'辰溪话'，创建新任务...")
            default_task = Task(
                task_id=str(uuid.uuid4()),
                task_name="辰溪话",
                description="辰溪话语音采集任务",
                is_default=True
            )
            db.add(default_task)
            db.commit()
            print(f"[MIGRATION] 已创建默认任务: {default_task.task_id}")
        
        # 更新所有没有task_id的记录
        update_sql = text("""
            UPDATE recordings 
            SET task_id = :task_id 
            WHERE task_id IS NULL OR task_id = ''
        """)
        
        result = db.execute(update_sql, {"task_id": default_task.task_id})
        db.commit()
        
        print(f"[MIGRATION] 已更新 {result.rowcount} 条录音记录的task_id为: {default_task.task_id}")
        
        # 统计更新结果
        count_sql = text("""
            SELECT COUNT(*) as count 
            FROM recordings 
            WHERE task_id = :task_id
        """)
        result = db.execute(count_sql, {"task_id": default_task.task_id})
        count = result.fetchone()[0]
        print(f"[MIGRATION] 当前任务'{default_task.task_name}'共有 {count} 条录音记录")
        
    except Exception as e:
        print(f"[ERROR] 更新task_id失败: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def main():
    """执行迁移"""
    print("=" * 50)
    print("数据库迁移：添加task_id字段")
    print("=" * 50)
    
    try:
        # 步骤1：添加task_id字段
        migrate_add_task_id()
        
        # 步骤2：更新现有记录的task_id
        migrate_update_task_id()
        
        print("=" * 50)
        print("数据库迁移完成！")
        print("=" * 50)
        
    except Exception as e:
        print("=" * 50)
        print(f"数据库迁移失败: {str(e)}")
        print("=" * 50)
        raise

if __name__ == "__main__":
    main()
