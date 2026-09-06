# Hướng dẫn triển khai — Windows Monitor

Tài liệu dành cho đội tích hợp, mô tả logic hoạt động và quy trình triển khai cho khách hàng.

---

## 1. Tổng quan

Windows Monitor là ứng dụng giám sát máy tính dành cho phụ huynh. Ứng dụng chạy ngầm trên máy Windows của con, gửi thông tin về Telegram cho phụ huynh.

### Chức năng chính

| Chức năng | Mô tả |
|-----------|-------|
| Theo dõi app/website | Ghi lại app đang mở + website đang truy cập mỗi 5 giây |
| Chụp màn hình | Tự động chụp mỗi 60 giây, gửi qua Telegram |
| Chặn website | Chặn domain qua hosts file + Chrome/Edge policy |
| Giới hạn thời gian app | Đặt giới hạn phút/ngày, tự động tắt app khi hết |
| Báo cáo hàng ngày | Gửi tổng kết sử dụng lúc 22:00 |
| Bảo vệ DNS | Cưỡng chế DNS qua AdGuard Family cho Chrome/Edge/Firefox |
| Điều khiển từ xa | Mọi thao tác qua Telegram bot |

### Yêu cầu hệ thống

- Windows 10/11
- Python 3.10+ (chỉ cần trên máy dev để build; máy khách hàng không cần nếu dùng bản đóng gói)
- Tài khoản Admin trên máy (để cài đặt)
- Tài khoản Standard cho con (để giới hạn quyền)
- Kết nối internet (Telegram bot)

---

## 2. Kiến trúc

### Cấu trúc thư mục

```
windows-monitor/
├── monitor/                  # Source code chính
│   ├── __init__.py
│   ├── __main__.py           # Entry point: python -m monitor
│   ├── main.py               # Khởi tạo + vòng lặp asyncio chính
│   ├── config.py             # Đọc config.json, tính BASE_DIR
│   ├── db.py                 # SQLite: usage_log, blocked_domains, app_limits
│   ├── tracker.py            # Theo dõi cửa sổ đang active (Win32 API)
│   ├── screenshot.py         # Chụp màn hình bằng mss, gửi Telegram
│   ├── blocker.py            # Chặn website (hosts + registry) + Telegram bot commands
│   ├── reporter.py           # Báo cáo ngày + alert website bị chặn
│   ├── limiter.py            # Giới hạn thời gian app (IFEO registry)
│   └── utils.py              # Trích domain từ title, format duration
├── config.example.json       # Template cấu hình
├── config.json               # Cấu hình thực (tạo khi cài, KHÔNG commit)
├── usage.db                  # SQLite database (tạo tự động, KHÔNG commit)
├── monitor.log               # Log file (tạo tự động)
├── monitor.lock              # Lock file chống chạy trùng (tạo tự động)
├── install.bat               # Cài đặt Task Scheduler + Registry
├── uninstall.bat             # Gỡ cài đặt
├── setup-safe-dns.bat        # Cài DNS protection
├── undo-safe-dns.bat         # Gỡ DNS protection
├── setup-task.ps1            # PowerShell helper cho Task Scheduler
├── run_monitor.py            # Entry point cho PyInstaller
├── build.bat                 # Đóng gói bằng PyInstaller
├── start-monitor.vbs         # VBScript launcher ẩn (tạo bởi install.bat)
└── requirements.txt          # Dependencies: mss, python-telegram-bot, psutil
```

### Luồng hoạt động chính

