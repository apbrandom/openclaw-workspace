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

STATUS_FIELDS = {
    "position":       "Позиция:",
    "status":         "Статус:",
    "tugboat":        "Буксир:",
    "last_update_dt": "Обновлено:",
}


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


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


def append_events(body: str, events: list[str]) -> str:
    if not events:
        return body

    header_re = re.compile(r"^## История событий[ \t]*$", re.MULTILINE)
    m = header_re.search(body)
    if not m:
        die("⚠ '## История событий' section missing")

    # Find end of section: next "## " header, or EOF
    section_start = m.end()
    next_header = re.search(r"^## ", body[section_start:], re.MULTILINE)
    section_end = section_start + next_header.start() if next_header else len(body)

    section_text = body[section_start:section_end]
    existing = set(line.strip() for line in section_text.splitlines() if line.strip())

    new_lines = []
    for ev in events:
        bullet = f"- {ev.strip()}"
        if bullet not in existing:
            new_lines.append(bullet)
            existing.add(bullet)

    if not new_lines:
        return body

    # Ensure section ends with single blank line before next header (or EOF)
    section_trimmed = section_text.rstrip("\n")
    rebuilt = section_trimmed + "\n" + "\n".join(new_lines) + "\n"
    if next_header:
        rebuilt += "\n"
    return body[:section_start] + rebuilt + body[section_end:]


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
    """Expand bare HH:MM events to YYYY-MM-DD HH:MM using last_update_dt or today."""
    from datetime import date as _date
    if last_update_dt and DT_RE.match(last_update_dt):
        date_prefix = last_update_dt.split(" ", 1)[0]
    else:
        date_prefix = _date.today().isoformat()
    result = []
    for ev in events:
        m = TIME_ONLY_RE.match(ev.strip())
        if m:
            result.append(f"{date_prefix} {m.group(1)}{m.group(2)}")
        else:
            result.append(ev)
    return result


def update(payload: dict[str, Any]) -> str:
    validate(payload)
    name = payload["name"].strip()
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
    return f"✓ {name} updated ({ship_path.relative_to(WORKSPACE)})"


def main() -> None:
    ap = argparse.ArgumentParser(description="Tier-1 ship card update")
    ap.add_argument("--json", help="JSON payload (if absent, read from stdin)")
    args = ap.parse_args()

    raw = args.json if args.json is not None else sys.stdin.read()
    if not raw.strip():
        die("⚠ empty input")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"⚠ invalid JSON: {e}")

    print(update(payload))


if __name__ == "__main__":
    main()
