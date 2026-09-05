# Changelog — Windows Monitor

## 2026-09-05

### Bug Fix: install.bat Task Scheduler không chạy monitor

**Triệu chứng:** `python -m monitor` chạy OK, nhưng sau `install.bat` thì monitor không hoạt động. `tasklist | findstr monitor` không thấy process. File `monitor.log` trống.

**Nguyên nhân gốc:**
1. `schtasks /create` không hỗ trợ set working directory — Task Scheduler mặc định chạy từ `C:\Windows\System32`
2. `config.py` và `db.py` dùng `Path(__file__).parent.parent` để tìm `config.json` và `usage.db` — đường dẫn tương đối này chỉ đúng khi working directory là thư mục project
3. PowerShell set working directory phía sau bị `>nul 2>&1` nuốt lỗi, có thể thất bại âm thầm

**Files đã sửa:**

| File | Thay đổi |
|------|----------|
| `monitor/config.py` | Thêm `BASE_DIR` — dùng `Path(__file__).resolve()` (dev) hoặc `sys.executable` (PyInstaller) để tính đường dẫn tuyệt đối. Thêm debug logging. |
| `monitor/db.py` | Dùng `BASE_DIR` từ config thay vì tự tính `Path(__file__).parent.parent` |
| `monitor/main.py` | Log level → DEBUG. Log startup info (BASE_DIR, CWD, Python path, frozen). Wrap `run()` trong try/except log fatal error. Log file đặt tại `BASE_DIR/monitor.log` |
| `install.bat` | Dùng PowerShell `Register-ScheduledTask` thay `schtasks /create` để set WorkingDirectory chắc chắn. Thêm debug output, verify task, kiểm tra process sau 3s |
| `build.bat` | Sửa entry point PyInstaller: `monitor\__main__.py` → `run_monitor.py` (fix ImportError relative import) |
| `run_monitor.py` | File mới — entry point cho PyInstaller, dùng absolute import |

### Enhancement: File logging

Thêm `RotatingFileHandler` ghi ra `monitor.log` cạnh thư mục project (hoặc cạnh exe khi đóng gói). Max 2MB/file, giữ 3 backup. Mute log spam từ httpx/httpcore/telegram.

### Bug Fix: Firefox DNS không hoạt động

**Triệu chứng:** `setup-safe-dns.bat` chạy xong nhưng Firefox vẫn truy cập bình thường, không qua AdGuard DNS.

**Nguyên nhân:** Script chỉ ghi `policies.json` vào `C:\Program Files\Mozilla Firefox` — nếu Firefox cài ở đường dẫn khác thì bỏ qua.

**Sửa trong `setup-safe-dns.bat`:**
- Thêm registry policy (`HKLM\SOFTWARE\Policies\Mozilla\Firefox`) — Firefox 78+ đọc trực tiếp, không phụ thuộc đường dẫn cài đặt
- Tìm Firefox ở nhiều vị trí (Program Files, x86, LocalAppData)
- Vẫn giữ policies.json làm backup

**Sửa trong `undo-safe-dns.bat`:**
- Xóa registry key `Mozilla\Firefox`
- Xóa policies.json ở tất cả đường dẫn

---

## Hướng dẫn cài đặt / chạy lại

### Trên máy dev (có Python)

```
cd C:\đường-dẫn\windows-monitor

# 1. Test thử (xem log trực tiếp trên console)
python -m monitor

# 2. Cài vào Task Scheduler (chạy với quyền Admin)
install.bat

# 3. Cài DNS protection (chạy với quyền Admin)
setup-safe-dns.bat

# 4. Kiểm tra
tasklist | findstr pythonw
type monitor.log
```

### Đóng gói cho máy con (không cần Python)

```
cd C:\đường-dẫn\windows-monitor

# 1. Build (cần Python + PyInstaller trên máy dev)
build.bat

# 2. Copy thư mục dist\WindowsMonitor\ sang máy con

# 3. Trên máy con (chạy với quyền Admin)
install.bat        # Hỏi Bot Token, Chat ID, admin credentials
setup-safe-dns.bat # Cài DNS protection

# 4. Kiểm tra
tasklist | findstr monitor.exe
type monitor\monitor.log
```

### Debug khi không chạy

```
# Xem log
type monitor.log

# Chạy trực tiếp để thấy lỗi trên console
# (dev mode)
python -m monitor

# (PyInstaller mode — từ thư mục WindowsMonitor)
monitor\monitor.exe

# Kiểm tra Task Scheduler
schtasks /query /tn "WindowsMonitor" /v

# Kiểm tra Firefox DNS
# Mở about:policies trong Firefox
```
