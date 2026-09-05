import json
import sys
from pathlib import Path


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.json"
    if not config_path.exists():
        print(f"ERROR: config.json not found at {config_path}")
        print("Copy config.example.json to config.json and fill in your Telegram bot token and chat ID.")
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    required = ["bot_token", "chat_id"]
    for key in required:
        val = cfg.get(key, "")
        if not val or val.startswith("YOUR_"):
            print(f"ERROR: '{key}' in config.json is not set.")
            sys.exit(1)

    cfg.setdefault("poll_interval_seconds", 5)
    cfg.setdefault("screenshot_interval_seconds", 60)
    cfg.setdefault("daily_report_hour", 22)
    cfg.setdefault("idle_timeout_seconds", 120)
    return cfg
