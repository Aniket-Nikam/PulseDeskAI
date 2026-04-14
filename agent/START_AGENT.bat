@echo off
title PulseDesk Agent
color 0F

set AGENT=%~dp0
cd /d "%AGENT%"

if not exist "%AGENT%venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. 
    echo Please run INSTALL_AGENT.bat first!
    pause
    exit /b 1
)

if not exist "%AGENT%.env" (
    echo [ERROR] .env file missing.
    echo Download the agent package again from the join portal to get the pre-configured .env, or use the join link.
    pause
    exit /b 1
)

echo Starting PulseDesk monitoring agent...
echo Press Ctrl+C to stop.
echo ========================================
echo.

"venv\Scripts\python.exe" agent.py

echo.
echo ========================================
echo Agent stopped.
pause
