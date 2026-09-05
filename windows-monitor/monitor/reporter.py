import asyncio
import logging
from datetime import date, datetime

from . import db
from .utils import format_duration, make_bar

logger = logging.getLogger(__name__)


def build_daily_report(target_date: date | None = None) -> str:
    summary = db.get_daily_summary(target_date)
    d = summary["date"]
    total = summary["total_seconds"]

    lines = [
        f"📊 Báo cáo ngày {d}",
        "",
        f"🖥️ Tổng thời gian: {format_duration(total)}",
    ]

    if summary["top_apps"]:
        lines.append("")
        lines.append("📱 Top Apps:")
        for app_name, sec in summary["top_apps"][:7]:
            frac = sec / total if total > 0 else 0
            pct = round(frac * 100)
            bar = make_bar(frac)
            name = app_name.replace(".exe", "")
            lines.append(f"  {name:<15} {format_duration(sec)}  {bar} {pct}%")

    if summary["top_sites"]:
        lines.append("")
        lines.append("🌐 Top Websites:")
        site_total = sum(s for _, s in summary["top_sites"])
        for domain, sec in summary["top_sites"][:7]:
            frac = sec / site_total if site_total > 0 else 0
            pct = round(frac * 100)
            bar = make_bar(frac)
            lines.append(f"  {domain:<15} {format_duration(sec)}  {bar} {pct}%")

    blocked = db.list_blocked_domains()
    if blocked:
        lines.append("")
        lines.append(f"🚫 Blocked domains: {len(blocked)}")

    limits = db.get_all_app_limits()
    if limits:
        lines.append("")
        lines.append("⏰ App Limits:")
        for exe, limit_sec in limits.items():
            used = db.get_app_usage_today(exe)
            remaining = max(0, limit_sec - used)
            status = "🔴" if remaining == 0 else "🟢"
            name = exe.replace(".exe", "")
            lines.append(
                f"  {status} {name:<15} {format_duration(used)}/{format_duration(limit_sec)} (còn {format_duration(remaining)})"
            )

    return "\n".join(lines)


async def send_blocked_alert(bot, chat_id: str, app_name: str, domain: str):
    now = datetime.now().strftime("%H:%M:%S")
    text = (
        f"🚫 Blocked site detected!\n"
        f"Domain: {domain}\n"
        f"App: {app_name}\n"
        f"Time: {now}"
    )
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception:
        logger.exception("Failed to send blocked alert")


class ReportScheduler:
    def __init__(self, config: dict, bot):
        self.report_hour = config["daily_report_hour"]
        self.bot = bot
        self.chat_id = str(config["chat_id"])
        self._running = False
        self._last_report_date = None

    async def run(self):
        self._running = True
        logger.info("Report scheduler started (daily at %d:00)", self.report_hour)

        while self._running:
            await asyncio.sleep(60)
            if not self._running:
                break

            now = datetime.now()
            today = now.date()

            if now.hour == self.report_hour and self._last_report_date != today:
                await self._send_daily(today)
                self._last_report_date = today

    def stop(self):
        self._running = False

    async def _send_daily(self, target_date: date):
        report = build_daily_report(target_date)
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=report)
            summary = db.get_daily_summary(target_date)
            db.mark_daily_report_sent(target_date, summary["total_seconds"])
            logger.info("Daily report sent for %s", target_date)
        except Exception:
            logger.exception("Failed to send daily report")

    async def send_now(self):
        report = build_daily_report()
        await self.bot.send_message(chat_id=self.chat_id, text=report)
