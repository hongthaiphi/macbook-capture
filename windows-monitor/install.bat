@echo off
echo ========================================
echo  Windows Monitor - Installation
echo ========================================
echo.

:: Must run as Administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Phai chay voi quyen Administrator.
    echo Click phai file nay ^> "Run as administrator"
    echo.
    pause
    exit /b 1
)

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

:: Get paths
set MONITOR_DIR=%~dp0
for %%I in (python.exe) do set PYTHON_PATH=%%~$PATH:I
for %%I in ("%PYTHON_PATH%") do set PYTHON_DIR=%%~dpI
set PYTHONW_PATH=%PYTHON_DIR%pythonw.exe

if not exist "%PYTHONW_PATH%" (
    echo WARNING: pythonw.exe not found at %PYTHONW_PATH%
    echo Using python.exe instead (a console window will appear)
    set PYTHONW_PATH=%PYTHON_PATH%
)

echo.
echo ========================================
echo  Task Scheduler Setup
echo ========================================
echo.
echo De monitor khong bi tat boi user Standard,
echo task se chay duoi tai khoan Administrator.
echo.
echo Nhap thong tin tai khoan ADMIN cua may tinh nay:
echo (tai khoan dang dung de chay install.bat)
echo.

:: Get admin credentials for Task Scheduler
set /p ADMIN_USER=Admin username (vd: Admin, %USERNAME%):
set /p ADMIN_PASS=Admin password:

echo.
echo Creating scheduled task...

:: Remove old task if exists
schtasks /delete /tn "WindowsMonitor" /f >nul 2>&1

:: Create task that runs under admin account with highest privileges
:: Triggered on ANY user logon — runs in the user's session but elevated
:: Standard users CANNOT kill an elevated process (Access Denied in Task Manager)
schtasks /create ^
    /tn "WindowsMonitor" ^
    /tr "\"%PYTHONW_PATH%\" -m monitor" ^
    /sc onlogon ^
    /ru "%ADMIN_USER%" ^
    /rp "%ADMIN_PASS%" ^
    /rl highest ^
    /f

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Khong tao duoc scheduled task.
    echo Kiem tra lai username va password.
    echo.
    echo Ban van co the chay thu bang: python -m monitor
    pause
    exit /b 1
)

echo Task created successfully.
echo.

:: Also set task to restart on failure
echo Configuring auto-restart on failure...
powershell -Command "$action = New-ScheduledTaskAction -Execute '%PYTHONW_PATH%' -Argument '-m monitor' -WorkingDirectory '%MONITOR_DIR%'; $settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit 0; Set-ScheduledTask -TaskName 'WindowsMonitor' -Settings $settings -Action $action" >nul 2>&1

:: Set working directory via XML update
powershell -Command "$task = Get-ScheduledTask 'WindowsMonitor'; $task.Actions[0].WorkingDirectory = '%MONITOR_DIR%'; Set-ScheduledTask -InputObject $task" >nul 2>&1

echo.

:: Start now
echo Starting monitor now...
cd /d "%MONITOR_DIR%"
start "" "%PYTHONW_PATH%" -m monitor

echo.
echo ========================================
echo  Installation complete!
echo ========================================
echo.
echo  - Monitor dang chay ngam.
echo  - Tu dong khoi dong khi bat ky user nao dang nhap.
echo  - Standard user KHONG the tat duoc process.
echo  - Neu process bi crash, tu dong restart sau 1 phut.
echo.
echo  Dieu khien qua Telegram bot.
echo.
echo ========================================
echo  QUAN TRONG: Tao tai khoan Standard cho con
echo ========================================
echo.
echo  De bao ve toi da, hay tao tai khoan Windows
echo  kieu Standard (khong phai Admin) cho con:
echo.
echo  Settings ^> Accounts ^> Family ^> Add account
echo  Chon "Standard User" (khong phai Administrator)
echo.
pause
