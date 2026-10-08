@echo off
chcp 936 >nul
title HR 招聘助手 · 演示模式
cd /d "%~dp0"
echo.
echo   演示模式：不调用 Dify，直接返回一份样例报告
echo   用来演示界面长什么样、报告怎么呈现
echo.
echo   浏览器访问：http://127.0.0.1:8000
echo.
where python >nul 2>nul
if %errorlevel%==0 (
  python server.py --mock %*
) else (
  echo   [提示] 找不到 python 命令，改用 py 启动器...
  py server.py --mock %*
)
echo.
pause
