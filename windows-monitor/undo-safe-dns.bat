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

echo Removing system-wide DNS policy (NRPT)...
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient\DnsPolicyConfig\AdGuardFamily" /f >nul 2>&1
echo Done.

echo Resetting adapter DNS to automatic (DHCP)...
powershell -Command "Get-NetAdapter | ForEach-Object { Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ResetServerAddresses }"
echo Done.

echo Removing Firefox policies...
reg delete "HKLM\SOFTWARE\Policies\Mozilla\Firefox" /f >nul 2>&1
for %%P in (
    "C:\Program Files\Mozilla Firefox"
    "C:\Program Files (x86)\Mozilla Firefox"
    "%LOCALAPPDATA%\Mozilla Firefox"
) do (
    if exist "%%~P\distribution\policies.json" (
        del "%%~P\distribution\policies.json"
        echo    Removed policies.json from %%~P
    )
)
echo Done.

echo Flushing DNS cache...
ipconfig /flushdns >nul

echo.
echo All settings have been reverted to defaults.
echo Restart your browsers for changes to take effect.
echo.
pause