```
main.py khởi động
    │
    ├─► Đọc config.json (bot_token, chat_id)
    ├─► Khởi tạo SQLite database
    ├─► Gửi "🟢 Monitor started" qua Telegram
    │
    └─► Chạy 4 task song song (asyncio):
        │
        ├── [1] Tracker (mỗi 5s)
        │   ├── GetForegroundWindow() → tên app + tiêu đề cửa sổ
        │   ├── Trích domain từ tiêu đề (nếu là browser)
        │   ├── Ghi vào usage_log (SQLite)
        │   ├── Nếu domain bị chặn → alert Telegram
        │   └── Kiểm tra giới hạn thời gian → tắt + chặn app nếu hết
        │
        ├── [2] Screenshot (mỗi 60s)
        │   ├── Kiểm tra idle (không chụp nếu không thao tác > 120s)
        │   └── Chụp toàn màn hình → gửi Telegram → xóa file temp
        │
        ├── [3] Report Scheduler (mỗi phút check)
        │   └── Đúng 22:00 → gửi báo cáo tổng kết ngày
        │
        └── [4] Midnight Reset (mỗi phút check)
            └── Qua ngày mới → gỡ chặn tất cả app bị giới hạn
```

---

## 3. Chi tiết từng module

### 3.1. config.py — Quản lý cấu hình

**File:** `config.json` (tạo từ `config.example.json`)

```json
{
  "bot_token": "123456:ABC-DEF...",
  "chat_id": "987654321",
  "poll_interval_seconds": 5,
  "screenshot_interval_seconds": 60,
  "daily_report_hour": 22,
  "idle_timeout_seconds": 120
}
```

| Trường | Ý nghĩa | Mặc định |
|--------|---------|----------|
| `bot_token` | Token từ @BotFather trên Telegram | *bắt buộc* |
| `chat_id` | Chat ID của phụ huynh (dùng getUpdates API để lấy) | *bắt buộc* |
| `poll_interval_seconds` | Tần suất kiểm tra cửa sổ đang mở | 5s |
| `screenshot_interval_seconds` | Tần suất chụp màn hình | 60s |
| `daily_report_hour` | Giờ gửi báo cáo ngày (24h) | 22 |
| `idle_timeout_seconds` | Bao lâu không thao tác thì coi là idle | 120s |

**BASE_DIR:** Tự động xác định thư mục gốc project:
- Dev mode: `Path(__file__).resolve().parent.parent` (thư mục chứa folder `monitor/`)
- PyInstaller: `Path(sys.executable).parent.parent` (thư mục chứa folder `monitor/`)

Mọi đường dẫn (config.json, usage.db, monitor.log) đều tính từ BASE_DIR → hoạt động đúng bất kể working directory.

### 3.2. db.py — Database

**File:** `usage.db` (SQLite, tạo tự động)

**Bảng:**

```sql
-- Ghi lại mỗi lần poll (mỗi 5s khi user active)
usage_log (id, timestamp, app_name, window_title, domain, duration_seconds)

-- Danh sách domain bị chặn
blocked_domains (domain, blocked_at)

-- Theo dõi báo cáo đã gửi
daily_reports (date, sent_at, total_seconds)

-- Giới hạn thời gian app
app_limits (app_name, daily_limit_seconds, created_at)
```

### 3.3. tracker.py — Theo dõi cửa sổ

Dùng Windows API qua `ctypes`:

| API | Mục đích |
|-----|---------|
| `GetForegroundWindow()` | Lấy handle cửa sổ đang active |
| `GetWindowThreadProcessId()` | Từ handle → PID → tên process (qua `psutil`) |
| `GetWindowTextW()` | Lấy tiêu đề cửa sổ |
| `GetLastInputInfo()` | Phát hiện idle (không chuột/bàn phím) |

**Cách trích domain từ tiêu đề:**
1. Nhận diện browser (chrome.exe, msedge.exe, firefox.exe, brave.exe, opera.exe)
2. Cắt bỏ suffix browser: `"YouTube - Google Chrome"` → `"YouTube"`
3. Regex tìm domain pattern: `youtube.com`
4. Fallback: map keyword đã biết: `"YouTube"` → `youtube.com`

**Idle detection:** Nếu không thao tác chuột/bàn phím > 120s → không ghi log, không chụp ảnh.

### 3.4. screenshot.py — Chụp màn hình

- Dùng thư viện `mss` (không cần GUI framework)
- Chụp toàn bộ virtual screen (tất cả monitor)
- Lưu file temp PNG → gửi Telegram `sendPhoto` → xóa file temp
- **Quan trọng:** Process PHẢI chạy trong desktop session của user → không thể chạy elevated hoặc dưới tài khoản khác

