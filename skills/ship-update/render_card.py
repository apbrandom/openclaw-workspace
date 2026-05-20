#!/usr/bin/env python3
"""Render Telegram HTML ship card (Шаблон 2) from vault file.

Usage:
  echo '{"name":"MODUS"}' | python render_card.py
  python render_card.py --name MODUS
  python render_card.py --name Модус --auto-resolve

Output: ready HTML string for Telegram (parse_mode=HTML).
Exit 0 on success, non-zero on error (single line to stderr).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/home/apbrandom/.openclaw/workspace")
SHIPS_DIRS = [
    WORKSPACE / "vault" / "ships" / "myship",
    WORKSPACE / "vault" / "ships" / "craneship",
]

STATUS_RULES = [
    (["якор", "рейд"],                                              "⚓", "На якоре"),
    (["погрузк"],                                                   "🟡", "Погрузка"),
    (["выгрузк", "разгрузк"],                                       "🟡", "Выгрузка"),
    (["на ходу", "отошёл", "следует", "вышел", "переход", "в пути"], "🟢", "На ходу"),
]

FULL_TS_RE  = re.compile(r"^- (\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}) — (.+)")
DATE_ONLY_RE = re.compile(r"^- (\d{4})-(\d{2})-(\d{2}) — (.+)")
WIKI_RE     = re.compile(r"^- \[\[")

POSITION_RE = re.compile(r"^- Позиция:\s*(.+)",   re.MULTILINE)
STATUS_RE   = re.compile(r"^- Статус:\s*(.+)",     re.MULTILINE)
TUGBOAT_RE  = re.compile(r"^- Буксир:\s*(.+)",     re.MULTILINE)
UPDATED_RE  = re.compile(r"^- Обновлено:\s*(.+)",  re.MULTILINE)
FM_NAME_RE  = re.compile(r"^name:[ \t]*(.+)",       re.MULTILINE)
FM_TYPE_RE  = re.compile(r"^type:[ \t]*(\S.*)",     re.MULTILINE)


def die(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def find_ship_file(name: str) -> Path:
    if "/" in name or ".." in name:
        die(f"⚠ invalid ship name: {name!r}")
    for d in SHIPS_DIRS:
        p = d / f"{name}.md"
        if p.is_file():
            return p
    known = [f.stem for d in SHIPS_DIRS if d.is_dir() for f in sorted(d.glob("*.md"))]
    die(f"⚠ ship not found: {name}.md  (known: {', '.join(known)})")


def try_resolve(name: str) -> str:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "resolve_ship", Path(__file__).parent / "resolve_ship.py"
        )
        mod = importlib.util.module_from_spec(spec)   # type: ignore[arg-type]
        spec.loader.exec_module(mod)                  # type: ignore[union-attr]
        result = mod.resolve(name)
        if result.get("found"):
            return result["canonical"]
    except Exception:
        pass
    return name


def get_section(body: str, header: str) -> str:
    m = re.search(rf"^## {re.escape(header)}[ \t]*$", body, re.MULTILINE)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^## ", body[start:], re.MULTILINE)
    return body[start: start + nxt.start() if nxt else len(body)]


def status_emoji_label(raw: str) -> tuple[str, str]:
    sl = raw.lower()
    for keywords, emoji, label in STATUS_RULES:
        if any(k in sl for k in keywords):
            return emoji, label
    return "⬜", "Неизвестно"


def _parse_dt(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None


def relative_time(dt_str: str) -> str:
    dt = _parse_dt(dt_str)
    if not dt:
        return dt_str.strip()
    mins = int((datetime.now() - dt).total_seconds() / 60)
    if mins < 2:   return "только что"
    if mins < 60:  return f"{mins} мин назад"
    h = mins // 60
    if h < 24:     return f"{h} ч назад"
    return f"{h // 24} дн назад"


def freshness_emoji(dt_str: str) -> str:
    dt = _parse_dt(dt_str)
    if not dt:
        return "⬜"
    mins = int((datetime.now() - dt).total_seconds() / 60)
    if mins < 60:  return "🟢"
    if mins < 240: return "🟡"
    return "🟠"


def parse_events(section: str, limit: int = 5) -> list[tuple[str, str]]:
    """Return up to `limit` events newest-first as (sort_key, display_line)."""
    results: list[tuple[str, str]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line or WIKI_RE.match(line):
            continue
        m = FULL_TS_RE.match(line)
        if m:
            yr, mo, dy, hh, mm, text = m.groups()
            results.append((f"{yr}-{mo}-{dy} {hh}:{mm}", f"• {dy}.{mo} {hh}:{mm}  {text}"))
            continue
        m = DATE_ONLY_RE.match(line)
        if m:
            yr, mo, dy, text = m.groups()
            results.append((f"{yr}-{mo}-{dy} 00:00", f"• {dy}.{mo}  {text}"))
    results.sort(key=lambda x: x[0])
    return results[-limit:][::-1]  # newest first


def render(name: str, auto_resolve: bool = False) -> str:
    if auto_resolve:
        name = try_resolve(name)
    path = find_ship_file(name)
    body = path.read_text(encoding="utf-8")

    # Frontmatter
    m = FM_NAME_RE.search(body)
    display_name = m.group(1).strip() if m else name
    m = FM_TYPE_RE.search(body)
    ship_type = m.group(1).strip() if m else ""

    # Текущее положение
    pos_sec = get_section(body, "Текущее положение")
    m = POSITION_RE.search(pos_sec)
    position = m.group(1).strip() if m else "—"
    m = STATUS_RE.search(pos_sec)
    status_raw = m.group(1).strip() if m else ""
    m = TUGBOAT_RE.search(pos_sec)
    tugboat = m.group(1).strip() if m else ""
    m = UPDATED_RE.search(pos_sec)
    updated_str = m.group(1).strip() if m else ""

    s_emoji, s_label = status_emoji_label(status_raw)

    # История событий
    events = parse_events(get_section(body, "История событий"), limit=5)

    # Fallback updated_str from newest event
    if not updated_str and events:
        updated_str = events[0][0]

    # Line 1
    type_part = f" · {ship_type}" if ship_type else ""
    line1 = f"🚢 <b>{display_name}</b>{type_part}        {s_emoji} {s_label}"

    # Blockquote
    bq: list[str] = [f"📍 {position}"]
    if tugboat and tugboat not in ("", "-", "[не задано]"):
        bq.append(f"🛥 Буксир: {tugboat}")
    bq.append("")
    bq.append("📋 Журнал событий")
    if events:
        bq.extend(display for _, display in events)
    else:
        bq.append("(нет данных)")

    # Footer
    if updated_str:
        footer = f"{freshness_emoji(updated_str)} Обновлено {relative_time(updated_str)}"
    else:
        footer = "⬜ Обновлено —"

    return f"{line1}\n\n<blockquote>{chr(10).join(bq)}</blockquote>\n\n{footer}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Render Telegram HTML ship card (Шаблон 2)")
    ap.add_argument("--name",         help="Ship name (canonical or alias)")
    ap.add_argument("--json",         help='JSON payload: {"name":"MODUS"}')
    ap.add_argument("--auto-resolve", action="store_true",
                    help="Resolve alias via resolve_ship.py")
    args = ap.parse_args()

    if args.json:
        try:
            payload = json.loads(args.json)
        except json.JSONDecodeError as e:
            die(f"⚠ invalid JSON: {e}")
        name         = payload.get("name", "").strip()
        auto_resolve = payload.get("auto_resolve", False) or args.auto_resolve
    elif args.name:
        name         = args.name.strip()
        auto_resolve = args.auto_resolve
    else:
        raw = sys.stdin.read().strip()
        if not raw:
            die("⚠ no input: provide --name, --json, or pipe JSON")
        try:
            payload      = json.loads(raw)
            name         = payload.get("name", "").strip()
            auto_resolve = payload.get("auto_resolve", False) or args.auto_resolve
        except json.JSONDecodeError:
            name         = raw
            auto_resolve = args.auto_resolve

    if not name:
        die("⚠ 'name' is required")

    print(render(name, auto_resolve=auto_resolve))


if __name__ == "__main__":
    main()
