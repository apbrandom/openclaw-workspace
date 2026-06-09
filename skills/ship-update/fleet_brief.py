#!/usr/bin/env python3
"""Fleet Morning Brief — deterministic daily summary for the own fleet (myship/).

Reuses render_card.render() for each ship card and concatenates the rendered
Telegram cards under a dated header. Emits ready Telegram HTML (parse_mode=HTML)
to stdout.

Design: the model does NOT explore the filesystem. This script reads only the
canonical ship cards in vault/ships/myship/ — it never scans vault/events/ and
never guesses filenames. The cron job just runs this and forwards stdout.

Usage:
  python3 fleet_brief.py                 # all myship cards, sorted by name
  python3 fleet_brief.py --names ATLAS_1,TISA
Exit 0 on success, non-zero only if there are no ships at all.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
MYSHIP_DIR = Path("/home/apbrandom/.openclaw/workspace/vault/ships/myship")

SEP = "\n\n– – – – – – – – – –\n\n"

WEEKDAYS_RU = [
    "Понедельник", "Вторник", "Среда", "Четверг",
    "Пятница", "Суббота", "Воскресенье",
]
MONTHS_RU = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def load_render():
    """Import render_card.render() from the sibling module."""
    spec = importlib.util.spec_from_file_location(
        "render_card", HERE / "render_card.py"
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)                 # type: ignore[union-attr]
    return mod.render


def fleet_names() -> list[str]:
    """All ship-card stems in myship/, sorted (auto-tracks fleet changes)."""
    if not MYSHIP_DIR.is_dir():
        return []
    return sorted(p.stem for p in MYSHIP_DIR.glob("*.md"))


def header() -> str:
    now = datetime.now()
    weekday = WEEKDAYS_RU[now.weekday()]
    return f"🚢 <b>Fleet Brief</b> — {weekday}, {now.day} {MONTHS_RU[now.month]}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Deterministic fleet morning brief")
    ap.add_argument(
        "--names",
        help="Comma-separated ship names; default = all myship cards",
    )
    args = ap.parse_args()

    render = load_render()

    if args.names:
        names = [n.strip() for n in args.names.split(",") if n.strip()]
    else:
        names = fleet_names()

    if not names:
        print("⚠ no ships found in myship/", file=sys.stderr)
        sys.exit(2)

    cards: list[str] = []
    for name in names:
        try:
            cards.append(render(name, events_limit=3))
        except SystemExit:
            # render_card.die() exits on missing/invalid card — degrade gracefully
            cards.append(f"🚢 <b>{name}</b>        ⬜ карточка недоступна")
        except Exception as e:  # noqa: BLE001 — one bad card must not kill the brief
            cards.append(f"🚢 <b>{name}</b>        ⚠ ошибка рендера: {e}")

    print(header() + "\n\n" + SEP.join(cards))


if __name__ == "__main__":
    main()
