@echo off
title PulseDesk Agent — Install
color 0A
echo.
echo ================================================
echo   PulseDesk Agent Installer
echo ================================================
echo.

set AGENT=%~dp0

REM ─── Find Python ──────────────────────────────────────────────────────────
set PY=
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" ( set PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe && goto :py_found )
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" ( set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe && goto :py_found )
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" ( set PY=%LOCALAPPDATA%\Programs\Python\Python310\python.exe && goto :py_found )
if exist "C:\Program Files\Python311\python.exe" ( set "PY=C:\Program Files\Python311\python.exe" && goto :py_found )
if exist "C:\Python311\python.exe" ( set PY=C:\Python311\python.exe && goto :py_found )
where py >nul 2>nul && set PY=py && goto :py_found

echo [ERROR] Python not found.
echo Install from: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
pause & exit /b 1

:py_found
echo [OK] Python: %PY%
echo %PY%> "%AGENT%python_path.txt"
echo.

echo Installing packages...
"%PY%" -m pip install --upgrade pip --quiet 2>nul
"%PY%" -m pip install psutil requests python-dotenv schedule --quiet
if %errorlevel% equ 0 (echo [OK] Core packages) else (echo [WARN] Some packages failed)

"%PY%" -m pip install pynput --quiet
if %errorlevel% equ 0 (echo [OK] pynput - keyboard/mouse tracking) else (echo [WARN] pynput skipped)

"%PY%" -m pip install mss --quiet
if %errorlevel% equ 0 (echo [OK] mss - screenshots enabled) else (echo [WARN] mss skipped - screenshots disabled)

echo.
echo ================================================
echo   Installation complete!
echo   Run START_AGENT.bat to begin monitoring.
echo ================================================
pause
