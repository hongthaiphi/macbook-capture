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

## Known Limitations

- **Window title parsing** is heuristic — some SPAs don't put the domain in the title
- **Incognito/private windows** may show generic titles
- **Multiple monitors** — `mss` captures the full virtual screen (all monitors stitched)
- **Admin rights** required for hosts file modification
- **No persistence of screenshot count** — `screenshot_loop.count` resets on restart
- **Task Scheduler** job uses `pythonw` — no console window, but also no visible errors
