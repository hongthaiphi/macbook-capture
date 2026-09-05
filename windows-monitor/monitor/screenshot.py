import asyncio
import logging
import tempfile
from pathlib import Path

import mss
import mss.tools

logger = logging.getLogger(__name__)


async def capture_and_send(bot, chat_id: str) -> bool:
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # full virtual screen
            img = sct.grab(monitor)

            tmp = Path(tempfile.gettempdir()) / "monitor_screenshot.png"
            mss.tools.to_png(img.rgb, img.size, output=str(tmp))

        with open(tmp, "rb") as photo:
            await bot.send_photo(chat_id=chat_id, photo=photo)

        tmp.unlink(missing_ok=True)
        logger.debug("Screenshot sent")
        return True
    except Exception:
        logger.exception("Screenshot failed")
        return False


class ScreenshotLoop:
    def __init__(self, config: dict, bot, get_idle_seconds):
        self.interval = config["screenshot_interval_seconds"]
        self.idle_timeout = config["idle_timeout_seconds"]
        self.bot = bot
        self.chat_id = str(config["chat_id"])
        self.get_idle = get_idle_seconds
        self._running = False
        self.count = 0

    async def run(self):
        self._running = True
        logger.info("Screenshot loop started (every %ds)", self.interval)

        while self._running:
            await asyncio.sleep(self.interval)
            if not self._running:
                break

            idle = self.get_idle()
            if idle > self.idle_timeout:
                logger.debug("User idle, skipping screenshot")
                continue

            ok = await capture_and_send(self.bot, self.chat_id)
            if ok:
                self.count += 1

    def stop(self):
        self._running = False
