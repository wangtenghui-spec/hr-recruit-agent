@echo off
chcp 936 >nul
title 双击自检
cd /d "%~dp0"

set "T=%~dp0自检结果.txt"
> "%T%" echo 双击执行成功！
>>"%T%" echo 时间 : %DATE% %TIME%
>>"%T%" echo 脚本 : %~f0
>>"%T%" echo 目录 : %CD%

echo.
echo   ┌──────────────────────────────────────────────┐
echo   │  双击自检：这个窗口能正常显示，就说明       │
echo   │  本机双击 .bat 是好的。                      │
echo   └──────────────────────────────────────────────┘
echo.
echo   已写入：%T%
echo.
echo   如果这个窗口一闪就没了、而且「自检结果.txt」也没生成，
echo   那就是系统或杀软拦截了 .bat 的执行，不是脚本本身的问题。
echo.
echo   按任意键关闭本窗口。
pause >nul
exit /b
