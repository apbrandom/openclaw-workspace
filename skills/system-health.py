#!/usr/bin/env python3
"""system-health.py — nightly deterministic health check (cron: system-health-nightly, 02:07).

Does all mechanics itself: temp cleanup, SQLite size, disk usage, port check,
and appends results to today's daily memory note.

Output: one summary line; lines starting with "ALERT:" mean Vadim must be notified.
Usage: python3 system-health.py [--dry-run]
"""

import glob
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

DAILY_DIR = "/home/apbrandom/.openclaw/workspace/memory"
SQLITE_PATH = "/home/apbrandom/.openclaw/memory/main.sqlite"
HOME_PATH = "/home/apbrandom"
LOOPBACK_PORTS = ("11434", "18789", "18791")
SQLITE_LIMIT_MB = 500
DISK_LIMIT_PCT = 85
TEMP_MAX_AGE_SEC = 3600


def cleanup_temp(dry_run: bool) -> int:
    removed = 0
    now = time.time()
    for path in glob.glob("/tmp/page-*.png") + glob.glob("/tmp/*.pdf"):
        try:
            if now - os.path.getmtime(path) > TEMP_MAX_AGE_SEC:
                if not dry_run:
                    os.remove(path)
                removed += 1
        except OSError:
            pass
    return removed


def sqlite_size_mb() -> int:
    try:
        return os.path.getsize(SQLITE_PATH) // (1024 * 1024)
    except OSError:
        return -1


def disk_usage_pct() -> int:
    usage = shutil.disk_usage(HOME_PATH)
    return round(usage.used / usage.total * 100)


def non_loopback_listeners() -> list[str]:
    out = subprocess.run(["ss", "-tln"], capture_output=True, text=True).stdout
    bad = []
    for line in out.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 4:
            continue
        local = fields[3]
        addr, _, port = local.rpartition(":")
        if port in LOOPBACK_PORTS and addr not in ("127.0.0.1", "[::1]"):
            bad.append(local)
    return bad


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    now = datetime.now()

    removed = cleanup_temp(dry_run)
    sqlite_mb = sqlite_size_mb()
    disk_pct = disk_usage_pct()
    bad_ports = non_loopback_listeners()

    alerts = []
    if sqlite_mb > SQLITE_LIMIT_MB:
        alerts.append(f"ALERT: SQLite {sqlite_mb} MB (>{SQLITE_LIMIT_MB} MB)")
    if disk_pct > DISK_LIMIT_PCT:
        alerts.append(f"ALERT: диск {disk_pct}% (>{DISK_LIMIT_PCT}%)")
    if bad_ports:
        alerts.append(f"ALERT: порты слушают не на loopback: {', '.join(bad_ports)}")

    section = (
        f"\n## SysHealth [{now:%H:%M}]\n\n"
        f"- Temp cleanup: {removed} файлов удалено\n"
        f"- SQLite: {sqlite_mb} MB\n"
        f"- Диск: {disk_pct}%\n"
        f"- Порты (loopback only): {', '.join(bad_ports) if bad_ports else 'OK'}\n"
        + ("".join(f"- {a}\n" for a in alerts))
    )
    if not dry_run:
        daily_path = os.path.join(DAILY_DIR, f"{now:%Y-%m-%d}.md")
        with open(daily_path, "a", encoding="utf-8") as f:
            f.write(section)

    print(
        f"SysHealth {now:%Y-%m-%d %H:%M}{' (dry-run)' if dry_run else ''}: "
        f"cleanup={removed} sqlite={sqlite_mb}MB disk={disk_pct}% "
        f"ports={', '.join(bad_ports) if bad_ports else 'OK'}"
    )
    for a in alerts:
        print(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
