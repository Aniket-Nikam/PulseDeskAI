@echo off
setlocal
title PulseDesk Agent - Enable Autostart

set "AGENT=%~dp0"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS_FILE=%STARTUP_DIR%\PulseDeskAgentAutostart.vbs"

if not exist "%AGENT%START_AGENT_SILENT.bat" (
    echo [ERROR] START_AGENT_SILENT.bat not found.
    pause
    exit /b 1
)

if not exist "%STARTUP_DIR%" (
    mkdir "%STARTUP_DIR%" >nul 2>&1
)

(
    echo Set WshShell = CreateObject("WScript.Shell"^)
    echo WshShell.Run Chr(34^) ^& "%AGENT%START_AGENT_SILENT.bat" ^& Chr(34^), 0, False
    echo Set WshShell = Nothing
) > "%VBS_FILE%"

if exist "%VBS_FILE%" (
    echo [OK] Agent autostart enabled.
    echo Startup file: %VBS_FILE%
    exit /b 0
)

echo [ERROR] Failed to enable autostart.
pause
exit /b 1
