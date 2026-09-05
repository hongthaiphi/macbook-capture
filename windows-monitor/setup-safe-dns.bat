@echo off
echo ============================================================
echo  AdGuard DNS Family + SafeSearch Setup for Windows
echo  Chrome, Edge, and system-level DNS protection
echo ============================================================
echo.

:: Check admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click the file and select "Run as administrator".
    pause
    exit /b 1
)

echo [1/5] Setting Chrome policies...

:: Chrome: Force DNS over HTTPS with AdGuard Family
reg add "HKLM\SOFTWARE\Policies\Google\Chrome" /v DnsOverHttpsMode /t REG_SZ /d "secure" /f >nul
reg add "HKLM\SOFTWARE\Policies\Google\Chrome" /v DnsOverHttpsTemplates /t REG_SZ /d "https://family.adguard-dns.com/dns-query" /f >nul

:: Chrome: Force Google SafeSearch
reg add "HKLM\SOFTWARE\Policies\Google\Chrome" /v ForceGoogleSafeSearch /t REG_DWORD /d 1 /f >nul

:: Chrome: Disable Guest Mode
reg add "HKLM\SOFTWARE\Policies\Google\Chrome" /v BrowserGuestModeEnabled /t REG_DWORD /d 0 /f >nul

:: Chrome: Disable QUIC protocol (prevents DNS bypass)
reg add "HKLM\SOFTWARE\Policies\Google\Chrome" /v QuicAllowed /t REG_DWORD /d 0 /f >nul

:: Chrome: Disable Incognito Mode
reg add "HKLM\SOFTWARE\Policies\Google\Chrome" /v IncognitoModeAvailability /t REG_DWORD /d 1 /f >nul

echo    Done.

echo [2/5] Setting Edge policies...

:: Edge: Force DNS over HTTPS with AdGuard Family
reg add "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v DnsOverHttpsMode /t REG_SZ /d "secure" /f >nul
reg add "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v DnsOverHttpsTemplates /t REG_SZ /d "https://family.adguard-dns.com/dns-query" /f >nul

:: Edge: Force Google SafeSearch
reg add "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v ForceGoogleSafeSearch /t REG_DWORD /d 1 /f >nul

:: Edge: Disable Guest Mode
reg add "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v BrowserGuestModeEnabled /t REG_DWORD /d 0 /f >nul

:: Edge: Disable QUIC protocol
reg add "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v QuicAllowed /t REG_DWORD /d 0 /f >nul

:: Edge: Disable InPrivate Mode
reg add "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v InPrivateModeAvailability /t REG_DWORD /d 1 /f >nul

:: Edge: Force Bing SafeSearch (strict)
reg add "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v ForceBingSafeSearch /t REG_DWORD /d 2 /f >nul

echo    Done.

echo [3/6] Setting system-wide DNS policy (NRPT)...

:: NRPT forces ALL DNS queries through AdGuard regardless of which network is connected.
:: This survives WiFi changes, VPN connections, and adapter resets.
set NRPT_KEY=HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient\DnsPolicyConfig\AdGuardFamily
reg add "%NRPT_KEY%" /v Name /t REG_SZ /d "." /f >nul
reg add "%NRPT_KEY%" /v GenericDNSServers /t REG_SZ /d "94.140.14.15;94.140.15.16" /f >nul
reg add "%NRPT_KEY%" /v ConfigOptions /t REG_DWORD /d 0x8 /f >nul
reg add "%NRPT_KEY%" /v Version /t REG_DWORD /d 2 /f >nul
echo    Done.

echo [4/6] Setting DNS on all network adapters (backup layer)...

:: Also set per-adapter DNS as a fallback layer
powershell -Command "Get-NetAdapter | ForEach-Object { Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ServerAddresses ('94.140.14.15','94.140.15.16') }"
echo    Done.

echo [5/6] Setting up Firefox policy (if installed)...

:: Firefox: registry policy (works from Firefox 78+, same as Chrome/Edge approach)
reg add "HKLM\SOFTWARE\Policies\Mozilla\Firefox\DNSOverHTTPS" /v Enabled /t REG_DWORD /d 1 /f >nul
reg add "HKLM\SOFTWARE\Policies\Mozilla\Firefox\DNSOverHTTPS" /v ProviderURL /t REG_SZ /d "https://family.adguard-dns.com/dns-query" /f >nul
reg add "HKLM\SOFTWARE\Policies\Mozilla\Firefox\DNSOverHTTPS" /v Locked /t REG_DWORD /d 1 /f >nul
reg add "HKLM\SOFTWARE\Policies\Mozilla\Firefox" /v DisablePrivateBrowsing /t REG_DWORD /d 1 /f >nul
reg add "HKLM\SOFTWARE\Policies\Mozilla\Firefox\Preferences" /v "network.trr.mode" /t REG_DWORD /d 3 /f >nul
echo    Firefox registry policies applied.

:: Firefox: also write policies.json (belt and suspenders)
set FF_FOUND=0
for %%P in (
    "C:\Program Files\Mozilla Firefox"
    "C:\Program Files (x86)\Mozilla Firefox"
    "%LOCALAPPDATA%\Mozilla Firefox"
    "%PROGRAMFILES%\Mozilla Firefox"
) do (
    if exist "%%~P\firefox.exe" (
        if not exist "%%~P\distribution" mkdir "%%~P\distribution"
        (
            echo {
            echo   "policies": {
            echo     "DNSOverHTTPS": {
            echo       "Enabled": true,
            echo       "ProviderURL": "https://family.adguard-dns.com/dns-query",
            echo       "Locked": true
            echo     },
            echo     "SearchEngines": {
            echo       "Default": "Google"
            echo     },
            echo     "DisablePrivateBrowsing": true,
            echo     "Preferences": {
            echo       "network.trr.mode": {
            echo         "Value": 3,
            echo         "Status": "locked"
            echo       }
            echo     }
            echo   }
            echo }
        ) > "%%~P\distribution\policies.json"
        echo    Firefox policies.json written to %%~P
        set FF_FOUND=1
    )
)
if "%FF_FOUND%"=="0" (
    echo    Firefox install folder not found - registry policy still active.
)

echo [6/6] Flushing DNS cache...
ipconfig /flushdns >nul
echo    Done.

echo.
echo ============================================================
echo  Setup complete! Here's what was configured:
echo ============================================================
echo.
echo  [OK] Chrome  - AdGuard DNS, SafeSearch, no Guest/Incognito
echo  [OK] Edge    - AdGuard DNS, SafeSearch, Bing SafeSearch, no Guest/InPrivate
echo  [OK] System  - NRPT policy: AdGuard DNS for ALL networks
echo  [OK] Adapter - DNS fallback on all adapters (94.140.14.15)
echo  [OK] Firefox - Policy applied (if installed)
echo.
echo  To verify Chrome: open chrome://policy
echo  To verify Edge:   open edge://policy
echo.
echo  To undo all changes, run: undo-safe-dns.bat
echo.
pause
