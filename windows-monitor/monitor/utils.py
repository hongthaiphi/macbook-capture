import re

BROWSER_SUFFIXES = {
    "chrome.exe": " - Google Chrome",
    "msedge.exe": " - Microsoft Edge",
    "brave.exe": " - Brave",
    "firefox.exe": " — Mozilla Firefox",
    "opera.exe": " - Opera",
    "vivaldi.exe": " - Vivaldi",
}

BROWSERS = set(BROWSER_SUFFIXES.keys())

DOMAIN_PATTERN = re.compile(
    r"(?:^|[\s/])([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)"
)


def is_browser(process_name: str) -> bool:
    return process_name.lower() in BROWSERS


def extract_domain_from_title(process_name: str, window_title: str) -> str | None:
    if not window_title:
        return None

    proc = process_name.lower()
    if proc not in BROWSERS:
        return None

    suffix = BROWSER_SUFFIXES.get(proc, "")
    page_title = window_title
    if suffix and window_title.endswith(suffix):
        page_title = window_title[: -len(suffix)]

    # New Tab / blank pages
    skip_titles = {"New Tab", "New tab", "Tab mới", "Start Page", ""}
    if page_title.strip() in skip_titles:
        return None

    match = DOMAIN_PATTERN.search(page_title)
    if match:
        return match.group(1).lower()

    # Many sites show "Page Title" without domain — try common patterns
    # "YouTube", "Facebook", etc. map to known domains
    known_map = {
        "youtube": "youtube.com",
        "facebook": "facebook.com",
        "instagram": "instagram.com",
        "twitter": "twitter.com",
        "tiktok": "tiktok.com",
        "reddit": "reddit.com",
        "github": "github.com",
        "google": "google.com",
        "gmail": "mail.google.com",
        "zalo": "zalo.me",
    }
    title_lower = page_title.lower().strip()
    for keyword, domain in known_map.items():
        if title_lower.startswith(keyword):
            return domain

    return None


def format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes:02d}m"


def make_bar(fraction: float, width: int = 14) -> str:
    filled = round(fraction * width)
    return "█" * filled + "░" * (width - filled)
