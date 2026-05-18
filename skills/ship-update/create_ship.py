#!/usr/bin/env python3
"""Create empty Craneship card in vault/ships/craneship/{NAME}.md from template.

Reads JSON from stdin or --json arg.

Input schema:
{
  "name":    "RIANA",                        # required, canonical filename
  "aliases": ["Riana", "Риана", "Рианой"]    # optional, list of strings
}

Behavior:
  - Refuses if file already exists in vault/ships/{name}.md OR vault/ships/craneship/{name}.md
  - Creates vault/ships/craneship/{NAME}.md with empty Tier-1 and Tier-2 sections
  - Sets `last_updated:` to today's date
  - Atomic write via NamedTemporaryFile + os.replace

Exit 0 on success, 2 on validation error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

WORKSPACE = Path("/home/apbrandom/.openclaw/workspace")
CRANESHIP_DIR = WORKSPACE / "vault" / "ships" / "craneship"
MYSHIP_DIR = WORKSPACE / "vault" / "ships" / "myship"
SHIPS_DIRS = [MYSHIP_DIR, CRANESHIP_DIR]

NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def validate(payload: dict[str, Any]) -> None:
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        die("⚠ 'name' required, non-empty string")
    if not NAME_RE.match(name.strip()):
        die(f"⚠ 'name' must be UPPERCASE_WITH_UNDERSCORES, got {name!r}")
    aliases = payload.get("aliases", [])
    if not isinstance(aliases, list) or not all(isinstance(a, str) and a.strip() for a in aliases):
        die("⚠ 'aliases' must be list of non-empty strings")


def render_card(name: str, aliases: list[str]) -> str:
    today = date.today().isoformat()
    alias_lines = "".join(f"  - {a.strip()}\n" for a in aliases) if aliases else ""
    return (
        "---\n"
        f"name: {name}\n"
        f"aliases:\n{alias_lines}"
        "type:\n"
        "year:\n"
        "imo:\n"
        "flag:\n"
        "owner:\n"
        f"last_updated: {today}\n"
        "---\n"
        "\n"
        f"# {name}\n"
        "\n"
        "## Текущее положение\n"
        "<!-- Tier 1: обновляется update_ship.py из forwarded-сообщений -->\n"
        "- Позиция: [не задано]\n"
        "- Статус: [не задано]\n"
        "- Обновлено: [не задано]\n"
        "\n"
        "## История событий\n"
        "\n"
        "## Технические характеристики\n"
        "<!-- Tier 2: накапливается из сообщений, синтезируется ночью -->\n"
        "\n"
        "### Главная энергетическая установка\n"
        "- Двигатель: [не задано]\n"
        "- Производитель: [не задано]\n"
        "- Серийный номер: [не задано]\n"
        "- Мощность: [не задано]\n"
        "\n"
        "### Вспомогательные механизмы\n"
        "[не задано]\n"
        "\n"
        "### Палубное оборудование\n"
        "[не задано]\n"
        "\n"
        "## Документы\n"
        "[ссылки на PDF, сертификаты, АПП]\n"
    )


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


def create(payload: dict[str, Any]) -> str:
    validate(payload)
    name = payload["name"].strip()
    aliases = payload.get("aliases", [])

    for d in SHIPS_DIRS:
        p = d / f"{name}.md"
        if p.exists():
            die(f"⚠ ship already exists: {p.relative_to(WORKSPACE)}")

    CRANESHIP_DIR.mkdir(parents=True, exist_ok=True)
    target = CRANESHIP_DIR / f"{name}.md"
    atomic_write(target, render_card(name, aliases))
    return f"✓ {name} created ({target.relative_to(WORKSPACE)})"


def main() -> None:
    ap = argparse.ArgumentParser(description="Create empty Craneship ship card")
    ap.add_argument("--json", help="JSON payload (if absent, read from stdin)")
    args = ap.parse_args()

    raw = args.json if args.json is not None else sys.stdin.read()
    if not raw.strip():
        die("⚠ empty input")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"⚠ invalid JSON: {e}")

    print(create(payload))


if __name__ == "__main__":
    main()
