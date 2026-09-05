@echo off
echo ========================================
echo  Windows Monitor - Build Package
echo ========================================
echo.
echo Script nay dong goi monitor thanh file .exe
echo va tao thu muc phan phoi san sang gui cho
echo phu huynh cai dat.
echo.
echo Yeu cau: Python + pip da cai tren may nay.
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python chua duoc cai dat.
    pause
    exit /b 1
)

:: Install build dependencies
echo [1/4] Installing build dependencies...
pip install pyinstaller -q
pip install -r requirements.txt -q
echo Done.
echo.

:: Build with PyInstaller
echo [2/4] Building monitor.exe with PyInstaller...
echo (co the mat 1-2 phut)
echo.

pyinstaller ^
    --noconfirm ^
    --onedir ^
    --noconsole ^
    --name "monitor" ^
    --hidden-import "monitor.config" ^
    --hidden-import "monitor.db" ^
    --hidden-import "monitor.tracker" ^
    --hidden-import "monitor.screenshot" ^
    --hidden-import "monitor.blocker" ^
    --hidden-import "monitor.reporter" ^
    --hidden-import "monitor.limiter" ^
    --hidden-import "monitor.utils" ^
    --hidden-import "monitor.main" ^
    --collect-all "telegram" ^
    --collect-all "mss" ^
    run_monitor.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Build that bai.
    pause
    exit /b 1
)

echo Build thanh cong.
echo.

:: Create distribution folder
echo [3/4] Creating distribution package...

set DIST=dist\WindowsMonitor
if exist "%DIST%" rmdir /s /q "%DIST%"
mkdir "%DIST%"

:: Copy built exe and dependencies
xcopy /s /e /q "dist\monitor\*" "%DIST%\monitor\" >nul

:: Copy config and scripts
copy config.example.json "%DIST%\" >nul
copy setup-safe-dns.bat "%DIST%\" >nul
copy undo-safe-dns.bat "%DIST%\" >nul

echo Done.
echo.

:: Create the distribution installer
echo [4/4] Creating installer scripts...

