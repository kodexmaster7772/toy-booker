@echo off
setlocal
cd /d "%~dp0"
title KTX Auto Booker - Update

if not exist "scripts\update_windows.ps1" (
  echo Update script is missing. Download the latest ZIP from GitHub.
  pause
  exit /b 1
)

set "UPDATER=%TEMP%\ktx-auto-booker-updater-%RANDOM%-%RANDOM%.ps1"
copy /Y "scripts\update_windows.ps1" "%UPDATER%" >nul
if errorlevel 1 (
  echo Could not prepare the updater.
  pause
  exit /b 1
)

start "KTX Auto Booker Updater" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%UPDATER%" -InstallDir "%CD%"
exit /b 0
