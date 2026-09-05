# Windows Monitor — Design Document

## Mục tiêu

Hệ thống parental control cho Windows, điều khiển qua Telegram:
- Track thời gian sử dụng từng app và website (mọi browser)
- Chụp screenshot định kỳ, gửi qua Telegram
- Block/unblock website từ xa qua Telegram bot
- Gửi daily report + real-time alert khi truy cập site bị cấm

## Kiến trúc

```
┌─────────────────────────────────────────────────┐
│                   main.py (asyncio)              │
│                                                  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ Tracker  │  │ Screenshot   │  │ Report    │  │
│  │ (5s poll)│  │ Loop (60s)   │  │ Scheduler │  │
│  └────┬─────┘  └──────┬───────┘  └─────┬─────┘  │
│       │               │                │         │
│       ▼               ▼                ▼         │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    │
│  │ SQLite  │    │ Telegram │    │ Telegram │    │
│  │  (db)   │    │ sendPhoto│    │ sendMsg  │    │
│  └─────────┘    └──────────┘    └──────────┘    │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │ Telegram Bot (long-polling)               │   │
│  │ /block /unblock /list /report /screenshot │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

## Cách detect website trên mọi browser

Không dùng extension — đọc **window title** của browser process:

| Browser | Process | Title format |
|---------|---------|-------------|
| Chrome | chrome.exe | `Page Title - Google Chrome` |
| Edge | msedge.exe | `Page Title - Microsoft Edge` |
| Firefox | firefox.exe | `Page Title — Mozilla Firefox` |
| Brave | brave.exe | `Page Title - Brave` |
| Opera | opera.exe | `Page Title - Opera` |

**Flow:**
1. `GetForegroundWindow()` → hwnd
2. `GetWindowThreadProcessId()` → pid → process name
3. Nếu process là browser → strip suffix → extract domain từ title
4. `GetLastInputInfo()` → skip nếu user idle > 120s

## Cách block website

1. Lưu domain vào SQLite (`blocked_domains` table)
2. Ghi `127.0.0.1 domain # MONITOR-BLOCKED` vào `C:\Windows\System32\drivers\etc\hosts`
3. `ipconfig /flushdns`
4. Khi tracker detect user mở blocked domain → gửi real-time alert qua Telegram

## Yêu cầu hệ thống

- Windows 10/11
- Python 3.10+
- Chạy với quyền **Administrator** (cần để sửa hosts file)
- Telegram Bot Token + Chat ID

## Cài đặt

1. Copy `config.example.json` → `config.json`, điền bot token và chat ID
2. Chạy `install.bat` (as Administrator)
3. Monitor tự khởi động khi login

## Hạn chế

- Window title không luôn chứa domain (incognito, một số SPA)
- Cần quyền admin để sửa hosts file
- Nếu user biết → có thể kill process hoặc xóa scheduled task
- Không track được nội dung cụ thể (chỉ biết domain)