:: Write install.bat for distribution
> "%DIST%\install.bat" (
echo @echo off
echo echo ========================================
echo echo  Windows Monitor - Cai Dat
echo echo ========================================
echo echo.
echo.
echo :: Must run as Administrator
echo net session ^>nul 2^>^&1
echo if %%errorlevel%% neq 0 ^(
echo     echo ERROR: Phai chay voi quyen Administrator.
echo     echo Click phai file nay ^^^> "Run as administrator"
echo     echo.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo set MONITOR_DIR=%%~dp0
echo set MONITOR_EXE=%%MONITOR_DIR%%monitor\monitor.exe
echo.
echo :: Check monitor.exe exists
echo if not exist "%%MONITOR_EXE%%" ^(
echo     echo ERROR: Khong tim thay monitor\monitor.exe
echo     echo Dam bao ban giai nen day du thu muc.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo :: Setup config
echo if not exist "%%MONITOR_DIR%%config.json" ^(
echo     echo.
echo     echo ========================================
echo     echo  Cau hinh Telegram Bot
echo     echo ========================================
echo     echo.
echo     echo Ban can tao Telegram Bot truoc:
echo     echo 1. Mo Telegram, tim @BotFather
echo     echo 2. Gui lenh /newbot
echo     echo 3. Lam theo huong dan de lay Bot Token
echo     echo 4. Gui tin nhan bat ky cho bot
echo     echo 5. Truy cap: https://api.telegram.org/bot[TOKEN]/getUpdates
echo     echo    de lay Chat ID
echo     echo.
echo     set /p BOT_TOKEN=Nhap Bot Token:
echo     set /p CHAT_ID=Nhap Chat ID:
echo     echo.
echo     echo {> "%%MONITOR_DIR%%config.json"
echo     echo   "bot_token": "%%BOT_TOKEN%%",>> "%%MONITOR_DIR%%config.json"
echo     echo   "chat_id": "%%CHAT_ID%%",>> "%%MONITOR_DIR%%config.json"
echo     echo   "poll_interval_seconds": 5,>> "%%MONITOR_DIR%%config.json"
echo     echo   "screenshot_interval_seconds": 60,>> "%%MONITOR_DIR%%config.json"
echo     echo   "daily_report_hour": 22,>> "%%MONITOR_DIR%%config.json"
echo     echo   "idle_timeout_seconds": 120>> "%%MONITOR_DIR%%config.json"
echo     echo }>> "%%MONITOR_DIR%%config.json"
echo     echo Config da luu.
echo     echo.
echo ^)
echo.
echo echo ========================================
echo echo  Dang ky Task Scheduler
echo echo ========================================
echo echo.
echo echo De monitor khong bi tat boi user Standard,
echo echo task se chay duoi tai khoan Administrator.
echo echo.
echo set /p ADMIN_USER=Admin username ^(vd: %%USERNAME%%^):
echo set /p ADMIN_PASS=Admin password:
echo echo.
echo.
echo :: Remove old task
echo schtasks /delete /tn "WindowsMonitor" /f ^>nul 2^>^&1
echo.
echo :: Create task
echo echo Creating scheduled task...
echo schtasks /create /tn "WindowsMonitor" /tr "\"%%MONITOR_EXE%%\"" /sc onlogon /ru "%%ADMIN_USER%%" /rp "%%ADMIN_PASS%%" /rl highest /f
echo.
echo if %%errorlevel%% neq 0 ^(
echo     echo ERROR: Khong tao duoc scheduled task.
echo     echo Kiem tra lai username/password.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo :: Configure restart on failure + working directory
echo powershell -Command "$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit 0; Set-ScheduledTask -TaskName 'WindowsMonitor' -Settings $settings" ^>nul 2^>^&1
echo.
echo :: Start now
echo echo.
echo echo Starting monitor...
echo cd /d "%%MONITOR_DIR%%"
echo start "" "%%MONITOR_EXE%%"
echo.
echo echo ========================================
echo echo  Cai dat hoan tat!
echo echo ========================================
echo echo.
echo echo  - Monitor dang chay ngam.
echo echo  - Tu dong khoi dong khi bat ky user nao dang nhap.
echo echo  - Standard user KHONG the tat duoc.
echo echo  - Neu crash, tu dong restart sau 1 phut.
echo echo.
echo echo  Buoc tiep theo:
echo echo  1. Chay setup-safe-dns.bat de bat bao ve DNS
echo echo  2. Tao tai khoan Standard cho con
echo echo     Settings ^^^> Accounts ^^^> Family ^^^> Add account
echo echo.
echo pause
)

:: Write uninstall.bat for distribution
> "%DIST%\uninstall.bat" (
echo @echo off
echo echo ========================================
echo echo  Windows Monitor - Go Cai Dat
echo echo ========================================
echo echo.
echo.
echo net session ^>nul 2^>^&1
echo if %%errorlevel%% neq 0 ^(
echo     echo ERROR: Phai chay voi quyen Administrator.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo echo Removing scheduled task...
echo schtasks /delete /tn "WindowsMonitor" /f ^>nul 2^>^&1
echo echo Done.
echo.
echo echo Stopping monitor process...
echo taskkill /f /im monitor.exe ^>nul 2^>^&1
echo echo Done.
echo.
echo echo Cleaning hosts file...
echo powershell -Command "(Get-Content 'C:\Windows\System32\drivers\etc\hosts') | Where-Object { $_ -notmatch 'MONITOR-BLOCKED' } | Set-Content 'C:\Windows\System32\drivers\etc\hosts'"
echo ipconfig /flushdns ^>nul 2^>^&1
echo echo Done.
echo.
echo echo Removing browser blocklist policies...
echo reg delete "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /f ^>nul 2^>^&1
echo reg delete "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /f ^>nul 2^>^&1
echo echo Done.
echo.
echo echo Removing app launch blocks...
echo for %%%%a in ^(chrome.exe msedge.exe firefox.exe brave.exe opera.exe Minecraft.Windows.exe RobloxPlayerBeta.exe steam.exe EpicGamesLauncher.exe Discord.exe^) do ^(
echo     reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\%%%%a" /v Debugger ^>nul 2^>^&1 ^&^& ^(
echo         reg delete "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\%%%%a" /v Debugger /f ^>nul 2^>^&1
echo     ^)
echo ^)
echo echo Done.
echo.
echo echo ========================================
echo echo  Go cai dat hoan tat.
echo echo ========================================
echo echo.
echo echo config.json va usage.db van duoc giu lai.
echo echo Xoa thu muc nay de xoa toan bo du lieu.
echo echo.
echo pause
)

echo Done.
echo.
echo ========================================
echo  Build hoan tat!
echo ========================================
echo.
echo Thu muc phan phoi: dist\WindowsMonitor\
echo.
echo Noi dung:
echo   WindowsMonitor\
echo     monitor\         - Chuong trinh (monitor.exe + libs)
echo     config.example.json
echo     install.bat      - Cai dat (chi can chay file nay)
echo     uninstall.bat    - Go cai dat
echo     setup-safe-dns.bat  - Bat bao ve DNS
echo     undo-safe-dns.bat   - Tat bao ve DNS
echo.
echo Nen zip thu muc WindowsMonitor va gui cho phu huynh.
echo Ho chi can: giai nen ^> chay install.bat ^> xong.
echo.
echo Khong can cai Python!
echo.
pause
