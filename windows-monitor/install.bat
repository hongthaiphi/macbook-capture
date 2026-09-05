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
:: Remove trailing backslash for cleaner paths
if "%MONITOR_DIR:~-1%"=="\" set MONITOR_DIR=%MONITOR_DIR:~0,-1%

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
echo  DEBUG INFO
echo ========================================
echo  MONITOR_DIR: %MONITOR_DIR%
echo  PYTHON_PATH: %PYTHON_PATH%
echo  PYTHONW_PATH: %PYTHONW_PATH%
echo.

:: Quick test — verify monitor can at least import
echo Testing monitor import...
python -c "from monitor.config import load_config; print('OK: config loads')"
if %errorlevel% neq 0 (
    echo ERROR: Monitor package cannot be imported.
    echo Make sure you are running install.bat from the windows-monitor folder.
    pause
    exit /b 1
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

:: Kill existing monitor process
taskkill /f /im pythonw.exe /fi "WINDOWTITLE eq monitor" >nul 2>&1

:: Use PowerShell to create task with proper working directory
:: LogonType InteractiveOrPassword = runs in desktop session (can capture screen) but also starts when user not logged on
powershell -Command "$action = New-ScheduledTaskAction -Execute '%PYTHONW_PATH%' -Argument '-m monitor' -WorkingDirectory '%MONITOR_DIR%'; $trigger = New-ScheduledTaskTrigger -AtLogOn; $principal = New-ScheduledTaskPrincipal -UserId '%ADMIN_USER%' -LogonType InteractiveOrPassword -RunLevel Highest; $settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit 0; $task = Register-ScheduledTask -TaskName 'WindowsMonitor' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Password '%ADMIN_PASS%' -Force; if ($task) { Write-Host 'Task created successfully.'; Write-Host 'WorkingDirectory:' $task.Actions[0].WorkingDirectory; Write-Host 'LogonType:' $task.Principal.LogonType } else { Write-Host 'ERROR: Task creation failed'; exit 1 }"

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Khong tao duoc scheduled task.
    echo Kiem tra lai username va password.
    echo.
    echo Ban van co the chay thu bang: python -m monitor
    pause
    exit /b 1
)

echo.

:: Verify task was created correctly
echo Verifying task...
powershell -Command "$t = Get-ScheduledTask -TaskName 'WindowsMonitor' -ErrorAction SilentlyContinue; if ($t) { Write-Host '  Status:' $t.State; Write-Host '  Execute:' $t.Actions[0].Execute; Write-Host '  Arguments:' $t.Actions[0].Arguments; Write-Host '  WorkDir:' $t.Actions[0].WorkingDirectory; Write-Host '  RunAs:' $t.Principal.UserId } else { Write-Host 'ERROR: Task not found after creation!' }"

echo.

:: Start task via Task Scheduler (runs independently, survives CMD close)
echo Starting monitor via Task Scheduler...
schtasks /run /tn "WindowsMonitor"

:: Wait a moment then check if it's running
timeout /t 5 >nul
tasklist | findstr /i "pythonw.exe monitor.exe" >nul 2>&1
if not errorlevel 1 (
    echo Monitor is running via Task Scheduler, independent of this window.
) else (
    echo.
    echo WARNING: Monitor does not appear to be running.
    echo Check monitor.log for details:
    echo   type "%MONITOR_DIR%\monitor.log"
    echo.
    echo Or run manually to see errors:
    echo   cd /d "%MONITOR_DIR%"
    echo   python -m monitor
)

echo.
echo ========================================
echo  Installation complete!
echo ========================================
echo.
echo  - Monitor dang chay ngam.
echo  - Tu dong khoi dong khi bat ky user nao dang nhap.
echo  - Standard user KHONG the tat duoc process.
echo  - Neu process bi crash, tu dong restart sau 1 phut.
echo  - Log file: %MONITOR_DIR%\monitor.log
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
