@echo off
title PulseDesk Monitor

set AGENT=%~dp0
set PY=
if exist "%AGENT%python_path.txt" ( set /p PY=<"%AGENT%python_path.txt" )
if "%PY%"=="" (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    ) else ( set PY=py )
)

if not exist "%AGENT%.env" (
    echo [ERROR] .env file missing.
    echo Download the agent again from the join portal.
    pause & exit /b 1
)

echo Starting PulseDesk monitoring agent...
echo Press Ctrl+C to stop.
echo.
"%PY%" "%AGENT%agent.py"

echo.
echo Agent stopped.
pause
