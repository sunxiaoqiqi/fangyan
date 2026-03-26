@echo off
echo 激活 Conda 环境并启动后端...
echo.

REM 激活环境
call E:\project\31fangyan\Miniconda\Scripts\activate.bat fangyan

REM 进入项目目录
cd /d e:\project\31fangyan\backend

REM 启动后端
echo 启动FastAPI服务...
echo 服务地址: http://localhost:8001
echo API文档: http://localhost:8001/docs
echo.
python main.py

pause
