@echo off
setlocal
cd /d "%~dp0"
title KTX Auto Booker - First Setup

echo.
echo [1/3] Checking Python...

if exist ".venv\Scripts\python.exe" goto python_ready

py -3.12 -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" goto python_ready

py -3.11 -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" goto python_ready

python -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)" >nul 2>nul
if not errorlevel 1 python -m venv .venv
if exist ".venv\Scripts\python.exe" goto python_ready

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" "%LocalAppData%\Programs\Python\Python312\python.exe" -m venv .venv
if exist ".venv\Scripts\python.exe" goto python_ready

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" "%LocalAppData%\Programs\Python\Python311\python.exe" -m venv .venv
if exist ".venv\Scripts\python.exe" goto python_ready

if exist "%ProgramFiles%\Python312\python.exe" "%ProgramFiles%\Python312\python.exe" -m venv .venv
if exist ".venv\Scripts\python.exe" goto python_ready

if exist "%ProgramFiles%\Python311\python.exe" "%ProgramFiles%\Python311\python.exe" -m venv .venv
if exist ".venv\Scripts\python.exe" goto python_ready

echo.
echo Python 3.11 or 3.12 was not found.
echo Install Python from https://www.python.org/downloads/windows/
echo Be sure to enable "Add Python to PATH" during installation.
pause
exit /b 1

:python_ready
echo Python was found successfully.
echo [2/3] Installing server packages...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto install_error
python -m pip install -r requirements.txt
if errorlevel 1 goto install_error

echo [3/3] Installing Chromium for browser automation...
python -m playwright install chromium
if errorlevel 1 goto install_error

if not exist "data" mkdir "data"
echo installed>"data\install.complete"
echo.
echo Setup completed successfully.
echo Run START_SERVER.bat to start the server.
pause
exit /b 0

:install_error
echo.
echo Setup failed. Check the Internet connection and try again.
pause
exit /b 1
