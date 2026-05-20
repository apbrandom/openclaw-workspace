#!/usr/bin/env python3
"""Deterministic Tier-1 ship card update.

Reads JSON from stdin or --json arg, patches vault/ships/{name}.md or
vault/ships/craneship/{name}.md.

Input schema (all fields optional except `name`):
{
  "name":           "TISA",                   # canonical filename without .md
  "position":       "Причал 24",              # район/локация из списка AGENTS.md
  "status":         "грузовые",               # операционный статус из списка
  "tugboat":        "SIROKO",                 # обязательно для type=баржа
  "last_update_dt": "2026-05-17 13:00",       # YYYY-MM-DD HH:MM
  "events":         ["2026-05-17 12:30 — Сироко увела", ...],
  "type":           "буксир"                  # frontmatter type:, free string
}

Behavior:
  - Validates ship file exists in vault/ships/ or vault/ships/craneship/
  - Replaces TWO lines under ## Текущее положение (full-value replace)
  - Appends events to ## История событий (one bullet per item)
  - Updates `last_updated:` in YAML frontmatter (date portion only)
  - Atomic write via NamedTemporaryFile + os.replace
  - Idempotent: same input twice = same result

Exit 0 on success, non-zero on validation error. Single-line message to
stderr on error, single line to stdout on success.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime as _datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path("/home/apbrandom/.openclaw/workspace")
SHIPS_DIRS = [
    WORKSPACE / "vault" / "ships" / "myship",
    WORKSPACE / "vault" / "ships" / "craneship",
]

DT_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_ONLY_RE = re.compile(r"^(\d{2}:\d{2})([ \t]*[—\-][ \t]*.*)")
BULLET_TS_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) — (.{1,30})")
VALID_EVENT_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} — .+")

STATUS_FIELDS = {
    "position":       "Позиция:",
    "status":         "Статус:",
    "tugboat":        "Буксир:",
    "last_update_dt": "Обновлено:",
}


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def _try_resolve(name: str) -> str | None:
    """Try alias/frontmatter resolution via resolve_ship.py. Returns canonical name or None."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "resolve_ship", Path(__file__).parent / "resolve_ship.py"
        )
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        result = mod.resolve(name)
        if result.get("found"):
            return result["canonical"]
    except Exception:
        pass
    return None


def find_ship_file(name: str) -> Path:
    if "/" in name or ".." in name:
        die(f"⚠ invalid ship name: {name!r}")
    for d in SHIPS_DIRS:
        p = d / f"{name}.md"
        if p.is_file():
            return p
    listings = []
    for d in SHIPS_DIRS:
        if d.is_dir():
            listings.extend(sorted(f.stem for f in d.glob("*.md")))
    die(f"⚠ ship file not found: {name}.md (known: {', '.join(listings)})")


def replace_status_field(body: str, marker: str, new_value: str) -> str:
    pattern = re.compile(
        rf"^(- {re.escape(marker)})[ \t]*.*$",
        re.MULTILINE,
    )
    if not pattern.search(body):
        die(f"⚠ status field not found in card: {marker}")
    return pattern.sub(rf"\1 {new_value}", body, count=1)


def _sem_key(bullet: str):
    """Semantic dedup key: (date, time, first-30-chars-normalized). Avoids byte-equal false negatives from unicode glitches."""
    m = BULLET_TS_RE.match(bullet)
    if m:
        text = unicodedata.normalize("NFKC", m.group(3)).lower().strip()
        return (m.group(1), m.group(2), text)
    return bullet


def _sort_section(section_text: str) -> str:
    """Sort timestamped event bullets chronologically; non-timestamped lines stay at top."""
    lines = section_text.splitlines(keepends=True)
    i = len(lines) - 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    trailing = lines[i + 1:]
    content_lines = lines[: i + 1]

    timestamped: list[tuple[_datetime, str]] = []
    other: list[str] = []
    for line in content_lines:
        m = BULLET_TS_RE.match(line)
        if m:
            try:
                dt = _datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M")
                timestamped.append((dt, line))
                continue
            except ValueError:
                pass
        other.append(line)

    timestamped.sort(key=lambda x: x[0])
    return "".join(other + [t[1] for t in timestamped] + trailing)


def append_events(body: str, events: list[str]) -> str:
    if not events:
        return body

    header_re = re.compile(r"^## История событий[ \t]*$", re.MULTILINE)
    m = header_re.search(body)
    if not m:
        die("⚠ '## История событий' section missing")

    section_start = m.end()
    next_header = re.search(r"^## ", body[section_start:], re.MULTILINE)
    section_end = section_start + next_header.start() if next_header else len(body)

    section_text = body[section_start:section_end]
    existing_bullets = [line.strip() for line in section_text.splitlines() if line.strip()]
    existing_keys = {_sem_key(b) for b in existing_bullets}

    new_lines = []
    for ev in events:
        bullet = f"- {ev.strip()}"
        key = _sem_key(bullet)
        if key not in existing_keys:
            new_lines.append(bullet)
            existing_keys.add(key)

    if not new_lines:
        return body

    section_trimmed = section_text.rstrip("\n")
    rebuilt = section_trimmed + "\n" + "\n".join(new_lines) + "\n"
    if next_header:
        rebuilt += "\n"
    return body[:section_start] + _sort_section(rebuilt) + body[section_end:]


