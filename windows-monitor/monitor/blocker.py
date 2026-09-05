import subprocess
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from . import db
from .reporter import build_daily_report
from .screenshot import capture_and_send

logger = logging.getLogger(__name__)

HOSTS_PATH = Path(r"C:\Windows\System32\drivers\etc\hosts")
MARKER = "# MONITOR-BLOCKED"


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
            ok = _sync_hosts_file()
            if ok:
                await update.message.reply_text(f"✅ Blocked: {domain}")
            else:
                await update.message.reply_text(f"⚠️ Added to DB but hosts file update failed (need admin rights)")
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
            _sync_hosts_file()
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

    def build_app(self) -> Application:
        self.app = Application.builder().token(self.config["bot_token"]).build()

        handlers = [
            CommandHandler("start", self._cmd_start),
            CommandHandler("help", self._cmd_start),
            CommandHandler("block", self._cmd_block),
            CommandHandler("unblock", self._cmd_unblock),
            CommandHandler("list", self._cmd_list),
            CommandHandler("report", self._cmd_report),
            CommandHandler("screenshot", self._cmd_screenshot),
        ]
        for h in handlers:
            self.app.add_handler(h)

        return self.app
