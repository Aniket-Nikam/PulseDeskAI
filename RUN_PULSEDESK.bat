@echo off
setlocal enabledelayedexpansion
title PulseDesk v5 — Launcher (Setup + Start)
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
set SETUP_REQUIRED=false
if not exist "%BACKEND%\venv\Scripts\python.exe" set SETUP_REQUIRED=true
if not exist "%FRONTEND%\node_modules" set SETUP_REQUIRED=true
if not exist "%BACKEND%\.env" set SETUP_REQUIRED=true

if "%SETUP_REQUIRED%"=="false" goto :skip_setup

echo [INFO] PulseDesk is not fully set up. Running integrated setup now...
echo.

REM ─── Find Python 3.11+ ─────────────────────────────────────────────────────
echo Searching for Python 3.11+...
set PY=
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    goto :py_found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    goto :py_found
)
if exist "C:\Program Files\Python311\python.exe" (
    set "PY=C:\Program Files\Python311\python.exe"
    goto :py_found
)
where py >nul 2>nul
if %errorlevel% equ 0 ( set PY=py && goto :py_found )
echo.
echo [ERROR] Python 3.11+ not found.
echo Download from: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
echo Make sure to check "Add Python to PATH" during installation.
echo.
pause & exit /b 1

:py_found
echo [OK] Python: %PY%
echo %PY%> "%ROOT%python_path.txt"
echo.

REM ─── Backend venv + packages ──────────────────────────────────────────────
echo [1/6] Creating backend virtual environment...
cd /d "%BACKEND%"
"%PY%" -m venv venv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment
    pause & exit /b 1
)
echo [OK] Virtual environment created
echo [2/6] Installing backend packages...
"%BACKEND%\venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
"%BACKEND%\venv\Scripts\python.exe" -m pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install backend packages
    pause & exit /b 1
)
echo [OK] Backend packages installed

REM ─── Environment config ───────────────────────────────────────────────────
echo [3/6] Setting up environment configuration...
if not exist "%BACKEND%\.env" (
    if exist "%BACKEND%\.env.example" (
        copy "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
    ) else (
        ( echo # PulseDesk Configuration
          echo DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/pulsedesk
          echo GROQ_API_KEY=YOUR_GROQ_API_KEY_HERE
          echo ALGORITHM=HS256
          echo SECRET_KEY=your-secret-key-change-me-in-production
          echo DEBUG=false ) > "%BACKEND%\.env"
    )
    echo.
    echo *** Opening .env for configuration ***
    notepad "%BACKEND%\.env"
    echo Press any key after saving .env...
    pause >nul
) else (
    echo [OK] .env already exists
)
icacls "%BACKEND%\.env" /inheritance:r /grant:r "%USERNAME%:F" >nul 2>&1
echo.

REM ─── Verify API keys ────────────────────────────────────────────────────────
for /f "tokens=2 delims==" %%A in ('findstr /r "^GROQ_API_KEY=" "%BACKEND%\.env"') do set GROQ_KEY=%%A
if "%GROQ_KEY%"="" (
    echo [WARN] GROQ_API_KEY not set – AI features disabled
)
if "%GROQ_KEY%"=="YOUR_GROQ_API_KEY_HERE" (
    echo [WARN] GROQ_API_KEY placeholder – AI features disabled
)
echo.

REM ─── Database migration ───────────────────────────────────────────────────
echo [4/6] Running database migrations...
cd /d "%BACKEND%"
"%BACKEND%\venv\Scripts\python.exe" -m alembic upgrade head >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Database migration failed.
    pause & exit /b 1
)
echo [OK] Database schema ready

