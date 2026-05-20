#!/usr/bin/env python3
"""Regenerate all ship cards in vault/ship_cards/.

Run after bulk edits or to repair stale cards.
Normal flow: update_ship.py refreshes the card automatically after each update.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path("/home/apbrandom/.openclaw/workspace")
SHIPS_DIRS = [
    WORKSPACE / "vault" / "ships" / "myship",
    WORKSPACE / "vault" / "ships" / "craneship",
]
CARDS_DIR = WORKSPACE / "vault" / "ship_cards"


def main() -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "render_card", Path(__file__).parent / "render_card.py"
    )
    mod = importlib.util.module_from_spec(spec)   # type: ignore[arg-type]
    spec.loader.exec_module(mod)                  # type: ignore[union-attr]

    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    ok = err = 0
    for d in SHIPS_DIRS:
        if not d.is_dir():
            continue
        for md_file in sorted(d.glob("*.md")):
            name = md_file.stem
            try:
                html = mod.render(name)
                out = CARDS_DIR / f"{name}.html"
                out.write_text(html, encoding="utf-8")
                print(f"✓ {name}")
                ok += 1
            except SystemExit as e:
                print(f"✗ {name}: exit {e.code}", file=sys.stderr)
                err += 1
            except Exception as e:
                print(f"✗ {name}: {e}", file=sys.stderr)
                err += 1

    print(f"\n{ok} ok, {err} errors")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