### 3.5. blocker.py — Chặn website + Telegram bot

**Chặn website — 2 lớp:**

| Lớp | Cách thức | Tác dụng |
|-----|-----------|---------|
| Hosts file | Thêm `127.0.0.1 domain # MONITOR-BLOCKED` vào `C:\Windows\System32\drivers\etc\hosts` | Chặn ở cấp hệ thống (tất cả app) |
| Browser policy | Ghi domain vào `HKLM\...\Chrome\URLBlocklist` và `Edge\URLBlocklist` | Chặn ngay cả khi browser dùng DNS-over-HTTPS |

**Telegram commands:**

| Lệnh | Ví dụ | Chức năng |
|-------|-------|----------|
| `/block <domain>` | `/block tiktok.com` | Chặn website |
| `/unblock <domain>` | `/unblock tiktok.com` | Mở chặn website |
| `/list` | `/list` | Xem danh sách website bị chặn |
| `/limit <app> <phút>` | `/limit chrome 120` | Giới hạn 2 giờ/ngày cho Chrome |
| `/unlimit <app>` | `/unlimit chrome` | Xóa giới hạn |
| `/limits` | `/limits` | Xem trạng thái tất cả giới hạn |
| `/deny <app>` | `/deny chrome` | Chặn app ngay lập tức |
| `/allow <app>` | `/allow chrome` | Mở chặn app |
| `/apps` | `/apps` | Xem danh sách app hỗ trợ |
| `/report` | `/report` | Xem báo cáo sử dụng hôm nay |
| `/screenshot` | `/screenshot` | Chụp màn hình ngay |

**Bảo mật:** Chỉ `chat_id` trong config mới được phép gửi lệnh. Mọi tin nhắn từ chat_id khác đều bị bỏ qua.

### 3.6. limiter.py — Giới hạn thời gian app

**Cơ chế IFEO (Image File Execution Options):**

Khi app vượt giới hạn thời gian:
1. `taskkill /f /im chrome.exe` — tắt process
2. Registry: `HKLM\...\Image File Execution Options\chrome.exe\Debugger = "nul"` — Windows khi mở chrome.exe sẽ gọi "nul" làm debugger → app không thể khởi động lại
3. Gửi alert Telegram cho phụ huynh
4. Nửa đêm (00:00): tự động gỡ chặn tất cả app → reset ngày mới

**Danh sách app hỗ trợ tên tắt:**

| Tên tắt | Process |
|---------|---------|
| chrome | chrome.exe |
| edge | msedge.exe |
| firefox | firefox.exe |
| brave | brave.exe |
| minecraft | Minecraft.Windows.exe |
| roblox | RobloxPlayerBeta.exe |
| steam | steam.exe |
| epic | EpicGamesLauncher.exe |
| discord | Discord.exe |
| zalo | Zalo.exe |
| telegram | Telegram.exe |

Có thể dùng tên exe trực tiếp (vd: `/deny fortnite.exe`) cho app không có trong danh sách.

### 3.7. main.py — Entry point

**Single-instance lock:** Dùng `msvcrt.locking()` trên file `monitor.lock`. Nếu đã có instance đang chạy → instance mới tự thoát. Tránh xung đột Telegram `getUpdates`.

**Logging:** Ghi ra cả console (`stdout`) và file (`monitor.log`). Log level DEBUG. File log rotate max 2MB, giữ 3 bản backup. Mute log spam từ httpx/httpcore/telegram.

---

## 4. Cơ chế bảo vệ DNS

Script `setup-safe-dns.bat` cài 5 lớp bảo vệ:

