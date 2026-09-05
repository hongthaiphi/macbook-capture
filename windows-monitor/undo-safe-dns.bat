@echo off
echo ============================================================
echo  Undo AdGuard DNS + SafeSearch Settings
echo ============================================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator.
    pause
    exit /b 1
)

echo Removing Chrome policies...
reg delete "HKLM\SOFTWARE\Policies\Google\Chrome" /f >nul 2>&1
echo Done.

echo Removing Edge policies...
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Edge" /f >nul 2>&1
echo Done.

echo Resetting system DNS to automatic (DHCP)...
powershell -Command "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | ForEach-Object { Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ResetServerAddresses }"
echo Done.

echo Removing Firefox policies...
set FF_PATH=C:\Program Files\Mozilla Firefox
if exist "%FF_PATH%\distribution\policies.json" (
    del "%FF_PATH%\distribution\policies.json"
    echo Firefox policy removed.
) else (
    echo No Firefox policy found.
)

echo Flushing DNS cache...
ipconfig /flushdns >nul

echo.
echo All settings have been reverted to defaults.
echo Restart your browsers for changes to take effect.
echo.
pause
