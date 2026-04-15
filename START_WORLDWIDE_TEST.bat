@echo off
setlocal enabledelayedexpansion
title PulseDesk v5 - Worldwide Test Launcher
color 0A
cls

if /I "%~1"=="--help" goto :help
if /I "%~1"=="/?" goto :help

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "LOG_DIR=%ROOT%logs"
set "BACKEND_LOG=%LOG_DIR%\backend.log"
set "FRONTEND_LOG=%LOG_DIR%\frontend.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ================================================
echo   PulseDesk Worldwide Test Launcher
echo ================================================
echo.

if not exist "%BACKEND%\venv\Scripts\python.exe" (
    echo [ERROR] Backend virtual environment not found.
    echo Run SETUP_WINDOWS.bat first.
    echo.
    pause
    exit /b 1
)

if not exist "%FRONTEND%\node_modules" (
    echo [ERROR] Frontend dependencies not found.
    echo Run SETUP_WINDOWS.bat first.
    echo.
    pause
    exit /b 1
)

if not exist "%BACKEND%\.env" (
    echo [ERROR] Missing backend\.env file.
    echo Run SETUP_WINDOWS.bat first.
    echo.
    pause
    exit /b 1
)

set "NGROK_CMD=ngrok"
where ngrok >nul 2>nul
if errorlevel 1 (
    set "NGROK_WINGET=%LOCALAPPDATA%\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"
    if exist "%NGROK_WINGET%" (
        set "NGROK_CMD=%NGROK_WINGET%"
    ) else (
        echo [ERROR] ngrok is not installed or not in PATH.
        echo Install with:
        echo   winget install -e --id Ngrok.Ngrok
        echo Then configure:
        echo   ngrok config add-authtoken YOUR_TOKEN
        echo.
        pause
        exit /b 1
    )
)

echo Checking port availability...
call :kill_port 8000
call :kill_port 5173
call :kill_port 4040
echo.

echo [1/3] Starting Backend on 0.0.0.0:8000...
start "PulseDesk Backend" cmd /k "cd /d "%BACKEND%" && "%BACKEND%\venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info"

echo Waiting for backend health...
set "HEALTH_OK="
for /L %%I in (1,1,15) do (
    for /f %%A in ('powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri ''http://127.0.0.1:8000/api/health'' -TimeoutSec 2; if ($r.StatusCode -eq 200) { ''ok'' } } catch { ''wait'' }"') do (
        if "%%A"=="ok" set "HEALTH_OK=1"
    )
    if defined HEALTH_OK goto :backend_ready
    timeout /t 1 /nobreak >nul
)

:backend_ready
if defined HEALTH_OK (
    echo [OK] Backend is healthy.
) else (
    echo [WARN] Backend health check timed out. Continuing...
)
echo.

echo [2/3] Starting Frontend on 0.0.0.0:5173...
start "PulseDesk Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev:lan"
timeout /t 4 /nobreak >nul
echo.

echo [3/3] Starting ngrok tunnel for port 5173...
start "PulseDesk Tunnel (ngrok)" cmd /k ""%NGROK_CMD%" http 5173"
timeout /t 5 /nobreak >nul

set "PUBLIC_URL="
for /f "delims=" %%A in ('powershell -NoProfile -Command "try { $t = Invoke-RestMethod -Uri ''http://127.0.0.1:4040/api/tunnels'' -TimeoutSec 3; ($t.tunnels | Where-Object { $_.proto -eq ''https'' } | Select-Object -First 1 -ExpandProperty public_url) } catch { '''' }"') do (
    if not "%%A"=="" set "PUBLIC_URL=%%A"
)

echo.
echo ================================================
echo   PulseDesk is running for internet testing
echo ================================================
echo Local dashboard:  http://localhost:5173
echo Local API docs:   http://localhost:8000/api/docs
if defined PUBLIC_URL (
    echo Public URL:      !PUBLIC_URL!
) else (
    echo Public URL:      Not detected yet. Check ngrok window.
)
echo.
echo IMPORTANT:
echo 1. Use the same PUBLIC URL in Enroll Device ^> Server URL.
echo 2. Generate a NEW join code each time ngrok URL changes.
echo 3. Keep Backend, Frontend, and ngrok windows running.
echo ================================================
echo.

if defined PUBLIC_URL (
    start "" "!PUBLIC_URL!"
) else (
    start "" "http://localhost:5173"
)

pause
exit /b 0

:kill_port
set "PORT=%~1"
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1
if errorlevel 1 exit /b 0
echo [WARN] Port %PORT% is already in use. Terminating existing process...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do (
    taskkill /PID %%P /F >nul 2>&1
)
timeout /t 1 /nobreak >nul
exit /b 0

:help
echo Usage:
echo   START_WORLDWIDE_TEST.bat
echo.
echo What it does:
echo 1. Starts backend on 0.0.0.0:8000
echo 2. Starts frontend in LAN mode on 0.0.0.0:5173
echo 3. Starts ngrok tunnel for 5173
echo.
echo Requirement:
echo - ngrok installed and authenticated
exit /b 0
