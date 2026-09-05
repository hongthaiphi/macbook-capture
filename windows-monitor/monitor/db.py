import sqlite3
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "usage.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            app_name TEXT NOT NULL,
            window_title TEXT,
            domain TEXT,
            duration_seconds INTEGER DEFAULT 5
        );

        CREATE TABLE IF NOT EXISTS blocked_domains (
            domain TEXT PRIMARY KEY,
            blocked_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS daily_reports (
            date TEXT PRIMARY KEY,
            sent_at TEXT,
            total_seconds INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_usage_domain ON usage_log(domain);
    """)
    conn.close()


def log_usage(app_name: str, window_title: str, domain: str | None, duration: int = 5):
    conn = get_conn()
    conn.execute(
        "INSERT INTO usage_log (timestamp, app_name, window_title, domain, duration_seconds) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), app_name, window_title, domain, duration),
    )
    conn.commit()
    conn.close()


def get_daily_summary(target_date: date | None = None) -> dict:
    if target_date is None:
        target_date = date.today()

    date_prefix = target_date.isoformat()
    conn = get_conn()

    total = conn.execute(
        "SELECT COALESCE(SUM(duration_seconds), 0) FROM usage_log WHERE timestamp LIKE ?",
        (f"{date_prefix}%",),
    ).fetchone()[0]

    app_rows = conn.execute(
        """SELECT app_name, SUM(duration_seconds) as total_sec
           FROM usage_log WHERE timestamp LIKE ?
           GROUP BY app_name ORDER BY total_sec DESC LIMIT 10""",
        (f"{date_prefix}%",),
    ).fetchall()

    site_rows = conn.execute(
        """SELECT domain, SUM(duration_seconds) as total_sec
           FROM usage_log WHERE timestamp LIKE ? AND domain IS NOT NULL
           GROUP BY domain ORDER BY total_sec DESC LIMIT 10""",
        (f"{date_prefix}%",),
    ).fetchall()

    screenshot_count = conn.execute(
        "SELECT COUNT(*) FROM daily_reports WHERE date = ?",
        (date_prefix,),
    ).fetchone()[0]

    conn.close()

    return {
        "date": date_prefix,
        "total_seconds": total,
        "top_apps": [(r["app_name"], r["total_sec"]) for r in app_rows],
        "top_sites": [(r["domain"], r["total_sec"]) for r in site_rows],
        "screenshot_count": screenshot_count,
    }


def add_blocked_domain(domain: str) -> bool:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO blocked_domains (domain, blocked_at) VALUES (?, ?)",
            (domain, datetime.now().isoformat()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_blocked_domain(domain: str) -> bool:
    conn = get_conn()
    cursor = conn.execute("DELETE FROM blocked_domains WHERE domain = ?", (domain,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def list_blocked_domains() -> list[str]:
    conn = get_conn()
    rows = conn.execute("SELECT domain FROM blocked_domains ORDER BY blocked_at").fetchall()
    conn.close()
    return [r["domain"] for r in rows]


def is_domain_blocked(domain: str) -> bool:
    if not domain:
        return False
    conn = get_conn()
    blocked = list_blocked_domains()
    conn.close()
    return any(domain == d or domain.endswith(f".{d}") for d in blocked)


def mark_daily_report_sent(target_date: date, total_seconds: int):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO daily_reports (date, sent_at, total_seconds) VALUES (?, ?, ?)",
        (target_date.isoformat(), datetime.now().isoformat(), total_seconds),
    )
    conn.commit()
    conn.close()