| Lớp | Đối tượng | Cách thức |
|-----|-----------|-----------|
| 1 | Chrome | Registry policy: DNS-over-HTTPS → AdGuard Family, SafeSearch ON, tắt Guest/Incognito, tắt QUIC |
| 2 | Edge | Tương tự Chrome + ForceBingSafeSearch, tắt InPrivate |
| 3 | Hệ thống (NRPT) | Name Resolution Policy Table: ép toàn bộ DNS qua `94.140.14.15` (AdGuard Family), tồn tại qua thay đổi WiFi |
| 4 | Network adapter | Set DNS `94.140.14.15` trên tất cả adapter (lớp backup) |
| 5 | Firefox | Registry policy `HKLM\...\Mozilla\Firefox` + file `distribution/policies.json`: DoH → AdGuard Family, `trr.mode=3` (DoH only), tắt Private Browsing |

**Tại sao phải tắt QUIC:** Chrome QUIC (HTTP/3) có thể bỏ qua DNS bằng cached connection → vẫn truy cập được site dù DNS đã chặn.

**Kiểm tra:**
- Chrome: `chrome://policy`
- Edge: `edge://policy`
- Firefox: `about:policies`

---

## 5. Cơ chế chạy nền + tự khởi động

### 2 lớp auto-start

| Lớp | Cách thức | Standard user có tắt được? |
|-----|-----------|---------------------------|
| Task Scheduler | Task `WindowsMonitor` chạy `wscript.exe start-monitor.vbs` khi bất kỳ user nào login. Auto-restart 999 lần nếu bị kill (mỗi lần cách 1 phút) | Có thể kill process, nhưng tự chạy lại sau 1 phút |
| Registry `HKLM\Run` | `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run\WindowsMonitor` chạy VBScript wrapper | Standard user **KHÔNG THỂ** xóa key HKLM |

### Tại sao không chạy elevated (quyền Admin)?

Process elevated chạy ở session riêng → không truy cập được desktop của user đang login → `mss` không chụp được màn hình (lỗi `BitBlt: Access Denied`).

### Tại sao không chạy SYSTEM?

`NT AUTHORITY\SYSTEM` chạy ở Session 0 (services) → hoàn toàn không có desktop → `GetForegroundWindow()`, `GetWindowTextW()`, `mss` đều thất bại.

### VBScript wrapper (start-monitor.vbs)

```vbs
Set ws = CreateObject("WScript.Shell")
ws.CurrentDirectory = "C:\...\windows-monitor"
ws.Run """C:\...\pythonw.exe"" -m monitor", 0, False
```

Flag `0` = cửa sổ ẩn hoàn toàn. Dù dùng `python.exe` (thay vì `pythonw.exe`) cũng không hiện CMD window.

---

## 6. Quy trình triển khai cho khách hàng

### Bước 1: Chuẩn bị Telegram Bot

1. Mở Telegram, tìm `@BotFather`
2. Gửi `/newbot`, đặt tên (vd: "Monitor Con Tôi")
3. Lưu lại **Bot Token** (dạng `123456:ABC-DEF...`)
4. Gửi tin nhắn bất kỳ cho bot vừa tạo
5. Truy cập `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Tìm `"chat":{"id": 987654321}` → đây là **Chat ID**

### Bước 2: Cài đặt trên máy khách hàng

**Cách A: Có Python trên máy (dev/test)**

```
1. Copy thư mục windows-monitor vào máy
2. Mở CMD với quyền Administrator
3. cd C:\đường-dẫn\windows-monitor
4. copy config.example.json config.json
5. Sửa config.json: điền bot_token và chat_id
6. Chạy: install.bat
7. Chạy: setup-safe-dns.bat
```

**Cách B: Đóng gói (không cần Python trên máy khách)**

Trên máy dev:
```
1. cd windows-monitor
2. build.bat     (cần Python + PyInstaller)
3. Zip thư mục dist\WindowsMonitor\
4. Gửi file zip cho khách hàng
```

Trên máy khách:
```
1. Giải nén
2. Click phải install.bat → Run as administrator
3. Nhập Bot Token, Chat ID theo hướng dẫn trên màn hình
4. Click phải setup-safe-dns.bat → Run as administrator
```

### Bước 3: Tạo tài khoản Standard cho con

```
Settings → Accounts → Family → Add account → Standard User
```

**Bắt buộc phải là Standard User** — nếu con dùng tài khoản Admin thì:
- Có thể xóa registry key HKLM\Run
- Có thể xóa Task Scheduler task
- Có thể gỡ DNS policy
- Có thể sửa hosts file

### Bước 4: Kiểm tra hoạt động

| Kiểm tra | Lệnh/cách |
|----------|-----------|
| Process đang chạy? | `tasklist \| findstr python` |
| Telegram nhận "started"? | Xem chat Telegram |
| Screenshot hoạt động? | Gửi `/screenshot` trên Telegram |
| Block website? | Gửi `/block tiktok.com` → mở tiktok.com trên Chrome |
| Giới hạn app? | Gửi `/limit chrome 1` (1 phút) → mở Chrome |
| DNS bảo vệ? | Truy cập site 18+ → bị AdGuard chặn |
| Chrome policy? | Mở `chrome://policy` |
| Log file? | `type C:\...\windows-monitor\monitor.log` |

