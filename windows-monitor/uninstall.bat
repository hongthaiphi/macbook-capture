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

echo.
echo ========================================
echo  Uninstall complete.
echo ========================================
echo.
echo Note: config.json and usage.db are kept.
echo Delete the folder manually to remove all data.
echo.
pause