def update_frontmatter_date(body: str, date_str: str) -> str:
    fm_re = re.compile(r"^(last_updated:)[ \t]*.*$", re.MULTILINE)
    if not fm_re.search(body):
        die("⚠ 'last_updated:' missing in frontmatter")
    return fm_re.sub(rf"\1 {date_str}", body, count=1)


def update_frontmatter_type(body: str, type_str: str) -> str:
    fm_re = re.compile(r"^(type:)[ \t]*.*$", re.MULTILINE)
    if not fm_re.search(body):
        die("⚠ 'type:' missing in frontmatter")
    return fm_re.sub(rf"\1 {type_str}", body, count=1)


def atomic_write(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def validate(payload: dict[str, Any]) -> None:
    if "name" not in payload or not isinstance(payload["name"], str) or not payload["name"].strip():
        die("⚠ 'name' required, non-empty string")

    dt = payload.get("last_update_dt")
    if dt is not None:
        if not isinstance(dt, str) or not DT_RE.match(dt):
            die(f"⚠ 'last_update_dt' must be 'YYYY-MM-DD HH:MM', got {dt!r}")

    for k in ("position", "status", "tugboat", "type"):
        v = payload.get(k)
        if v is not None and (not isinstance(v, str) or not v.strip()):
            die(f"⚠ '{k}' if set must be non-empty string")

    events = payload.get("events", [])
    if not isinstance(events, list) or not all(isinstance(e, str) and e.strip() for e in events):
        die("⚠ 'events' must be list of non-empty strings")


def _normalize_event_dates(events: list[str], last_update_dt: str | None) -> list[str]:
    """NFKC-normalize, expand bare HH:MM to YYYY-MM-DD HH:MM, validate format."""
    from datetime import date as _date
    if last_update_dt and DT_RE.match(last_update_dt):
        date_prefix = last_update_dt.split(" ", 1)[0]
    else:
        date_prefix = _date.today().isoformat()
    result = []
    for ev in events:
        ev = unicodedata.normalize("NFKC", ev).strip()
        m = TIME_ONLY_RE.match(ev)
        if m:
            ev = f"{date_prefix} {m.group(1)}{m.group(2)}"
        if not VALID_EVENT_RE.match(ev):
            die(f"⚠ invalid event format (expected 'HH:MM — text' or 'YYYY-MM-DD HH:MM — text'): {ev!r}")
        result.append(ev)
    return result


def update(payload: dict[str, Any], auto_resolve: bool = False) -> str:
    validate(payload)
    name = payload["name"].strip()
    if auto_resolve:
        canonical = _try_resolve(name)
        if canonical:
            name = canonical
    ship_path = find_ship_file(name)
    body = ship_path.read_text(encoding="utf-8")

    for key, marker in STATUS_FIELDS.items():
        v = payload.get(key)
        if v is not None:
            body = replace_status_field(body, marker, v.strip())

    events = payload.get("events", [])
    events = _normalize_event_dates(events, payload.get("last_update_dt"))
    body = append_events(body, events)

    # Update frontmatter date from last_update_dt if provided
    dt = payload.get("last_update_dt")
    if dt:
        body = update_frontmatter_date(body, dt.split(" ", 1)[0])

    # Update frontmatter type if provided
    type_str = payload.get("type")
    if type_str:
        body = update_frontmatter_type(body, type_str.strip())

    atomic_write(ship_path, body)
    _refresh_card(name)
    return f"✓ {name} updated ({ship_path.relative_to(WORKSPACE)})"


def _refresh_card(name: str) -> None:
    """Regenerate vault/ship_cards/{name}.html after update. Silent on failure."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "render_card", Path(__file__).parent / "render_card.py"
        )
        mod = importlib.util.module_from_spec(spec)   # type: ignore[arg-type]
        spec.loader.exec_module(mod)                  # type: ignore[union-attr]
        html = mod.render(name)
        cards_dir = WORKSPACE / "vault" / "ship_cards"
        cards_dir.mkdir(parents=True, exist_ok=True)
        (cards_dir / f"{name}.html").write_text(html, encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description="Tier-1 ship card update")
    ap.add_argument("--json", help="JSON payload (if absent, read from stdin)")
    ap.add_argument("--auto-resolve", action="store_true",
                    help="Resolve free-text ship name via aliases/frontmatter if not found directly")
    args = ap.parse_args()

    raw = args.json if args.json is not None else sys.stdin.read()
    if not raw.strip():
        die("⚠ empty input")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"⚠ invalid JSON: {e}")

    print(update(payload, auto_resolve=args.auto_resolve))


if __name__ == "__main__":
    main()