---

## 7. Xử lý sự cố

### App không chạy

```bash
# Xem log
type monitor.log

# Chạy trực tiếp để thấy lỗi
cd C:\...\windows-monitor
python -m monitor
```

### Screenshot failed

- **"Access is denied"**: Process đang chạy elevated hoặc ở session khác → kiểm tra Task Scheduler, đảm bảo dùng `BUILTIN\Users` group, `RunLevel Limited`
- **"User idle"**: Bình thường — không chụp khi không có thao tác

### Telegram Conflict

```
Conflict: terminated by other getUpdates request
```

Có 2 instance monitor chạy cùng lúc:
```bash
taskkill /f /im pythonw.exe
taskkill /f /im python.exe
# Chờ 5s rồi start lại 1 instance
schtasks /run /tn "WindowsMonitor"
```

Code có single-instance lock (`monitor.lock`) để tự xử lý, nhưng nếu 2 instance start cùng lúc trước khi lock kịp tạo thì vẫn có thể xung đột.

### DNS không hoạt động với Firefox

1. Kiểm tra `about:policies` trong Firefox → phải thấy policy active
2. Nếu không thấy → chạy lại `setup-safe-dns.bat` với quyền Admin
3. Restart Firefox sau khi chạy script

### Con tắt được monitor

Bình thường — process chạy ở quyền Standard user nên có thể bị kill trong Task Manager. Tuy nhiên:
- Task Scheduler tự restart sau 1 phút
- Registry Run key tự start lại khi login lần sau
- Con không thể xóa được 2 cơ chế auto-start này (cần quyền Admin)

---

## 8. Gỡ cài đặt

Chạy với quyền Administrator:

```bash
uninstall.bat        # Gỡ Task Scheduler + Registry + hosts + IFEO
undo-safe-dns.bat    # Gỡ DNS protection
```

Xóa thủ công:
- `config.json` (chứa bot token)
- `usage.db` (dữ liệu sử dụng)
- `monitor.log` (log file)
- Toàn bộ thư mục `windows-monitor`

---

## 9. Lưu ý quan trọng cho đội triển khai

1. **Bảo mật bot token:** `config.json` chứa bot token — không commit lên git, không chia sẻ. Nếu lộ, revoke token qua @BotFather
2. **Quyền Admin khi cài:** `install.bat`, `setup-safe-dns.bat` đều cần chạy với quyền Administrator
3. **Tài khoản Standard bắt buộc:** Nếu con dùng Admin account, toàn bộ cơ chế bảo vệ đều vô hiệu
4. **Kiểm tra sau cài:** Luôn test `/screenshot` và `/block` sau khi cài xong
5. **Cập nhật:** Khi cần cập nhật code, copy file mới → chạy lại `install.bat`
6. **PyInstaller build:** Nếu dùng bản đóng gói, phải build lại khi thay đổi code
7. **Firewall:** Đảm bảo máy không chặn kết nối tới `api.telegram.org`
8. **Multiple monitors:** `mss` chụp toàn bộ virtual screen (tất cả monitor ghép lại)
