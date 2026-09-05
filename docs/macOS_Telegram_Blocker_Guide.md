# Tài liệu Kiến trúc & Hướng dẫn Hệ thống Telegram Domain Blocker trên macOS

## 1. Tổng quan Dự án (Project Overview)

Hệ thống kết hợp giữa **Telegram Bot (Python)** và dịch vụ hệ thống **macOS `LaunchDaemons`** để quản lý việc chặn/mở chặn các tên miền (domain) từ xa.

- **Mục đích:** Chặn truy cập web cấp hệ thống thông qua việc sửa đổi file `/etc/hosts` và làm sạch cache DNS (`mDNSResponder`).
- **Cơ chế chạy:** Chạy dưới dạng dịch vụ ngầm với quyền `root` (System-level), hoạt động 24/7 ngay khi bật máy Mac, độc lập hoàn toàn với việc người dùng có đăng nhập (login) hay chưa.

---

## 2. Kiến trúc & Cơ chế Hoạt động (System Architecture)

### 2.1. Luồng xử lý file `/etc/hosts` an toàn

- Để tránh làm hỏng file hệ thống gốc nếu gặp sự cố, bot duy trì một file tạm tại `/tmp/hosts.blocked`.
- Khi thực hiện lệnh chặn/mở chặn:
  1. Kiểm tra sự tồn tại của `/tmp/hosts.blocked` (nếu chưa có, tự sao chép từ `/etc/hosts`).
  2. Thao tác thêm/xóa dòng chứa IP `127.0.0.1 <domain>` và `127.0.0.1 www.<domain>` trên file `/tmp/hosts.blocked`.
  3. Sao chép đè từ `/tmp/hosts.blocked` sang `/etc/hosts`.
  4. Thực thi `killall -HUP mDNSResponder` để làm sạch DNS Cache, áp dụng thay đổi ngay lập tức.

### 2.2. Khởi chạy vĩnh viễn với `LaunchDaemons`

- **Vị trí file cấu hình:** `/Library/LaunchDaemons/com.phihongthai.tgbot.plist`
- **Quyền sở hữu (Permissions):** `root:wheel`, CHMOD `644`.
- **Phân biệt `LaunchAgents` vs `LaunchDaemons`:**
  - `LaunchAgents`: Chỉ chạy khi user đã đăng nhập GUI.
  - `LaunchDaemons`: Chạy ngay từ khi boot máy (ngay cả ở màn hình Lock Screen/Login Screen).

---

## 3. Mã nguồn Python Hoàn chỉnh (`/Users/phihongthai/telegram_blocker.py`)

```python
import os
import shutil
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# === CẤU HÌNH BẢO MẬT ===
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Thay bằng Token Bot Telegram
YOUR_CHAT_ID = 123456789          # Thay bằng Chat ID kiểu số của Admin

TMP_HOSTS = "/tmp/hosts.blocked"
SYSTEM_HOSTS = "/etc/hosts"

def is_admin(update: Update) -> bool:
    return update.effective_user.id == YOUR_CHAT_ID

def ensure_tmp_hosts_exists():
    if not os.path.exists(TMP_HOSTS):
        shutil.copyfile(SYSTEM_HOSTS, TMP_HOSTS)

def apply_changes():
    shutil.copyfile(TMP_HOSTS, SYSTEM_HOSTS)
    subprocess.run(["killall", "-HUP", "mDNSResponder"], check=True)

async def start_or_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    help_text = (
        "🛠 **DANH SÁCH LỆNH ĐIỀU KHIỂN BOT**\n\n"
        "🚫 `/block domain.com` — Chặn truy cập tên miền\n"
        "✅ `/unblock domain.com` — Mở chặn tên miền\n"
        "📋 `/list` — Xem toàn bộ danh sách tên miền đang bị chặn\n"
        "ℹ️ `/help` — Hiển thị trợ giúp này"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    if not context.args:
        await update.message.reply_text("⚠️ Vui lòng nhập tên miền.\nVí dụ: `/block youtube.com`", parse_mode="Markdown")
        return

    domain = context.args[0].lower().strip()

    try:
        ensure_tmp_hosts_exists()

        with open(TMP_HOSTS, "r") as f:
            content = f.read()

        lines_to_add = f"\n127.0.0.1 {domain}\n127.0.0.1 www.{domain}\n"

        if f"127.0.0.1 {domain}" in content:
            await update.message.reply_text(f"ℹ️ `{domain}` đã bị chặn từ trước rồi.", parse_mode="Markdown")
            return

        with open(TMP_HOSTS, "a") as f:
            f.write(lines_to_add)

        apply_changes()
        await update.message.reply_text(f"🚫 Đã chặn thành công: `{domain}`", parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Thất bại khi chặn: {e}")

async def unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    if not context.args:
        await update.message.reply_text("⚠️ Vui lòng nhập tên miền.\nVí dụ: `/unblock youtube.com`", parse_mode="Markdown")
        return

    domain = context.args[0].lower().strip()

    try:
        ensure_tmp_hosts_exists()

        with open(TMP_HOSTS, "r") as f:
            lines = f.readlines()

        new_lines = [line for line in lines if domain not in line]

        if len(lines) == len(new_lines):
            await update.message.reply_text(f"ℹ️ Không tìm thấy `{domain}` trong danh sách chặn.", parse_mode="Markdown")
            return

        with open(TMP_HOSTS, "w") as f:
            f.writelines(new_lines)

        apply_changes()
        await update.message.reply_text(f"✅ Đã mở chặn thành công: `{domain}`", parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Thất bại khi mở chặn: {e}")

async def list_blocked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    try:
        ensure_tmp_hosts_exists()

        with open(TMP_HOSTS, "r") as f:
            lines = f.readlines()

        blocked_domains = set()

        for line in lines:
            line = line.strip()
            if line.startswith("#") or not line:
                continue

            parts = line.split()
            if len(parts) >= 2 and parts[0] == "127.0.0.1":
                dom = parts[1].lower()
                if dom not in ["localhost", "broadcasthost"]:
                    if dom.startswith("www."):
                        dom = dom[4:]
                    blocked_domains.add(dom)

        if not blocked_domains:
            await update.message.reply_text("🎉 Hiện tại không có tên miền nào bị chặn.")
            return

        sorted_domains = sorted(list(blocked_domains))
        msg = "📋 **DANH SÁCH TÊN MIỀN ĐANG BỊ CHẶN:**\n\n"
        for idx, dom in enumerate(sorted_domains, 1):
            msg += f"{idx}. `{dom}`\n"

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Không thể lấy danh sách: {e}")

def main():
    ensure_tmp_hosts_exists()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_or_help))
    app.add_handler(CommandHandler("help", start_or_help))
    app.add_handler(CommandHandler("block", block))
    app.add_handler(CommandHandler("unblock", unblock))
    app.add_handler(CommandHandler("list", list_blocked))
    app.add_handler(CommandHandler("show", list_blocked))

    print("Bot chặn domain đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
```
