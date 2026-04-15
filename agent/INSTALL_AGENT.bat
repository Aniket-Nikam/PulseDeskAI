@echo off
title PulseDesk Agent — Install

set AGENT=%~dp0
cd /d "%AGENT%"

echo ================================================
echo   PulseDesk Agent Installer
echo ================================================
echo.

REM 1. Find Python
set PY=
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PY=python
    goto :py_found
)
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PY=py
    goto :py_found
)

echo [ERROR] Python not found on your system PATH!
echo Install from: https://www.python.org/downloads/
echo Make sure to check "Add python.exe to PATH" during installation.
pause
exit /b 1

:py_found
echo [OK] Python found: %PY%
echo.

REM 2. Create Virtual Environment
echo Creating virtual environment...
%PY% -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment!
    pause
    exit /b 1
)
echo [OK] Virtual environment created.

REM 3. Install packages
echo Installing dependencies...
call "venv\Scripts\activate.bat"
python -m pip install --upgrade pip setuptools wheel --quiet

REM Install core requirements
python -m pip install -r requirements.txt --quiet
if %errorlevel% equ 0 (
echo [OK] Core packages installed.
) else (
    echo [ERROR] Failed to install core packages!
    pause
    exit /b 1
)

REM All capture modules are now in requirements.txt

deactivate

echo.
echo Enabling agent auto-start on Windows login...
call "%AGENT%ENABLE_AGENT_AUTOSTART.bat" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Auto-start enabled.
) else (
    echo [WARN] Could not enable auto-start automatically.
    echo Run ENABLE_AGENT_AUTOSTART.bat manually.
)

echo Starting agent in background now...
call "%AGENT%START_AGENT_SILENT.bat" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Agent started in background.
) else (
    echo [WARN] Agent did not start now.
    echo You can run START_AGENT.bat manually.
)

echo.
echo ================================================
echo   Installation complete!
echo   Auto-start is enabled.
echo   The agent will start automatically at next login.
echo   Run START_AGENT.bat now only if you want to start immediately.
echo ================================================
pause
