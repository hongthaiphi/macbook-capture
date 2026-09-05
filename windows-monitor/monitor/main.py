import asyncio
import logging
import signal
import sys

from datetime import date

from .config import load_config
from .db import init_db
from .tracker import Tracker, get_idle_seconds
from .screenshot import ScreenshotLoop
from .blocker import TelegramBot, _sync_all
from .reporter import ReportScheduler, send_blocked_alert
from .limiter import reset_daily_blocks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main():
    config = load_config()
    init_db()

    logger.info("Starting Windows Monitor...")

    telegram_bot = TelegramBot(config)
    app = telegram_bot.build_app()

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    bot = app.bot
    chat_id = str(config["chat_id"])

    async def on_blocked(app_name: str, domain: str):
        await send_blocked_alert(bot, chat_id, app_name, domain)

    # Wrapper to call async from sync context
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

    await app.updater.stop()
    await app.stop()
    await app.shutdown()

    await bot.send_message(chat_id=chat_id, text="🔴 Windows Monitor stopped")
    logger.info("Shutdown complete")


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
