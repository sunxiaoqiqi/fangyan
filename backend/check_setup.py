"""
检查后端环境配置
"""
import os
import sys
from pathlib import Path

# 设置控制台编码为UTF-8（Windows）
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

BASE_DIR = Path(__file__).parent
CSV_FILE = BASE_DIR.parent / "辰溪话_朗读语料包v1_480句.csv"

print("=" * 50)
print("辰溪话语音采集系统 - 环境检查")
print("=" * 50)

# 检查CSV文件
print(f"\n1. 检查CSV文件...")
print(f"   预期路径: {CSV_FILE}")
print(f"   绝对路径: {CSV_FILE.absolute()}")

if CSV_FILE.exists():
    print(f"   [OK] CSV文件存在")
    file_size = CSV_FILE.stat().st_size
    print(f"   文件大小: {file_size} 字节")
    
    # 尝试读取第一行
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            print(f"   第一行: {first_line[:50]}...")
    except Exception as e:
        print(f"   [ERROR] 读取文件失败: {e}")
else:
    print(f"   [ERROR] CSV文件不存在！")
    print(f"   请确保CSV文件位于项目根目录: {BASE_DIR.parent}")
    print(f"   文件名应为: 辰溪话_朗读语料包v1_480句.csv")

# 检查recordings目录
print(f"\n2. 检查录音存储目录...")
RECORDINGS_DIR = BASE_DIR / "recordings"
print(f"   路径: {RECORDINGS_DIR}")

if RECORDINGS_DIR.exists():
    print(f"   [OK] 目录存在")
    file_count = len(list(RECORDINGS_DIR.glob("*.webm"))) + len(list(RECORDINGS_DIR.glob("*.wav")))
    print(f"   已有录音文件: {file_count} 个")
else:
    print(f"   [WARN] 目录不存在，将在首次运行时自动创建")

# 检查Python依赖
print(f"\n3. 检查Python依赖...")
try:
    import fastapi
    print(f"   [OK] fastapi: {fastapi.__version__}")
except ImportError:
    print(f"   [ERROR] fastapi 未安装")

try:
    import uvicorn
    print(f"   [OK] uvicorn: {uvicorn.__version__}")
except ImportError:
    print(f"   [ERROR] uvicorn 未安装")

try:
    import aiofiles
    print(f"   [OK] aiofiles 已安装")
except ImportError:
    print(f"   [ERROR] aiofiles 未安装")

# 总结
print(f"\n" + "=" * 50)
if CSV_FILE.exists():
    print("[SUCCESS] 环境检查通过，可以启动后端服务")
    print(f"\n启动命令:")
    print(f"   cd backend")
    print(f"   python main.py")
else:
    print("[FAILED] 环境检查未通过，请先解决上述问题")
print("=" * 50)

