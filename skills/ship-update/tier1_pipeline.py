#!/usr/bin/env python3
"""Tier-1 pipeline: resolve → update → send_card in one call.

Lisa calls this for every forwarded dispatcher message. No intermediate steps.

Usage:
  echo '<JSON>' | python tier1_pipeline.py --chat-id 7622255068

Input JSON:
{
  "name":           "BP_01",              # ship name (alias or canonical)
  "position":       "РПР №3",            # current location
  "status":         "на якоре",          # operational status
  "tugboat":        "SIROKO",            # optional, barges only
  "last_update_dt": "2026-05-20 14:10",  # YYYY-MM-DD HH:MM
  "events":         ["14:10 — встали на якорь в РПР №3", ...]
}

Exit 0 on success, prints ✓ confirmation to stdout.
Exit 2 on error, prints reason to stderr.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PYTHON = "/home/apbrandom/.openclaw/tools-venv/bin/python"
SKILLS = Path(__file__).parent
UPDATE_PY = SKILLS / "update_ship.py"
SEND_CARD_PY = SKILLS / "send_card.py"


def die(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def run_update(payload: dict) -> str:
    result = subprocess.run(
        [PYTHON, str(UPDATE_PY), "--auto-resolve"],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True, text=True
    )
    if result.returncode != 0:
        die(f"⚠ update_ship failed: {result.stderr.strip()}")
    return result.stdout.strip()


def run_send_card(name: str, chat_id: str | None) -> str:
    cmd = [PYTHON, str(SEND_CARD_PY), "--name", name]
    if chat_id:
        cmd += ["--chat-id", chat_id]
    result = subprocess.run(
        cmd, capture_output=True, text=True
    )
    if result.returncode != 0:
        die(f"⚠ send_card failed: {result.stderr.strip()}")
    return result.stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat-id", dest="chat_id", default=None,
                    help="override card destination; default = work dispatch chat")
    ap.add_argument("--json", help="JSON payload (else read stdin)")
    args = ap.parse_args()

    raw = args.json if args.json else sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"⚠ invalid JSON: {e}")

    name = payload.get("name", "").strip()
    if not name:
        die("⚠ 'name' required")

    run_update(payload)
    result = run_send_card(name, args.chat_id)
    print(result)


if __name__ == "__main__":
    main()
