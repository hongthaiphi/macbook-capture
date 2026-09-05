@echo off
echo ========================================
echo  Windows Monitor - Uninstall
echo ========================================
echo.

:: Remove scheduled task
echo Removing scheduled task...
schtasks /delete /tn "WindowsMonitor" /f >nul 2>&1
echo Done.

:: Kill running process
echo Stopping monitor process...
taskkill /f /im pythonw.exe /fi "WINDOWTITLE eq monitor*" >nul 2>&1

:: Clean hosts file
echo Cleaning hosts file...
powershell -Command "(Get-Content 'C:\Windows\System32\drivers\etc\hosts') | Where-Object { $_ -notmatch 'MONITOR-BLOCKED' } | Set-Content 'C:\Windows\System32\drivers\etc\hosts'"
ipconfig /flushdns >nul 2>&1
echo Done.

:: Remove browser URLBlocklist policies
echo Removing browser blocklist policies...
reg delete "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /f >nul 2>&1
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /f >nul 2>&1
echo Done.

:: Remove IFEO blocks (app time limits)
echo Removing app launch blocks...
for %%a in (chrome.exe msedge.exe firefox.exe brave.exe opera.exe Minecraft.Windows.exe RobloxPlayerBeta.exe steam.exe EpicGamesLauncher.exe Discord.exe) do (
    reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\%%a" /v Debugger >nul 2>&1 && (
        reg delete "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\%%a" /v Debugger /f >nul 2>&1
        echo   Unblocked %%a
    )
)
echo Done.

echo.
echo ========================================
echo  Uninstall complete.
echo ========================================
echo.
echo Note: config.json and usage.db are kept.
echo Delete the folder manually to remove all data.
echo.
pause
