@echo off
setlocal

set "AGENT=%~dp0"
cd /d "%AGENT%"

if not exist "%AGENT%venv\Scripts\python.exe" exit /b 1
if not exist "%AGENT%.env" exit /b 1

for /f %%A in ('powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -like ''python*'' -and $_.CommandLine -like ''*agent.py*'' }; if ($p) { ''yes'' } else { ''no'' }"') do set "ALREADY=%%A"
if /I "%ALREADY%"=="yes" exit /b 0

if exist "%AGENT%venv\Scripts\pythonw.exe" (
    start "" /min "%AGENT%venv\Scripts\pythonw.exe" "%AGENT%agent.py"
) else (
    start "" /min "%AGENT%venv\Scripts\python.exe" "%AGENT%agent.py"
)

exit /b 0
