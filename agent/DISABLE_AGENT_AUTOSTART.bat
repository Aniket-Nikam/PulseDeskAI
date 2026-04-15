@echo off
setlocal
title PulseDesk Agent - Disable Autostart

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS_FILE=%STARTUP_DIR%\PulseDeskAgentAutostart.vbs"

if exist "%VBS_FILE%" (
    del /f /q "%VBS_FILE%" >nul 2>&1
)

if exist "%VBS_FILE%" (
    echo [ERROR] Could not remove startup entry.
    pause
    exit /b 1
)

echo [OK] Agent autostart disabled.
exit /b 0
