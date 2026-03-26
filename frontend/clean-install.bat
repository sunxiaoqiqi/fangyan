@echo off
echo 完全清理并重新安装依赖
echo.

REM 关闭 Node 进程
echo 正在关闭 Node 进程...
taskkill /F /IM node.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM 删除 node_modules
echo 正在删除 node_modules...
if exist "node_modules" (
    rmdir /s /q "node_modules"
    echo node_modules 已删除
)

REM 删除 package-lock.json（可选）
if exist "package-lock.json" (
    del /q "package-lock.json"
    echo package-lock.json 已删除
)

REM 清理 Vite 缓存
if exist "node_modules\.vite" (
    rmdir /s /q "node_modules\.vite"
)

REM 重新安装
echo.
echo 正在重新安装依赖...
call npm install

if errorlevel 1 (
    echo.
    echo 安装失败！请检查网络连接或使用国内镜像：
    echo   npm install --registry=https://registry.npmmirror.com
    pause
    exit /b 1
)

echo.
echo 安装完成！现在可以运行 npm run dev
pause



