# Developer Guide — Windows Monitor

## Quick Start

```bash
cd windows-monitor
copy config.example.json config.json
# Edit config.json: fill bot_token and chat_id
pip install -r requirements.txt
python -m monitor
```

## Architecture Overview

```
main.py (asyncio event loop)
  ├── Tracker        — polls active window every 5s
  ├── ScreenshotLoop — captures screen every 60s
  ├── ReportScheduler— sends daily summary at configured hour
  └── TelegramBot    — receives commands via long-polling
```

All four run concurrently in a single process using `asyncio`. The Telegram bot uses `python-telegram-bot` v21+ (async-native).

## Module Responsibilities

### config.py
Loads `config.json` from the project root. Validates required fields (`bot_token`, `chat_id`) and sets defaults for optional ones. Exits with a clear error if config is missing or incomplete.

### db.py
SQLite database at `usage.db` in the project root. Three tables:

- **usage_log** — one row per poll tick (every 5s when user is active). Columns: `timestamp`, `app_name`, `window_title`, `domain` (nullable), `duration_seconds`.
- **blocked_domains** — domains the admin has blocked via Telegram.
- **daily_reports** — tracks which dates have had reports sent.

Uses WAL journal mode for concurrent read/write safety. All functions open and close their own connection (simple, no connection pooling needed for this workload).

### tracker.py
The core tracking engine. Uses Win32 API via `ctypes`:

- `GetForegroundWindow()` → active window handle
- `GetWindowThreadProcessId()` → PID → process name (via `psutil`)
- `GetWindowTextW()` → window title
- `GetLastInputInfo()` → idle detection

**Idle detection**: if the user hasn't touched keyboard/mouse for `idle_timeout_seconds` (default 120s), the tick is skipped — no false usage logged.

**Blocked domain alert**: when tracker detects a blocked domain AND it's a new detection (not the same app+domain as last tick), it fires the `on_blocked_domain` callback which sends a Telegram alert.

### utils.py
Domain extraction logic. Maps browser process names to their window title suffix pattern:

```
chrome.exe  → " - Google Chrome"
msedge.exe  → " - Microsoft Edge"  
firefox.exe → " — Mozilla Firefox"  (em dash, not hyphen)
brave.exe   → " - Brave"
```

Strips the suffix, then:
1. Regex scan for domain pattern (e.g., `youtube.com`)
2. Fallback: known keyword → domain map (e.g., "YouTube" → `youtube.com`)

Also provides `format_duration()` and `make_bar()` for report formatting.

### screenshot.py
Uses `mss` library (no GUI framework dependency) to capture the full virtual screen. Saves to a temp PNG, sends via Telegram Bot API `sendPhoto`, then deletes the temp file.

`ScreenshotLoop` wraps this in an async loop with idle detection — doesn't capture when the user is away.

### blocker.py
Two parts:

**Hosts file management**: Appends `127.0.0.1 <domain> # MONITOR-BLOCKED` to `C:\Windows\System32\drivers\etc\hosts`. The `MARKER` comment tag lets us cleanly remove only our entries without touching other hosts entries. Requires Administrator privileges.

**Telegram bot handlers**: `/block`, `/unblock`, `/list`, `/report`, `/screenshot`. All commands check `is_admin()` — only the configured `chat_id` can issue commands.

### reporter.py
Builds the daily report by querying SQLite:
- Total active time
- Top 7 apps by duration
- Top 7 websites by duration
- Visual bar chart using Unicode block characters

`ReportScheduler` checks every minute if it's the configured hour and hasn't sent today's report yet.

### main.py
Entry point. Initializes everything, starts the Telegram bot's polling, creates three async tasks (tracker, screenshot, report scheduler), and waits for shutdown signal (Ctrl+C or SIGTERM).

Sends a "started" message on boot and "stopped" on clean shutdown.

## Data Flow

```
User opens Chrome → visits youtube.com
    │
    ▼
Tracker tick (every 5s)
    ├── GetForegroundWindow() → chrome.exe, "YouTube - Google Chrome"
    ├── extract_domain_from_title() → "youtube.com"
    ├── is_domain_blocked("youtube.com") → false
    └── db.log_usage("chrome.exe", "YouTube - Google Chrome", "youtube.com", 5)
    
User opens blocked site (tiktok.com)
    │
    ▼
Tracker tick
    ├── extract_domain_from_title() → "tiktok.com"
    ├── is_domain_blocked("tiktok.com") → true
    ├── on_blocked_domain("chrome.exe", "tiktok.com")
    │   └── send_blocked_alert() → Telegram message to admin
    └── db.log_usage(...)

22:00 daily
    │
    ▼
ReportScheduler
    ├── db.get_daily_summary()
    ├── build_daily_report() → formatted text
    └── bot.send_message() → Telegram daily report
```

## Adding a New Telegram Command

1. Add handler method in `blocker.py`:
```python
async def _cmd_foo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not self._is_admin(update):
        return
    # your logic here
    await update.message.reply_text("response")
```

2. Register in `build_app()`:
```python
CommandHandler("foo", self._cmd_foo),
```

## Testing Without Windows

The tracker module imports `ctypes.windll` which only exists on Windows. To develop on macOS/Linux, you can:

1. Mock `tracker.py` — replace `get_active_window_info()` and `get_idle_seconds()` with stubs
2. Test other modules independently — `db.py`, `utils.py`, `reporter.py` are cross-platform
3. Use `pytest` with the Windows-specific imports behind `platform.system()` checks (future improvement)

## App Time Limits (limiter.py)

Allows setting daily usage limits for browsers and games. When an app exceeds its daily limit:

1. **Kill process** — `taskkill /f /im <exe>`
2. **Block relaunch** — IFEO (Image File Execution Options) Debugger trick: sets `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\<exe>\Debugger` to `nul`. When Windows tries to launch the exe, it invokes "nul" as the debugger, which silently fails.
3. **Alert parent** — sends Telegram message with usage details
4. **Midnight reset** — a background loop detects date change and removes all IFEO blocks

### IFEO Debugger Trick

Windows checks the IFEO registry key before launching any executable. If a `Debugger` value is present, Windows launches that debugger process instead of the target exe (passing the exe path as an argument). By setting `Debugger = "nul"`, the launch effectively does nothing — the app cannot start.

This is more reliable than simply killing the process, because it prevents the child from being relaunched by the user or by auto-restart mechanisms.

### Telegram Commands

| Command | Example | Description |
|---------|---------|-------------|
| `/limit <app> <minutes>` | `/limit chrome 120` | Set 2-hour daily limit for Chrome |
| `/unlimit <app>` | `/unlimit chrome` | Remove limit and unblock |
| `/limits` | `/limits` | Show all limits with current usage |
| `/deny <app>` | `/deny chrome` | Block app immediately |
| `/allow <app>` | `/allow chrome` | Unblock app immediately |
| `/apps` | `/apps` | List known app shortcuts |

### Known App Shortcuts

`chrome`, `edge`, `firefox`, `brave`, `opera`, `minecraft`, `roblox`, `steam`, `epic`, `discord`, `zalo`, `telegram` — each maps to the exe name. Custom exe names (e.g., `fortnite.exe`) can also be used directly.

## Known Limitations

- **Window title parsing** is heuristic — some SPAs don't put the domain in the title
- **Incognito/private windows** may show generic titles
- **Multiple monitors** — `mss` captures the full virtual screen (all monitors stitched)
- **Admin rights** required for hosts file modification
- **No persistence of screenshot count** — `screenshot_loop.count` resets on restart
- **Task Scheduler** job uses `pythonw` — no console window, but also no visible errors

## AdGuard DNS + SafeSearch Setup

Two batch scripts handle browser-level and system-level DNS protection:

### setup-safe-dns.bat

Applies five layers of protection. Must run as Administrator.

**1. Chrome Registry Policies** (`HKLM\SOFTWARE\Policies\Google\Chrome`)

| Key | Value | Purpose |
|-----|-------|---------|
| `DnsOverHttpsMode` | `secure` | Force Chrome to use DNS-over-HTTPS only |
| `DnsOverHttpsTemplates` | `https://family.adguard-dns.com/dns-query` | Point DoH to AdGuard Family |
| `ForceGoogleSafeSearch` | `1` (DWORD) | Lock Google Search to SafeSearch mode |
| `BrowserGuestModeEnabled` | `0` (DWORD) | Disable Guest Mode bypass |
| `QuicAllowed` | `0` (DWORD) | Block QUIC/HTTP3 protocol (prevents DNS bypass) |
| `IncognitoModeAvailability` | `1` (DWORD) | Disable Incognito Mode |

Chrome reads these at startup from the Windows Registry. Level becomes `Mandatory`, scope is `Machine` — the user cannot override from `chrome://settings`.

**2. Edge Registry Policies** (`HKLM\SOFTWARE\Policies\Microsoft\Edge`)

Same as Chrome, plus:
- `ForceBingSafeSearch` = `2` (Strict) — locks Bing SafeSearch
- `InPrivateModeAvailability` = `1` — disables InPrivate browsing

Edge uses the same Chromium policy engine, different registry path.

**3. System-wide DNS via NRPT** — Name Resolution Policy Table, a Windows registry-based policy that forces ALL DNS queries through specified servers regardless of which network adapter or WiFi is active. Registry key:

```
HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient\DnsPolicyConfig\AdGuardFamily
  Name            = "."                          (match all domains)
  GenericDNSServers = "94.140.14.15;94.140.15.16"  (AdGuard Family)
  ConfigOptions   = 0x8                          (DWORD)
  Version         = 2                            (DWORD)
```

Unlike per-adapter DNS settings (which reset when connecting to a new WiFi), NRPT persists across all network changes. The per-adapter DNS (`Set-DnsClientServerAddress` on all adapters) is kept as a backup layer.


**4. Firefox** — doesn't use Windows Registry for policies. Instead, it reads `<install-dir>/distribution/policies.json`:

```json
{
  "policies": {
    "DNSOverHTTPS": {
      "Enabled": true,
      "ProviderURL": "https://family.adguard-dns.com/dns-query",
      "Locked": true
    },
    "DisablePrivateBrowsing": true,
    "Preferences": {
      "network.trr.mode": { "Value": 3, "Status": "locked" }
    }
  }
}
```

`network.trr.mode = 3` means "DoH only" (no fallback to plain DNS). `Locked` prevents the user from changing it in `about:config`.

**5. DNS flush** — `ipconfig /flushdns` clears cached resolutions so new DNS settings take effect immediately.

### undo-safe-dns.bat

Reverses everything: deletes Chrome/Edge registry keys, resets system DNS to DHCP, removes Firefox policy file.

### Verification

- Chrome: navigate to `chrome://policy` — all policies should show Level=`Mandatory`, Applies to=`Machine`
- Edge: `edge://policy` — same check
- Firefox: `about:policies` — should show active policies
- Test: Google search for explicit content → SafeSearch active; visit a known 18+ site → blocked by AdGuard DNS

### Why QUIC must be disabled

Chrome's QUIC (HTTP/3) protocol can bypass DNS resolution entirely by using cached QUIC connections to Google servers. This means even with DoH pointed at AdGuard, Chrome might skip the DNS lookup and connect directly. Disabling QUIC forces all connections through standard HTTPS, ensuring every domain lookup goes through AdGuard DNS Family.
