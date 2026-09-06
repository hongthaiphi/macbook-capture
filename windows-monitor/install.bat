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
if "%MONITOR_DIR:~-1%"=="\" set MONITOR_DIR=%MONITOR_DIR:~0,-1%

for %%I in (python.exe) do set PYTHON_PATH=%%~$PATH:I
for %%I in ("%PYTHON_PATH%") do set PYTHON_DIR=%%~dpI
set PYTHONW_PATH=%PYTHON_DIR%pythonw.exe

if not exist "%PYTHONW_PATH%" (
    echo NOTE: pythonw.exe not found, using python.exe with hidden wrapper.
    set PYTHONW_PATH=%PYTHON_PATH%
)

echo.
echo ========================================
echo  DEBUG INFO
echo ========================================
echo  MONITOR_DIR: %MONITOR_DIR%
echo  PYTHON: %PYTHONW_PATH%
echo.

:: Quick test
echo Testing monitor import...
python -c "from monitor.config import load_config; print('OK: config loads')"
if %errorlevel% neq 0 (
    echo ERROR: Monitor package cannot be imported.
    pause
    exit /b 1
)
echo.

:: Kill existing monitor
echo Stopping existing monitor...
taskkill /f /im pythonw.exe >nul 2>&1
taskkill /f /im wscript.exe >nul 2>&1
schtasks /delete /tn "WindowsMonitor" /f >nul 2>&1
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "WindowsMonitor" /f >nul 2>&1
timeout /t 2 >nul

:: ===== Create VBScript launcher (hidden, no CMD window) =====
:: This wrapper is used by BOTH Task Scheduler and Registry Run
:: ws.Run with flag 0 = completely hidden window
echo Creating hidden launcher...
echo Set ws = CreateObject("WScript.Shell")> "%MONITOR_DIR%\start-monitor.vbs"
echo ws.CurrentDirectory = "%MONITOR_DIR%">> "%MONITOR_DIR%\start-monitor.vbs"
echo ws.Run """%PYTHONW_PATH%"" -m monitor", 0, False>> "%MONITOR_DIR%\start-monitor.vbs"
echo  OK - start-monitor.vbs created.
echo.

echo ========================================
echo  Setting up auto-start (2 layers)
echo ========================================
echo.

:: ===== LAYER 1: Task Scheduler =====
:: Runs wscript.exe with VBS wrapper = completely hidden
:: Auto-restart if killed (up to 999 times, every 1 minute)
echo [1/2] Creating Task Scheduler task...
powershell -Command "$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '\""%MONITOR_DIR%\start-monitor.vbs""\"' -WorkingDirectory '%MONITOR_DIR%'; $trigger = New-ScheduledTaskTrigger -AtLogOn; $principal = New-ScheduledTaskPrincipal -GroupId 'BUILTIN\Users' -RunLevel Limited; $settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit 0 -MultipleInstances IgnoreNew; Register-ScheduledTask -TaskName 'WindowsMonitor' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null; $t = Get-ScheduledTask -TaskName 'WindowsMonitor'; Write-Host '  OK - Task created'; Write-Host '  Execute:' $t.Actions[0].Execute $t.Actions[0].Arguments"

if %errorlevel% neq 0 echo  FAILED - Task Scheduler setup failed.
if %errorlevel% equ 0 echo  Auto-restarts up to 999 times if killed.
echo.

:: ===== LAYER 2: Registry Run key =====
:: HKLM\...\Run = runs for ALL users on login
:: Standard users CANNOT modify HKLM registry
echo [2/2] Adding registry auto-start...
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "WindowsMonitor" /d "wscript.exe \"%MONITOR_DIR%\start-monitor.vbs\"" /f >nul
if %errorlevel% equ 0 echo  OK - Registry auto-start added.
if %errorlevel% neq 0 echo  FAILED - Registry auto-start failed.
echo.

:: ===== Start now =====
echo ========================================
echo  Starting monitor now...
echo ========================================
echo.

:: Start via VBScript directly (hidden, independent of this CMD)
wscript.exe "%MONITOR_DIR%\start-monitor.vbs"

:: Wait and verify
timeout /t 5 >nul
tasklist | findstr /i "python" >nul 2>&1
if not errorlevel 1 (
    echo Monitor is running (hidden, no window).
) else (
    echo WARNING: Monitor may not be running.
    echo Check: type "%MONITOR_DIR%\monitor.log"
    echo Or run manually: cd /d "%MONITOR_DIR%" ^& python -m monitor
)

echo.
echo ========================================
echo  Installation complete!
echo ========================================
echo.
echo  Protection layers:
echo  [1] Task Scheduler - auto-start on logon, auto-restart if killed
echo      (restarts within 1 minute, up to 999 times)
echo  [2] Registry HKLM\Run - backup auto-start, standard users
echo      CANNOT remove this registry key
echo.
echo  - Log file: %MONITOR_DIR%\monitor.log
echo  - Completely hidden (no window, no taskbar icon)
echo  - Dieu khien qua Telegram bot
echo.
echo ========================================
echo  QUAN TRONG: Tao tai khoan Standard cho con
echo ========================================
echo.
echo  Settings ^> Accounts ^> Family ^> Add account
echo  Chon "Standard User" (khong phai Administrator)
echo.
echo  Standard user:
echo  - Khong xoa duoc registry auto-start
echo  - Neu tat process, tu dong restart sau 1 phut
echo  - Khong thay cua so nao
echo.
pause
