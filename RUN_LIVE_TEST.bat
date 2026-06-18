@echo off
setlocal enabledelayedexpansion
title PulseDesk v5 — Live Website Test Launcher (LAN + Internet)
color 0B
cls

set ROOT=%~dp0
set BACKEND=%ROOT%backend
set FRONTEND=%ROOT%frontend
set LOG_DIR=%ROOT%logs
set TUNNEL_LOG=%LOG_DIR%\tunnel.log

REM Create logs directory
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ========================================================
echo   PulseDesk v5 — Live Website Test Launcher
echo ========================================================
echo.

REM ─── Verify Setup ───────────────────────────────────────────
set SETUP_REQUIRED=false
if not exist "%BACKEND%\venv\Scripts\python.exe" set SETUP_REQUIRED=true
if not exist "%FRONTEND%\node_modules" set SETUP_REQUIRED=true
if not exist "%BACKEND%\.env" set SETUP_REQUIRED=true

if "%SETUP_REQUIRED%"=="true" (
    echo [ERROR] PulseDesk is not fully set up.
    echo Please run RUN_PULSEDESK.bat first to complete installation.
    echo.
    pause & exit /b 1
)

echo [OK] Installation verified.
echo.

REM ─── Verify API Keys ────────────────────────────────────────
set GROQ_CONFIGURED=false
set DB_CONFIGURED=false
for /f "tokens=2 delims==" %%A in ('findstr /r "^GROQ_API_KEY=" "%BACKEND%\.env"') do (
    if not "%%A"=="" if not "%%A"=="YOUR_GROQ_API_KEY_HERE" set GROQ_CONFIGURED=true
)
for /f "tokens=2 delims==" %%A in ('findstr /r "^DATABASE_URL=" "%BACKEND%\.env"') do (
    if not "%%A"=="" if not "%%A"=="postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/pulsedesk" set DB_CONFIGURED=true
)
if "%DB_CONFIGURED%"=="false" (
    echo [WARN] Database not configured in .env
    pause & exit /b 1
)

REM ─── Kill existing processes on required ports ─────────────
echo Checking port availability...
call :kill_port 8000
call :kill_port 5173
call :kill_port 4040
echo.

REM ─── Detect Local IP for LAN testing ────────────────────────
set "LOCAL_IP="
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /R /C:"IPv4 Address"') do (
    set "_RAW=%%A"
    set "_IP=!_RAW: =!"
    echo !_IP! | findstr /R "^10\. ^192\.168\. ^172\." >nul 2>&1
    if not errorlevel 1 (
        if not defined LOCAL_IP set "LOCAL_IP=!_IP!"
    )
)
if not defined LOCAL_IP (
    for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /R /C:"IPv4 Address"') do (
        if not defined LOCAL_IP (
            set "_RAW=%%A"
            set "LOCAL_IP=!_RAW: =!"
        )
    )
)

REM ─── Start Backend ──────────────────────────────────────────
echo [1/3] Starting Backend (FastAPI) on 0.0.0.0:8000...
start "PulseDesk Backend" cmd /k "cd /d "%BACKEND%" && "%BACKEND%\venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info"

echo Waiting for backend startup...
set "HEALTH_OK="
for /L %%I in (1,1,15) do (
    for /f %%R in ('powershell -NoProfile -Command "try{$r=Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 1;if($r.StatusCode -eq 200){'ok'}}catch{'wait'}"') do (
        if "%%R"=="ok" set "HEALTH_OK=1"
    )
    if defined HEALTH_OK goto :backend_ready
    ping 127.0.0.1 -n 2 >nul
)
:backend_ready
if defined HEALTH_OK (
    echo [OK] Backend is healthy.
) else (
    echo [WARN] Backend health check timed out. Continuing...
)
echo.

REM ─── Start Frontend ─────────────────────────────────────────
echo [2/3] Starting Frontend (React/Vite) on 0.0.0.0:5173...
start "PulseDesk Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev:lan"
ping 127.0.0.1 -n 5 >nul
echo.

REM ─── Start Tunnel for Internet Testing ──────────────────────
echo [3/3] Exposing local server to the Internet via localtunnel...
if exist "%TUNNEL_LOG%" del "%TUNNEL_LOG%"
start "PulseDesk Tunnel (localtunnel)" cmd /k "npx --yes localtunnel --port 5173 > "%TUNNEL_LOG%""
echo Waiting for tunnel URL generation (max 10s)...
ping 127.0.0.1 -n 9 >nul

set "PUBLIC_URL="
if exist "%TUNNEL_LOG%" (
    for /f "tokens=4" %%A in ('findstr /C:"your url is:" "%TUNNEL_LOG%" 2^>nul') do (
        set "PUBLIC_URL=%%A"
    )
)

echo.
echo ========================================================
echo   PulseDesk is RUNNING for Live testing!
echo ========================================================
echo.
echo  On THIS PC:
echo    Dashboard : http://localhost:5173
echo    API Docs  : http://localhost:8000/api/docs
echo.
if defined LOCAL_IP (
    echo  From OTHER devices on SAME Wi-Fi / LAN / Hotspot:
    echo    Dashboard : http://!LOCAL_IP!:5173
    echo    API Base  : http://!LOCAL_IP!:8000
    echo.
    echo  *** Join Code Server URL: http://!LOCAL_IP!:8000
)
if defined PUBLIC_URL (
    echo.
    echo  From anywhere on the INTERNET:
    echo    Dashboard : !PUBLIC_URL!
    echo.
    echo  *** Join Code Server URL: !PUBLIC_URL!
    echo    (Note: Ensure your backend endpoints are exposed if agents connect remotely)
) else (
    echo.
    echo  Internet exposure: Tunnel not detected yet. Check the localtunnel window.
)
echo.
echo  Steps to enroll another device:
echo    1. Go to Enroll Device on the admin dashboard.
    2. Generate a Join Code, ensuring the Server URL matches
       either the Local LAN IP or the Tunnel URL.
    3. Run the installation script on the employee machine.
echo.
echo  Keep Backend, Frontend, and localtunnel windows running!
echo ========================================================
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
echo [WARN] Port %PORT% is in use - terminating old process...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do (
    taskkill /PID %%P /F >nul 2>&1
)
ping 127.0.0.1 -n 2 >nul
exit /b 0
