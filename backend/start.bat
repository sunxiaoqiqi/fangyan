@echo off
echo 启动辰溪话语音采集系统 - 后端服务
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查依赖
if not exist "requirements.txt" (
    echo 错误: 未找到requirements.txt
    pause
    exit /b 1
)

REM 安装依赖（如果需要）
echo 检查依赖...
pip install -q -r requirements.txt

REM 启动服务
echo.
echo 启动FastAPI服务...
echo 服务地址: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo.
python main.py

pause



