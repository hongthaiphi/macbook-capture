import subprocess
import logging
import winreg
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from . import db
from .reporter import build_daily_report
from .screenshot import capture_and_send
from . import limiter

logger = logging.getLogger(__name__)

HOSTS_PATH = Path(r"C:\Windows\System32\drivers\etc\hosts")
MARKER = "# MONITOR-BLOCKED"

CHROME_BLOCKLIST_KEY = r"SOFTWARE\Policies\Google\Chrome\URLBlocklist"
EDGE_BLOCKLIST_KEY = r"SOFTWARE\Policies\Microsoft\Edge\URLBlocklist"


def _flush_dns():
    try:
        subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        logger.exception("DNS flush failed")


def _sync_hosts_file():
    blocked = db.list_blocked_domains()

    try:
        content = HOSTS_PATH.read_text(encoding="utf-8")
    except PermissionError:
        logger.error("Cannot read hosts file — run as administrator")
        return False

    clean_lines = [line for line in content.splitlines() if MARKER not in line]

    for domain in blocked:
        clean_lines.append(f"127.0.0.1 {domain} {MARKER}")
        clean_lines.append(f"127.0.0.1 www.{domain} {MARKER}")

    try:
        HOSTS_PATH.write_text("\n".join(clean_lines) + "\n", encoding="utf-8")
        _flush_dns()
        return True
    except PermissionError:
        logger.error("Cannot write hosts file — run as administrator")
        return False


def _sync_browser_blocklist():
    """Write blocked domains to Chrome and Edge URLBlocklist registry policies.

    This works even when browsers use DNS-over-HTTPS, because URLBlocklist
    is enforced at the browser level before any network request is made.
    """
    blocked = db.list_blocked_domains()

    for key_path in (CHROME_BLOCKLIST_KEY, EDGE_BLOCKLIST_KEY):
        try:
            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        except FileNotFoundError:
            pass
        except PermissionError:
            logger.error("Cannot write registry — run as administrator")
            return False

        if not blocked:
            continue

        try:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            for i, domain in enumerate(blocked, start=1):
                winreg.SetValueEx(key, str(i), 0, winreg.REG_SZ, domain)
            winreg.CloseKey(key)
        except PermissionError:
            logger.error("Cannot write registry — run as administrator")
            return False

    logger.info("Browser URLBlocklist updated: %d domains", len(blocked))
    return True


def _sync_all():
    """Sync both hosts file (for non-browser apps) and browser policies."""
    hosts_ok = _sync_hosts_file()
    browser_ok = _sync_browser_blocklist()
    return hosts_ok or browser_ok


