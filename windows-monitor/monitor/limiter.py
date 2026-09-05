import subprocess
import logging
import winreg

from . import db
from .utils import format_duration

logger = logging.getLogger(__name__)

IFEO_BASE = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"

KNOWN_APPS = {
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "firefox": "firefox.exe",
    "brave": "brave.exe",
    "opera": "opera.exe",
    "minecraft": "Minecraft.Windows.exe",
    "roblox": "RobloxPlayerBeta.exe",
    "steam": "steam.exe",
    "epic": "EpicGamesLauncher.exe",
    "discord": "Discord.exe",
    "zalo": "Zalo.exe",
    "telegram": "Telegram.exe",
}


def resolve_app_name(name: str) -> str | None:
    lower = name.lower().strip()
    if lower in KNOWN_APPS:
        return KNOWN_APPS[lower]
    if lower.endswith(".exe"):
        return lower
    return None


def _kill_process(exe_name: str):
    try:
        subprocess.run(
            ["taskkill", "/f", "/im", exe_name],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        logger.exception("Failed to kill %s", exe_name)


def _block_app_launch(exe_name: str):
    """Use IFEO Debugger trick to prevent an app from launching."""
    key_path = f"{IFEO_BASE}\\{exe_name}"
    try:
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        winreg.SetValueEx(key, "Debugger", 0, winreg.REG_SZ, "nul")
        winreg.CloseKey(key)
        logger.info("Blocked launch: %s", exe_name)
        return True
    except PermissionError:
        logger.error("Cannot set IFEO for %s — need administrator", exe_name)
        return False


def _unblock_app_launch(exe_name: str):
    """Remove IFEO Debugger entry to allow app to launch again."""
    key_path = f"{IFEO_BASE}\\{exe_name}"
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_ALL_ACCESS)
        try:
            winreg.DeleteValue(key, "Debugger")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        try:
            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        except OSError:
            pass
        logger.info("Unblocked launch: %s", exe_name)
        return True
    except FileNotFoundError:
        return True
    except PermissionError:
        logger.error("Cannot remove IFEO for %s — need administrator", exe_name)
        return False


def is_app_blocked(exe_name: str) -> bool:
    key_path = f"{IFEO_BASE}\\{exe_name}"
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, "Debugger")
            return val == "nul"
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        return False


def enforce_app_limit(exe_name: str) -> str | None:
    """Check if app has exceeded its daily limit. Returns status message if exceeded."""
    limits = db.get_all_app_limits()
    if exe_name not in limits:
        return None

    limit_seconds = limits[exe_name]
    used_seconds = db.get_app_usage_today(exe_name)

    if used_seconds >= limit_seconds:
        if not is_app_blocked(exe_name):
            _kill_process(exe_name)
            _block_app_launch(exe_name)
            remaining = "0m"
            return (
                f"⏰ Hết thời gian!\n"
                f"App: {exe_name}\n"
                f"Limit: {format_duration(limit_seconds)}/ngày\n"
                f"Đã dùng: {format_duration(used_seconds)}"
            )
    else:
        if is_app_blocked(exe_name):
            _unblock_app_launch(exe_name)

    return None


def enforce_all_limits() -> list[str]:
    """Check all limited apps. Returns list of alert messages for newly exceeded limits."""
    alerts = []
    limits = db.get_all_app_limits()

    for exe_name in limits:
        msg = enforce_app_limit(exe_name)
        if msg:
            alerts.append(msg)

    return alerts


def reset_daily_blocks():
    """Unblock all apps that were blocked due to daily limits. Called at midnight."""
    limits = db.get_all_app_limits()
    for exe_name in limits:
        if is_app_blocked(exe_name):
            _unblock_app_launch(exe_name)
            logger.info("Daily reset: unblocked %s", exe_name)


def get_app_status(exe_name: str) -> str:
    limits = db.get_all_app_limits()
    used = db.get_app_usage_today(exe_name)
    blocked = is_app_blocked(exe_name)

    if exe_name in limits:
        limit = limits[exe_name]
        remaining = max(0, limit - used)
        status = "🔴 BLOCKED" if blocked else "🟢 Active"
        return (
            f"{exe_name}: {status}\n"
            f"  Đã dùng: {format_duration(used)} / {format_duration(limit)}\n"
            f"  Còn lại: {format_duration(remaining)}"
        )
    else:
        return f"{exe_name}: không giới hạn (đã dùng {format_duration(used)} hôm nay)"


def list_known_apps() -> str:
    lines = ["Tên tắt → process:"]
    for short, exe in sorted(KNOWN_APPS.items()):
        lines.append(f"  {short} → {exe}")
    return "\n".join(lines)
