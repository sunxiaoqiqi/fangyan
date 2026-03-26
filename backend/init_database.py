"""
初始化数据库脚本
"""
from database import init_db, engine, Base
from database import Speaker, Recording, DatasetSnapshot, ModelVersion

def main():
    print("=" * 50)
    print("初始化数据库...")
    print("=" * 50)
    
    # 创建所有表
    init_db()
    
    print("\n数据库表创建完成！")
    print("\n表列表:")
    print("  - speakers (说话人)")
    print("  - recordings (录音)")
    print("  - dataset_snapshots (数据集快照)")
    print("  - model_versions (模型版本)")

if __name__ == "__main__":
    main()



