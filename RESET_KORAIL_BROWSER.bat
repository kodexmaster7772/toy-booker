@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title KTX Auto Booker - Reset Korail Browser

if exist "data\server.pid" (
  set /p SERVER_PID=<"data\server.pid"
  echo Stopping the KTX Auto Booker server...
  taskkill /PID !SERVER_PID! /T /F >nul 2>nul
  del /Q "data\server.pid" >nul 2>nul
  timeout /t 2 /nobreak >nul
)

if not exist "data\korail-browser-profile" if not exist "data\korail-browser-profile-chromium" (
  echo The dedicated Korail browser profile does not exist yet.
  echo Start the server and try a real reservation again.
  pause
  exit /b 0
)

if exist "data\korail-browser-profile" (
  set "BACKUP=data\korail-browser-profile-backup-%RANDOM%-%RANDOM%"
  move "data\korail-browser-profile" "!BACKUP!" >nul
  if errorlevel 1 (
    echo The Chrome profile could not be reset. Close every automated Chrome window and try again.
    pause
    exit /b 1
  )
  echo Chrome backup: !BACKUP!
)

if exist "data\korail-browser-profile-chromium" (
  set "CHROMIUM_BACKUP=data\korail-browser-profile-chromium-backup-%RANDOM%-%RANDOM%"
  move "data\korail-browser-profile-chromium" "!CHROMIUM_BACKUP!" >nul
  if errorlevel 1 (
    echo The Chromium profile could not be reset. Close every automated browser window and try again.
    pause
    exit /b 1
  )
  echo Chromium backup: !CHROMIUM_BACKUP!
)

echo.
echo The dedicated Korail browser profile was reset successfully.
echo Your normal Chrome profile was not changed.
echo.
echo Next: run MODE_REAL_KORAIL.bat, then START_SERVER.bat.
pause
