@echo off
setlocal enabledelayedexpansion
title PulseDesk v5 — First Time Setup
color 0A
cls

echo.
echo ================================================
echo   PulseDesk v5 — First Time Setup
echo ================================================
echo.
echo PREREQUISITES:
echo   - PostgreSQL running (default: localhost:5432)
echo   - Database created: CREATE DATABASE pulsedesk;
echo   - Groq API key available (https://console.groq.com)
echo.
pause

set ROOT=%~dp0
set BACKEND=%ROOT%backend
set FRONTEND=%ROOT%frontend

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
    echo Make sure Python is properly installed and accessible.
    pause & exit /b 1
)
echo [OK] Virtual environment created

echo [2/6] Installing backend packages (may take 2-3 minutes)...
"%BACKEND%\venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
"%BACKEND%\venv\Scripts\python.exe" -m pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install backend packages
    echo Ensure requirements.txt exists in backend directory.
    pause & exit /b 1
)
echo [OK] Backend packages installed

REM ─── Environment config with API key protection ───────────────────────────
echo [3/6] Setting up environment configuration...
if not exist "%BACKEND%\.env" (
    REM Copy template
    if exist "%BACKEND%\.env.example" (
        copy "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
    ) else (
        REM Create with defaults
        (
            echo # PulseDesk Configuration
            echo DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/pulsedesk
            echo GROQ_API_KEY=YOUR_GROQ_API_KEY_HERE
            echo ALGORITHM=HS256
            echo SECRET_KEY=your-secret-key-change-me-in-production
            echo DEBUG=false
        ) > "%BACKEND%\.env"
    )
    
    echo.
    echo *** Opening .env for configuration ***
    echo.
    echo IMPORTANT: Set these values in the .env file:
    echo   1. DATABASE_URL - PostgreSQL connection string
    echo   2. GROQ_API_KEY - Your Groq API key (from console.groq.com)
    echo   3. SECRET_KEY - Strong random secret for JWT tokens
    echo.
    
    REM Secure file permissions (Windows only)
    icacls "%BACKEND%\.env" /inheritance:r /grant:r "%USERNAME%:F" >nul 2>&1
    
    notepad "%BACKEND%\.env"
    echo Press any key after saving .env...
    pause >nul
) else (
    echo [OK] .env already exists (not overwriting)
)
echo.

REM Verify API keys are set
for /f "tokens=2 delims==" %%A in ('findstr /r "^GROQ_API_KEY=" "%BACKEND%\.env"') do set GROQ_KEY=%%A
if "!GROQ_KEY!"=="" (
    echo [WARN] GROQ_API_KEY not set in .env - AI features will be disabled
)
if "!GROQ_KEY!"=="YOUR_GROQ_API_KEY_HERE" (
    echo [WARN] GROQ_API_KEY not configured - AI features will be disabled
)

REM ─── Database migration ───────────────────────────────────────────────────
echo [4/6] Running database migrations...
cd /d "%BACKEND%"
"%BACKEND%\venv\Scripts\python.exe" -m alembic upgrade head >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Database migration failed.
    echo Troubleshooting:
    echo   - Check DATABASE_URL in .env file
    echo   - Ensure PostgreSQL is running
    echo   - Verify database "pulsedesk" exists
    echo   - Run: CREATE DATABASE pulsedesk; in PostgreSQL
    echo.
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
if "!ADMIN_NAME!"=="" set "ADMIN_NAME=Super Admin"
set /p ADMIN_PASSWORD=Enter admin password (min 12 chars):

if "!ADMIN_EMAIL!"=="" (
    echo [ERROR] Admin email is required.
    pause & exit /b 1
)
if "!ADMIN_PASSWORD!"=="" (
    echo [ERROR] Admin password is required.
    pause & exit /b 1
)

"%BACKEND%\venv\Scripts\python.exe" -m app.db.seed
if errorlevel 1 (
    echo [ERROR] Admin creation failed.
    echo Check that email/password are valid and password is at least 12 chars.
    pause & exit /b 1
)
echo [OK] Admin account ready

REM ─── Frontend packages ────────────────────────────────────────────────────
echo [6/6] Installing frontend packages...
cd /d "%FRONTEND%"
call npm install --silent >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install frontend packages
    echo Make sure Node.js and npm are installed and in PATH
    echo Download from: https://nodejs.org/
    pause & exit /b 1
)
echo [OK] Frontend dependencies installed

echo.
echo ================================================
echo   Setup Complete!
echo ================================================
echo.
echo   Backend: http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://localhost:8000/api/docs
echo.
echo   Admin Login:
echo   Email: !ADMIN_EMAIL!
echo   Password: (the one you entered above)
echo.
echo   Next: Run START_WINDOWS.bat to launch PulseDesk
echo ================================================
echo.
pause
exit /b 0