class TelegramBot:
    def __init__(self, config: dict):
        self.config = config
        self.chat_id = str(config["chat_id"])
        self.app: Application | None = None

    def _is_admin(self, update: Update) -> bool:
        return str(update.effective_chat.id) == self.chat_id

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        await update.message.reply_text(
            "🖥️ Windows Monitor Bot\n\n"
            "Commands:\n"
            "/block <domain> — Block a website\n"
            "/unblock <domain> — Unblock a website\n"
            "/list — List blocked domains\n"
            "/limit <app> <minutes> — Daily time limit\n"
            "/unlimit <app> — Remove time limit\n"
            "/limits — Show all limits & status\n"
            "/deny <app> — Block app immediately\n"
            "/allow <app> — Unblock app immediately\n"
            "/apps — List known app shortcuts\n"
            "/report — Get today's usage report\n"
            "/screenshot — Take a screenshot now\n"
            "/help — Show this message"
        )

    async def _cmd_block(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        if not context.args:
            await update.message.reply_text("Usage: /block <domain>\nExample: /block tiktok.com")
            return

        domain = context.args[0].lower().strip()
        if db.add_blocked_domain(domain):
            ok = _sync_all()
            if ok:
                await update.message.reply_text(f"✅ Blocked: {domain}\n(hosts file + Chrome/Edge policy)")
            else:
                await update.message.reply_text(f"⚠️ Added to DB but system update failed (need admin rights)")
        else:
            await update.message.reply_text(f"ℹ️ Already blocked: {domain}")

    async def _cmd_unblock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        if not context.args:
            await update.message.reply_text("Usage: /unblock <domain>")
            return

        domain = context.args[0].lower().strip()
        if db.remove_blocked_domain(domain):
            _sync_all()
            await update.message.reply_text(f"✅ Unblocked: {domain}")
        else:
            await update.message.reply_text(f"ℹ️ Not in blocked list: {domain}")

    async def _cmd_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        blocked = db.list_blocked_domains()
        if blocked:
            text = "🚫 Blocked domains:\n" + "\n".join(f"  • {d}" for d in blocked)
        else:
            text = "✅ No domains blocked"
        await update.message.reply_text(text)

    async def _cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        report = build_daily_report()
        await update.message.reply_text(report)

    async def _cmd_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        await update.message.reply_text("📸 Capturing...")
        ok = await capture_and_send(self.app.bot, self.chat_id)
        if not ok:
            await update.message.reply_text("❌ Screenshot failed")

    async def _cmd_limit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /limit <app> <minutes>\nExample: /limit chrome 120")
            return

        name = context.args[0]
        exe = limiter.resolve_app_name(name)
        if not exe:
            await update.message.reply_text(f"❌ Unknown app: {name}\nDùng /apps để xem danh sách")
            return

        try:
            minutes = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Số phút phải là số nguyên")
            return

        db.set_app_limit(exe, minutes * 60)
        await update.message.reply_text(f"✅ Giới hạn {exe}: {minutes} phút/ngày")

    async def _cmd_unlimit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        if not context.args:
            await update.message.reply_text("Usage: /unlimit <app>")
            return

        name = context.args[0]
        exe = limiter.resolve_app_name(name)
        if not exe:
            await update.message.reply_text(f"❌ Unknown app: {name}")
            return

        limiter._unblock_app_launch(exe)
        if db.remove_app_limit(exe):
            await update.message.reply_text(f"✅ Đã xóa giới hạn: {exe}")
        else:
            await update.message.reply_text(f"ℹ️ {exe} không có giới hạn")

    async def _cmd_limits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        limits = db.get_all_app_limits()
        if not limits:
            await update.message.reply_text("✅ Chưa đặt giới hạn nào")
            return

        lines = ["⏰ App Limits:\n"]
        for exe in limits:
            lines.append(limiter.get_app_status(exe))
            lines.append("")
        await update.message.reply_text("\n".join(lines))

    async def _cmd_deny(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        if not context.args:
            await update.message.reply_text("Usage: /deny <app>\nExample: /deny chrome")
            return

        name = context.args[0]
        exe = limiter.resolve_app_name(name)
        if not exe:
            await update.message.reply_text(f"❌ Unknown app: {name}")
            return

        limiter._kill_process(exe)
        limiter._block_app_launch(exe)
        await update.message.reply_text(f"🚫 Đã chặn {exe}")

    async def _cmd_allow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        if not context.args:
            await update.message.reply_text("Usage: /allow <app>")
            return

        name = context.args[0]
        exe = limiter.resolve_app_name(name)
        if not exe:
            await update.message.reply_text(f"❌ Unknown app: {name}")
            return

        limiter._unblock_app_launch(exe)
        await update.message.reply_text(f"✅ Đã mở lại {exe}")

    async def _cmd_apps(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        await update.message.reply_text(limiter.list_known_apps())

    def build_app(self) -> Application:
        self.app = Application.builder().token(self.config["bot_token"]).build()

        handlers = [
            CommandHandler("start", self._cmd_start),
            CommandHandler("help", self._cmd_start),
            CommandHandler("block", self._cmd_block),
            CommandHandler("unblock", self._cmd_unblock),
            CommandHandler("list", self._cmd_list),
            CommandHandler("limit", self._cmd_limit),
            CommandHandler("unlimit", self._cmd_unlimit),
            CommandHandler("limits", self._cmd_limits),
            CommandHandler("deny", self._cmd_deny),
            CommandHandler("allow", self._cmd_allow),
            CommandHandler("apps", self._cmd_apps),
            CommandHandler("report", self._cmd_report),
            CommandHandler("screenshot", self._cmd_screenshot),
        ]
        for h in handlers:
            self.app.add_handler(h)

        return self.app
