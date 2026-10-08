@echo off
chcp 936 >nul
title HR 招聘助手 · 本地界面
cd /d "%~dp0"
echo.
echo   HR 招聘助手 · 本地界面
echo   ------------------------------------------------
echo   启动后浏览器访问：http://127.0.0.1:8000
echo   停止服务：按 Ctrl+C
echo.
echo   本界面只用 Python 标准库，不需要装任何第三方包，
echo   所以这台机器上 7 个 Python 里任何一个都能跑。
echo.
where python >nul 2>nul
if %errorlevel%==0 (
  python server.py %*
) else (
  echo   [提示] 找不到 python 命令，改用 py 启动器...
  py server.py %*
)
echo.
pause
