@echo off
echo ========================================
echo  Windows Monitor - Installation
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Install dependencies
echo Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

:: Check config
if not exist config.json (
    echo.
    echo config.json not found. Creating from template...
    copy config.example.json config.json
    echo.
    echo *** IMPORTANT: Edit config.json and fill in your Telegram bot token and chat ID ***
    echo.
    notepad config.json
    pause
    echo.
)

:: Get current directory
set MONITOR_DIR=%~dp0

:: Create Task Scheduler job
echo Creating scheduled task...
schtasks /create /tn "WindowsMonitor" /tr "pythonw -m monitor.main" /sc onlogon /rl highest /f
if %errorlevel% neq 0 (
    echo WARNING: Failed to create scheduled task. You may need to run as Administrator.
    echo You can still run manually: python -m monitor
) else (
    echo Task created successfully. Monitor will start on login.
)

:: Start now
echo.
echo Starting monitor now...
start "" pythonw -m monitor

echo.
echo ========================================
echo  Installation complete!
echo ========================================
echo.
echo Monitor is running in the background.
echo Use Telegram bot commands to control it.
echo.
pause
