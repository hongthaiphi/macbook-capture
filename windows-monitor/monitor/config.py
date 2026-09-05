import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def get_base_dir() -> Path:
    """Return the project root directory — works for both dev and PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()


def load_config() -> dict:
    config_path = BASE_DIR / "config.json"
    logger.debug("Looking for config at: %s", config_path)
    logger.debug("BASE_DIR: %s", BASE_DIR)
    logger.debug("CWD: %s", os.getcwd())

    if not config_path.exists():
        logger.error("config.json not found at %s", config_path)
        print(f"ERROR: config.json not found at {config_path}")
        print("Copy config.example.json to config.json and fill in your Telegram bot token and chat ID.")
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    required = ["bot_token", "chat_id"]
    for key in required:
        val = cfg.get(key, "")
        if not val or val.startswith("YOUR_"):
            logger.error("'%s' in config.json is not set.", key)
            print(f"ERROR: '{key}' in config.json is not set.")
            sys.exit(1)

    cfg.setdefault("poll_interval_seconds", 5)
    cfg.setdefault("screenshot_interval_seconds", 60)
    cfg.setdefault("daily_report_hour", 22)
    cfg.setdefault("idle_timeout_seconds", 120)

    logger.info("Config loaded from %s", config_path)
    return cfg
