@echo off
setlocal enabledelayedexpansion
title PulseDesk v5 — Launcher
color 0A
cls

set ROOT=%~dp0
set BACKEND=%ROOT%backend
set FRONTEND=%ROOT%frontend
set LOG_DIR=%ROOT%logs
set BACKEND_LOG=%LOG_DIR%\backend.log
set FRONTEND_LOG=%LOG_DIR%\frontend.log

REM Create logs directory
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM ─── Verify Setup ───────────────────────────────────────────────────────────
echo Checking PulseDesk installation...
if not exist "%BACKEND%\venv\Scripts\python.exe" (
    echo [ERROR] Backend not initialized.
    echo Please run SETUP_WINDOWS.bat first.
    echo.
    pause & exit /b 1
)

if not exist "%FRONTEND%\node_modules" (
    echo [ERROR] Frontend not initialized.
    echo Please run SETUP_WINDOWS.bat first.
    echo.
    pause & exit /b 1
)

if not exist "%BACKEND%\.env" (
    echo [ERROR] Configuration missing: .env
    echo Please run SETUP_WINDOWS.bat to configure.
    echo.
    pause & exit /b 1
)

echo [OK] Installation verified
echo.

REM ─── Verify API Keys ────────────────────────────────────────────────────────
echo Checking API configuration...
set GROQ_CONFIGURED=false
set DB_CONFIGURED=false

for /f "tokens=2 delims==" %%A in ('findstr /r "^GROQ_API_KEY=" "%BACKEND%\.env"') do (
    if not "%%A"=="" if not "%%A"=="YOUR_GROQ_API_KEY_HERE" set GROQ_CONFIGURED=true
)

for /f "tokens=2 delims==" %%A in ('findstr /r "^DATABASE_URL=" "%BACKEND%\.env"') do (
    if not "%%A"=="" if not "%%A"=="postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/pulsedesk" set DB_CONFIGURED=true
)

if "!DB_CONFIGURED!"=="false" (
    echo [WARN] Database not configured in .env
    echo Please update DATABASE_URL before continuing.
    pause & exit /b 1
)

if "!GROQ_CONFIGURED!"=="false" (
    echo [WARN] Groq API key not configured
    echo AI features will be disabled. Set GROQ_API_KEY in .env to enable.
)
echo.

REM ─── Port Availability Check ──────────────────────────────────────────────
echo Checking port availability...
netstat -ano | findstr ":8000 " >nul 2>&1
if !errorlevel! equ 0 (
    echo [WARN] Port 8000 is already in use
    echo Finding and terminating existing process...
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":8000 "') do (
        taskkill /PID %%A /F >nul 2>&1
    )
    timeout /t 1 /nobreak >nul
)

netstat -ano | findstr ":5173 " >nul 2>&1
if !errorlevel! equ 0 (
    echo [WARN] Port 5173 is already in use
    echo Finding and terminating existing process...
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":5173 "') do (
        taskkill /PID %%A /F >nul 2>&1
    )
    timeout /t 1 /nobreak >nul
)
echo.

REM ─── Start Backend ────────────────────────────────────────────────────────
echo [1/2] Starting Backend (FastAPI)...
echo Logs: %BACKEND_LOG%
start "PulseDesk Backend" cmd /k "cd /d "%BACKEND%" && "%BACKEND%\venv\Scripts\python.exe" -m uvicorn app.main:app --port 8000 --host 0.0.0.0 --log-level info"

REM Wait for backend to be ready
echo Waiting for backend startup...
timeout /t 3 /nobreak >nul

REM Health check loop (max 15 seconds) — ping public /api/health endpoint
set HEALTH_CHECK_COUNT=0
:backend_health_check
if %HEALTH_CHECK_COUNT% gtr 7 (
    echo [WARN] Backend startup in progress - continuing
    goto :backend_ready
)

for /f %%A in ('powershell -command "try {$r = Invoke-WebRequest -Uri 'http://localhost:8000/api/health' -ErrorAction SilentlyContinue; if ($r.StatusCode -eq 200) {echo 'ok'}} catch {echo 'err'}"') do (
    if "%%A"=="ok" (
        echo [OK] Backend is responding
        goto :backend_ready
    )
)

set /a HEALTH_CHECK_COUNT+=1
timeout /t 1 /nobreak >nul
goto :backend_health_check

:backend_ready
echo.

REM ─── Start Frontend ───────────────────────────────────────────────────────
echo [2/2] Starting Frontend (React/Vite)...
echo Logs: %FRONTEND_LOG%
timeout /t 1 /nobreak >nul
start "PulseDesk Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev"

REM Wait for frontend
echo Waiting for frontend startup...
timeout /t 4 /nobreak >nul

echo.
echo ================================================
echo   PulseDesk is Running!
echo ================================================
echo.
echo   DASHBOARD
echo   Web UI: http://localhost:5173
echo.
echo   API ENDPOINTS
echo   Base URL: http://localhost:8000
echo   API Docs: http://localhost:8000/api/docs
echo   RedDoc: http://localhost:8000/api/redoc
echo   Join Portal: http://localhost:8000/join
echo.
echo   LOGIN
echo   Use the admin credentials you configured during SETUP_WINDOWS.bat
echo   If needed, reset via backend\reset_password.py
echo.
echo   ENDPOINTS (Authenticated)
echo   /api/v1/employees - Employee management
echo   /api/v1/analytics/timeline - Activity timeline
echo   /api/v1/analytics/heatmap - Activity heatmap
echo   /api/v1/ai/activity-patterns - AI activity analysis
echo   /api/v1/ai/burnout-risks - Burnout risk assessment
echo   /api/v1/ai/work-recommendations/{id} - Weekly report (Groq AI)
echo   /api/v1/devices - Device management
echo   /api/v1/screenshots - Screenshot management
echo.
echo   LOGS
echo   Backend: %BACKEND_LOG%
echo   Frontend: %FRONTEND_LOG%
echo.
echo   MANAGE
echo   Press Ctrl+C in either window to stop a service
echo   Close this window to minimize launcher
echo ================================================
echo.
echo Setup complete! Opening dashboard...
timeout /t 2 /nobreak >nul

REM Open dashboard in default browser
start http://localhost:5173

echo.
echo Both services are running. Close this window to dismiss launcher.
echo Services continue running in background windows.
echo.
pause
exit /b 0
