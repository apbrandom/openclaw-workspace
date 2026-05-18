#!/usr/bin/env python3
"""Add or update a location entry in vault/locations.md.

Reads JSON from stdin or --json arg:
{
  "location": "Причал 24",          # canonical name
  "port":     "Порт Кавказ",        # parent port/region
  "aliases":  ["24 причал", "у 24"]  # optional, list of strings
}

Behavior:
  - If location row exists in table → update port and merge aliases (no duplicates)
  - If not exists → append new row
  - Atomic write via tempfile + os.replace
  - Idempotent: same input twice = same result

Markdown table format (3 columns): | Локация | Порт/район | Алиасы |
Header line is "| Локация" — script preserves it. First data row is after the
separator `|---|---|---|` line.

Exit 0 on success, 2 on validation error.
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

LOCATIONS_FILE = Path("/home/apbrandom/.openclaw/workspace/vault/locations.md")


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def validate(payload: dict[str, Any]) -> None:
    loc = payload.get("location")
    port = payload.get("port")
    if not isinstance(loc, str) or not loc.strip():
        die("⚠ 'location' required, non-empty string")
    if not isinstance(port, str) or not port.strip():
        die("⚠ 'port' required, non-empty string")
    aliases = payload.get("aliases", [])
    if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
        die("⚠ 'aliases' must be list of strings")


def parse_table(lines: list[str]) -> tuple[int, int, list[dict]]:
    """Find data rows of the table. Returns (start_idx, end_idx, rows)."""
    header_idx = None
    sep_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("| Локация"):
            header_idx = i
        elif header_idx is not None and re.match(r"^\|[-:\s|]+\|$", line.strip()):
            sep_idx = i
            break
    if header_idx is None or sep_idx is None:
        die("⚠ locations.md table header not found")

    start = sep_idx + 1
    end = start
    rows: list[dict] = []
    while end < len(lines):
        line = lines[end].strip()
        if not line.startswith("|"):
            break
        # split into 3 columns (ignore leading/trailing | and trim)
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) >= 3:
            rows.append({
                "location": parts[0],
                "port": parts[1],
                "aliases": [a.strip() for a in parts[2].split(",") if a.strip()],
                "_line_idx": end,
            })
        end += 1
    return start, end, rows


def render_row(loc: str, port: str, aliases: list[str]) -> str:
    alias_str = ", ".join(aliases)
    return f"| {loc} | {port} | {alias_str} |"


def merge_aliases(old: list[str], new: list[str]) -> list[str]:
    seen = []
    for a in old + new:
        a = a.strip()
        if a and a not in seen:
            seen.append(a)
    return seen


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


def add_location(payload: dict[str, Any]) -> str:
    validate(payload)
    loc = payload["location"].strip()
    port = payload["port"].strip()
    aliases = [a.strip() for a in payload.get("aliases", []) if a.strip()]

    if not LOCATIONS_FILE.exists():
        die(f"⚠ {LOCATIONS_FILE} not found")

    body = LOCATIONS_FILE.read_text(encoding="utf-8")
    lines = body.split("\n")
    start, end, rows = parse_table(lines)

    # Find existing row by location name (case-insensitive)
    existing = None
    for row in rows:
        if row["location"].lower() == loc.lower():
            existing = row
            break

    if existing:
        # Preserve canonical spelling from first occurrence.
        # If new input differs in case, add the variant to aliases.
        canonical = existing["location"]
        merged_aliases = merge_aliases(existing["aliases"], aliases)
        if loc != canonical and loc not in merged_aliases:
            merged_aliases.append(loc)
        new_row = render_row(canonical, port, merged_aliases)
        if new_row.strip() == lines[existing["_line_idx"]].strip():
            return f"✓ no change: {canonical}"
        lines[existing["_line_idx"]] = new_row
        action = "updated"
        loc = canonical
    else:
        new_row = render_row(loc, port, aliases)
        lines.insert(end, new_row)
        action = "added"

    atomic_write(LOCATIONS_FILE, "\n".join(lines))
    return f"✓ {action}: {loc} → {port}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Add/update location in vault/locations.md")
    ap.add_argument("--json", help="JSON payload (if absent, read from stdin)")
    args = ap.parse_args()

    raw = args.json if args.json is not None else sys.stdin.read()
    if not raw.strip():
        die("⚠ empty input")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"⚠ invalid JSON: {e}")

    print(add_location(payload))


if __name__ == "__main__":
    main()
