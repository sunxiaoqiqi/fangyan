@echo off
echo 修复 Vite 依赖锁定问题
echo.

REM 关闭可能运行的 Node 进程
echo 正在关闭相关进程...
taskkill /F /IM node.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM 删除 Vite 缓存目录
echo 正在清理 Vite 缓存...
if exist "node_modules\.vite" (
    rmdir /s /q "node_modules\.vite"
    echo 已删除 .vite 缓存目录
)

REM 如果问题持续，可以删除整个 node_modules（可选）
echo.
echo 如果问题仍然存在，请运行以下命令：
echo   rmdir /s /q node_modules
echo   npm install
echo.

echo 清理完成！现在可以重新运行 npm run dev
pause



