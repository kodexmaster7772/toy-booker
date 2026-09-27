@echo off
setlocal
cd /d "%~dp0"
if not exist ".env" copy /Y ".env.example" ".env" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='.env'; $c=Get-Content -Raw $p; $c=[regex]::Replace($c,'(?m)^KTX_AUTOMATION_MODE=.*$','KTX_AUTOMATION_MODE=playwright'); [IO.File]::WriteAllText((Resolve-Path $p),$c,(New-Object Text.UTF8Encoding($false)))"
if errorlevel 1 (
  echo Failed to change mode.
  pause
  exit /b 1
)
echo Real Korail mode enabled. Restart the server to apply.
pause
