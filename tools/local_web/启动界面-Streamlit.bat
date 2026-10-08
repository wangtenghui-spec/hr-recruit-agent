@echo off
set "LOGFILE=%~dp0启动日志.txt"
> "%LOGFILE%" echo [00] 脚本开始执行  %DATE% %TIME%
chcp 936 >nul
title HR 招聘助手 Streamlit 界面
cd /d "%~dp0"

>>"%LOGFILE%" echo [01] 工作目录=%CD%
>>"%LOGFILE%" echo [02] 脚本=%~f0

echo.
echo   HR 招聘助手 Streamlit 界面
echo   ================================================
echo   正在查找装了 streamlit 的 Python...
echo.
>>"%LOGFILE%" echo [03] 开始探测解释器

set "PYEXE="
set "PY_A=C:\Users\王腾辉\PycharmProjects\PythonProject\.venv\Scripts\python.exe"
set "PY_B=C:\Project\.venv_pd3\Scripts\python.exe"

if exist "%PY_A%" (
  >>"%LOGFILE%" echo [04] 存在，测试 import streamlit: %PY_A%
  "%PY_A%" -c "import streamlit" >>"%LOGFILE%" 2>&1
  if not errorlevel 1 set "PYEXE=%PY_A%"
) else (
  >>"%LOGFILE%" echo [04] 不存在: %PY_A%
)

if not defined PYEXE if exist "%PY_B%" (
  >>"%LOGFILE%" echo [05] 存在，测试 import streamlit: %PY_B%
  "%PY_B%" -c "import streamlit" >>"%LOGFILE%" 2>&1
  if not errorlevel 1 set "PYEXE=%PY_B%"
)

if not defined PYEXE goto :nopy

>>"%LOGFILE%" echo [06] 选定解释器: %PYEXE%
echo   找到：%PYEXE%
echo.
echo   浏览器会自动打开 http://localhost:8001
echo   停止服务：在这个窗口按 Ctrl+C
echo.
>>"%LOGFILE%" echo [07] 开始执行 streamlit run
"%PYEXE%" -m streamlit run app_streamlit.py --server.port 8001
set "RC=%ERRORLEVEL%"
>>"%LOGFILE%" echo [08] streamlit 已退出，退出码 %RC%

echo.
echo   ---- Streamlit 已退出（退出码 %RC%）----
echo   日志：%LOGFILE%
echo.
type "%LOGFILE%"
goto :hold

:nopy
>>"%LOGFILE%" echo [XX] 两个已知解释器都没找到，或者里面没装 streamlit
echo   [x] 没找到装了 streamlit 的解释器。
echo.
echo   已知的两个位置：
echo     %PY_A%
echo     %PY_B%
echo.
echo   可以改用标准库版：双击 启动界面.bat
echo   或者自己装一个：python -m pip install streamlit
echo.

:hold
>>"%LOGFILE%" echo [09] 已到达等待按键，窗口不会自动关闭
echo.
echo   按任意键关闭本窗口。
echo   日志已写入：%LOGFILE%
pause >nul
exit /b
