"""
检查数据库中的录音记录和任务信息
"""
from database import engine, get_db, Recording, Task
from sqlalchemy import text
import sys

def check_database():
    """检查数据库中的数据"""
    print("=" * 60)
    print("数据库检查")
    print("=" * 60)
    
    db = next(get_db())
    try:
        # 1. 检查任务列表
        print("\n【任务列表】")
        tasks = db.query(Task).all()
        for task in tasks:
            print(f"  - 任务ID: {task.task_id}")
            print(f"    任务名称: {task.task_name}")
            print(f"    是否默认: {task.is_default}")
            print()
        
        # 2. 检查录音记录总数
        print("\n【录音记录总数】")
        total_recordings = db.query(Recording).count()
        print(f"  总计: {total_recordings} 条")
        
        # 3. 检查task_id字段
        print("\n【task_id字段检查】")
        with engine.connect() as conn:
            # 检查task_id字段是否存在
            check_sql = text("""
                SELECT COUNT(*) as count 
                FROM pragma_table_info('recordings') 
                WHERE name = 'task_id'
            """)
            result = conn.execute(check_sql)
            field_exists = result.fetchone()[0] > 0
            
            if field_exists:
                print("  ✓ task_id字段存在")
                
                # 检查task_id为NULL的记录数
                null_count_sql = text("SELECT COUNT(*) FROM recordings WHERE task_id IS NULL OR task_id = ''")
                result = conn.execute(null_count_sql)
                null_count = result.fetchone()[0]
                print(f"  task_id为空的记录数: {null_count}")
                
                # 检查各个task_id的记录数
                count_by_task_sql = text("SELECT task_id, COUNT(*) as count FROM recordings GROUP BY task_id")
                result = conn.execute(count_by_task_sql)
                print("\n  按task_id统计:")
                for row in result:
                    task_id = row[0] if row[0] else "NULL"
                    count = row[1]
                    print(f"    {task_id}: {count}条")
            else:
                print("  ✗ task_id字段不存在")
        
        # 4. 检查各个任务的录音记录
        print("\n【各任务录音记录】")
        for task in tasks:
            recordings = db.query(Recording).filter(Recording.task_id == task.task_id).all()
            print(f"\n  任务: {task.task_name} (ID: {task.task_id})")
            print(f"  录音记录数: {len(recordings)}")
            
            if recordings:
                # 按status统计
                status_count = {}
                for r in recordings:
                    status = r.status
                    status_count[status] = status_count.get(status, 0) + 1
                print(f"  按状态统计: {status_count}")
                
                # 显示前5条记录
                print(f"  前5条记录:")
                for i, r in enumerate(recordings[:5], 1):
                    print(f"    {i}. sentence_id={r.sentence_id}, status={r.status}, pack_id={r.pack_id}")
        
        # 5. 检查没有task_id的记录
        print("\n【没有task_id的记录】")
        null_task_recordings = db.query(Recording).filter(
            (Recording.task_id == None) | (Recording.task_id == '')
        ).all()
        print(f"  数量: {len(null_task_recordings)}")
        if null_task_recordings:
            print(f"  前5条记录:")
            for i, r in enumerate(null_task_recordings[:5], 1):
                print(f"    {i}. sentence_id={r.sentence_id}, status={r.status}, pack_id={r.pack_id}")
        
    except Exception as e:
        print(f"\n[ERROR] 检查失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
    
    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)

if __name__ == "__main__":
    check_database()