REM ─── Create admin account ─────────────────────────────────────────────────
echo [5/6] Creating admin account...
cd /d "%BACKEND%"
set "ADMIN_EMAIL="
set "ADMIN_PASSWORD="
set "ADMIN_NAME="
set /p ADMIN_EMAIL=Enter admin email:
set /p ADMIN_NAME=Enter admin full name [Super Admin]:
if "%ADMIN_NAME%"=="" set "ADMIN_NAME=Super Admin"
set /p ADMIN_PASSWORD=Enter admin password (min 12 chars):
if "%ADMIN_EMAIL%"=="" ( echo [ERROR] Admin email required & pause & exit /b 1 )
if "%ADMIN_PASSWORD%"=="" ( echo [ERROR] Admin password required & pause & exit /b 1 )
"%BACKEND%\venv\Scripts\python.exe" -m app.db.seed
if errorlevel 1 (
    echo [ERROR] Admin creation failed.
    pause & exit /b 1
)
echo [OK] Admin account ready

REM ─── Frontend packages ───────────────────────────────────────────────────
echo [6/6] Installing frontend packages...
cd /d "%FRONTEND%"
call npm install --silent >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install frontend packages
    pause & exit /b 1
)
echo [OK] Frontend dependencies installed
echo.
echo ===============================================
echo   Setup Complete!
echo ===============================================
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo Admin Login: %ADMIN_EMAIL%
echo ===============================================
pause

:skip_setup
echo [OK] Installation verified

REM ─── Verify API Keys (runtime) ────────────────────────────────────────────────
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
if "%GROQ_CONFIGURED%"=="false" (
    echo [WARN] Groq API key not configured – AI features disabled.
)

echo.

REM ─── Port Availability Check ──────────────────────────────────────────────
netstat -ano | findstr ":8000 " >nul 2>&1
if !errorlevel! equ 0 (
    echo [WARN] Port 8000 is already in use – terminating existing process
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":8000 "') do (taskkill /PID %%A /F >nul 2>&1)
    ping 127.0.0.1 -n 2 >nul
)
netstat -ano | findstr ":5173 " >nul 2>&1
if !errorlevel! equ 0 (
    echo [WARN] Port 5173 is already in use – terminating existing process
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":5173 "') do (taskkill /PID %%A /F >nul 2>&1)
    ping 127.0.0.1 -n 2 >nul
)

echo.

REM ─── Start Backend ────────────────────────────────────────────────────────
echo [1/2] Starting Backend (FastAPI)...
start "PulseDesk Backend" cmd /k "cd /d "%BACKEND%" && "%BACKEND%\venv\Scripts\python.exe" -m uvicorn app.main:app --port 8000 --host 0.0.0.0 --log-level info"

echo Waiting for backend startup...
ping 127.0.0.1 -n 4 >nul

REM Health check loop (max ~15 seconds)
set HEALTH_CHECK_COUNT=0
:backend_health_check
if %HEALTH_CHECK_COUNT% gtr 7 (
    echo [WARN] Backend still initializing – proceeding anyway
    goto :backend_ready
)
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -ErrorAction Stop; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if !errorlevel! equ 0 (
    echo [OK] Backend is responding
    goto :backend_ready
)
set /a HEALTH_CHECK_COUNT+=1
ping 127.0.0.1 -n 2 >nul
goto :backend_health_check
:backend_ready

echo.

REM ─── Start Frontend ───────────────────────────────────────────────────────
echo [2/2] Starting Frontend (React/Vite)...
start "PulseDesk Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev"

echo Waiting for frontend startup...
ping 127.0.0.1 -n 5 >nul

echo ===============================================
echo   PulseDesk is Running!
echo ===============================================
echo   DASHBOARD
echo   Web UI: http://localhost:5173
echo   API ENDPOINTS
echo   Base URL: http://localhost:8000
echo   API Docs: http://localhost:8000/api/docs
echo   LOGIN – use admin credentials from setup
echo   LOGS – Backend: %BACKEND_LOG% ^| Frontend: %FRONTEND_LOG%
echo   Press Ctrl+C in either window to stop a service
echo   Close this window to minimize launcher
echo ===============================================
ping 127.0.0.1 -n 3 >nul
start http://localhost:5173
echo.
echo Both services are running. Close this window to dismiss launcher.
pause
exit /b 0
