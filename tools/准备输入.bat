@echo off
chcp 936 >nul
title 准备一次运行的输入
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0准备输入.ps1"
