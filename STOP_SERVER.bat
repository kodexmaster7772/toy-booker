@echo off
setlocal
cd /d "%~dp0"
title KTX Auto Booker - Stop

if not exist "data\server.pid" (
  echo The server is not running.
  pause
  exit /b 0
)

set /p SERVER_PID=<"data\server.pid"
echo Stopping server. PID: %SERVER_PID%
taskkill /PID %SERVER_PID% /T /F >nul 2>nul
if errorlevel 1 (
  echo The server process was already stopped or could not be found.
) else (
  echo Server stopped successfully.
)
del /Q "data\server.pid" >nul 2>nul
pause
