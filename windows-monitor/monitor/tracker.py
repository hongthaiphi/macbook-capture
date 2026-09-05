import ctypes
import ctypes.wintypes as wintypes
import asyncio
import logging

import psutil

from . import db
from .utils import extract_domain_from_title
from .limiter import enforce_app_limit

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_idle_seconds() -> float:
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    user32.GetLastInputInfo(ctypes.byref(lii))
    millis = kernel32.GetTickCount() - lii.dwTime
    return millis / 1000.0


def get_active_window_info() -> tuple[str, str] | None:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    try:
        process = psutil.Process(pid.value)
        app_name = process.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return app_name, ""

    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return app_name, buf.value


class Tracker:
    def __init__(self, config: dict, on_blocked_domain=None, on_limit_exceeded=None):
        self.poll_interval = config["poll_interval_seconds"]
        self.idle_timeout = config["idle_timeout_seconds"]
        self.on_blocked_domain = on_blocked_domain
        self.on_limit_exceeded = on_limit_exceeded
        self._last_app = None
        self._last_domain = None
        self._running = False

    async def run(self):
        self._running = True
        logger.info("Tracker started (poll every %ds)", self.poll_interval)

        while self._running:
            try:
                self._tick()
            except Exception:
                logger.exception("Tracker tick error")
            await asyncio.sleep(self.poll_interval)

    def stop(self):
        self._running = False

    def _tick(self):
        idle = get_idle_seconds()
        if idle > self.idle_timeout:
            return

        info = get_active_window_info()
        if info is None:
            return

        app_name, window_title = info
        domain = extract_domain_from_title(app_name, window_title)

        db.log_usage(app_name, window_title, domain, duration=self.poll_interval)

        if domain and db.is_domain_blocked(domain):
            if self.on_blocked_domain and (app_name, domain) != (self._last_app, self._last_domain):
                self.on_blocked_domain(app_name, domain)

        alert = enforce_app_limit(app_name)
        if alert and self.on_limit_exceeded:
            self.on_limit_exceeded(alert)

        self._last_app = app_name
        self._last_domain = domain
