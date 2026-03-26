@echo off
chcp 65001 >nul
echo ====================================================
echo    Whisper HTTP API 服务器启动器
echo ====================================================
echo.
echo 正在检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python
    pause
    exit /b 1
)

echo [OK] Python已找到
echo.
echo 正在检查依赖...

pip show flask >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装Flask...
    pip install flask
)

pip show faster-whisper >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装faster-whisper...
    pip install faster-whisper
)

echo [OK] 所有依赖已安装
echo.
echo ====================================================
echo.
echo 启动Whisper服务器...
echo.
echo 服务器地址: http://localhost:5000
echo.
echo 按 Ctrl+C 停止服务器
echo ====================================================
echo.

python whisper_server.py

pause
