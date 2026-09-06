import asyncio
import logging
import logging.handlers
import os
import signal
import sys

from datetime import date

# Setup logging FIRST, before any other module import
# so all modules get the configured handlers
from .config import BASE_DIR

_log_file = str(BASE_DIR / "monitor.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(
            _log_file, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        ),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

logger.info("=" * 50)
logger.info("Windows Monitor starting up")
logger.info("BASE_DIR: %s", BASE_DIR)
logger.info("Log file: %s", _log_file)
logger.info("CWD: %s", os.getcwd())
logger.info("Python: %s", sys.executable)
logger.info("Frozen: %s", getattr(sys, "frozen", False))
logger.info("=" * 50)

# Single-instance lock using Windows named mutex (kernel-level, no race condition)
_mutex_handle = None

def _acquire_lock():
    global _mutex_handle
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        _mutex_handle = kernel32.CreateMutexW(None, True, "Global\\WindowsMonitorSingleInstance")
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            logger.warning("Another instance is already running. Exiting.")
            kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
            return False
        logger.info("Mutex acquired (PID %d)", os.getpid())
        return True
    return True

def _release_lock():
    global _mutex_handle
    if _mutex_handle and sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.ReleaseMutex(_mutex_handle)
        kernel32.CloseHandle(_mutex_handle)
        _mutex_handle = None

from .config import load_config
from .db import init_db
from .tracker import Tracker, get_idle_seconds
from .screenshot import ScreenshotLoop
from .blocker import TelegramBot, _sync_all
from .reporter import ReportScheduler, send_blocked_alert
from .limiter import reset_daily_blocks


async def main():
    config = load_config()
    init_db()
    logger.info("DB path: %s", str(BASE_DIR / "usage.db"))

    logger.info("Starting Telegram bot...")

    telegram_bot = TelegramBot(config)
    app = telegram_bot.build_app()

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    bot = app.bot
    chat_id = str(config["chat_id"])

    async def on_blocked(app_name: str, domain: str):
        await send_blocked_alert(bot, chat_id, app_name, domain)

    loop = asyncio.get_event_loop()

    def on_blocked_sync(app_name: str, domain: str):
        asyncio.run_coroutine_threadsafe(
            send_blocked_alert(bot, chat_id, app_name, domain), loop
        )

    def on_limit_exceeded(alert_msg: str):
        asyncio.run_coroutine_threadsafe(
            bot.send_message(chat_id=chat_id, text=alert_msg), loop
        )

    tracker = Tracker(config, on_blocked_domain=on_blocked_sync, on_limit_exceeded=on_limit_exceeded)
    screenshot_loop = ScreenshotLoop(config, bot, get_idle_seconds)
    report_scheduler = ReportScheduler(config, bot)

    _sync_all()

    await bot.send_message(chat_id=chat_id, text="🟢 Windows Monitor started")
    logger.info("Telegram 'started' message sent")

    async def midnight_reset_loop():
        last_date = date.today()
        while True:
            await asyncio.sleep(60)
            today = date.today()
            if today != last_date:
                logger.info("Midnight reset: unblocking all limited apps")
                reset_daily_blocks()
                last_date = today

    tasks = [
        asyncio.create_task(tracker.run()),
        asyncio.create_task(screenshot_loop.run()),
        asyncio.create_task(report_scheduler.run()),
        asyncio.create_task(midnight_reset_loop()),
    ]
    logger.info("All 4 tasks created and running")

    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        tracker.stop()
        screenshot_loop.stop()
        report_scheduler.stop()
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: _signal_handler())

    logger.info("All systems running. Press Ctrl+C to stop.")
    await stop_event.wait()

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    try:
        await bot.send_message(chat_id=chat_id, text="🔴 Windows Monitor stopped")
    except Exception:
        logger.debug("Could not send stop message", exc_info=True)

    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    logger.info("Shutdown complete")


def run():
    if not _acquire_lock():
        return
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("Fatal error")
        raise
    finally:
        _release_lock()


if __name__ == "__main__":
    run()
