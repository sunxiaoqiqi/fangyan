@echo off
echo 启动辰溪话语音采集系统 - 前端服务
echo.

REM 检查Node环境
node --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Node.js，请先安装Node.js
    pause
    exit /b 1
)

REM 检查依赖
if not exist "node_modules" (
    echo 首次运行，正在安装依赖...
    call npm install
    if errorlevel 1 (
        echo 错误: 依赖安装失败
        pause
        exit /b 1
    )
)

REM 启动开发服务器
echo.
echo 启动Vue开发服务器...
echo 前端地址: http://localhost:3000
echo.
call npm run dev

pause



