@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title KTX Auto Booker - Start

if not exist "frontend\dist\index.html" (
  echo Frontend files are missing. Extract the ZIP again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo First-time setup will start now.
  call "%~dp0INSTALL_ONCE.bat"
  if errorlevel 1 exit /b 1
)

if exist "data\server.pid" (
  set /p SERVER_PID=<"data\server.pid"
  tasklist /FI "PID eq !SERVER_PID!" 2>nul | findstr /R /C:"[ ]!SERVER_PID![ ]" >nul
  if not errorlevel 1 (
    echo Server is already running. PID: !SERVER_PID!
    start "" "http://127.0.0.1:8000"
    exit /b 0
  )
  del /Q "data\server.pid" >nul 2>nul
)

echo Starting KTX Auto Booker...
start "KTX Auto Booker Server" /D "%CD%" cmd /k ""%CD%\.venv\Scripts\python.exe" "%CD%\scripts\run_server.py""
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:8000"
echo Server started. This launcher window may be closed.
timeout /t 2 /nobreak >nul
