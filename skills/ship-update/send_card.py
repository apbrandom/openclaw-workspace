#!/usr/bin/env python3
"""Send a rendered ship card directly to Telegram via Bot API.

Bypasses the LLM response — card HTML goes straight to Telegram.
Lisa calls this script; her response is the short ✓ confirmation.

Usage:
  python send_card.py --name MODUS --chat-id 7622255068
  python send_card.py --name Модус --chat-id 7622255068   # auto-resolve alias
  echo '{"name":"MODUS","chat_id":"7622255068"}' | python send_card.py

Exit 0 on success, prints single-line result to stdout.
Exit 2 on error, prints reason to stderr.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE    = Path("/home/apbrandom/.openclaw/workspace")
ENV_FILE     = Path("/home/apbrandom/.openclaw/.env")
CARDS_DIR    = WORKSPACE / "vault" / "ship_cards"
RENDER_PY    = Path(__file__).parent / "render_card.py"
RESOLVE_PY   = Path(__file__).parent / "resolve_ship.py"
WORK_ACCOUNT = "TELEGRAM_WORK_BOT_TOKEN"
API_BASE     = "https://api.telegram.org/bot{token}/sendMessage"


def die(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def load_token(key: str) -> str:
    try:
        data = json.loads(ENV_FILE.read_text())
        token = data.get(key, "")
        if not token:
            die(f"⚠ token '{key}' missing in .env")
        return token
    except Exception as e:
        die(f"⚠ cannot read .env: {e}")


def resolve_name(name: str) -> str:
    import importlib.util
    spec = importlib.util.spec_from_file_location("resolve_ship", RESOLVE_PY)
    mod = importlib.util.module_from_spec(spec)       # type: ignore[arg-type]
    spec.loader.exec_module(mod)                       # type: ignore[union-attr]
    result = mod.resolve(name)
    if result.get("found"):
        return result["canonical"]
    return name


def render_html(canonical: str) -> str:
    # Try pre-rendered card first (fast path)
    card_file = CARDS_DIR / f"{canonical}.html"
    if card_file.is_file():
        return card_file.read_text(encoding="utf-8").strip()

    # Fallback: render on the fly
    import importlib.util
    spec = importlib.util.spec_from_file_location("render_card", RENDER_PY)
    mod = importlib.util.module_from_spec(spec)        # type: ignore[arg-type]
    spec.loader.exec_module(mod)                        # type: ignore[union-attr]
    return mod.render(canonical).strip()


def send_telegram(token: str, chat_id: str, html: str) -> dict:
    import urllib.request
    payload = json.dumps({
        "chat_id":    chat_id,
        "text":       html,
        "parse_mode": "HTML",
    }).encode()
    url = API_BASE.format(token=token)
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def run(name: str, chat_id: str) -> str:
    canonical = resolve_name(name)
    html      = render_html(canonical)
    token     = load_token(WORK_ACCOUNT)

    result = send_telegram(token, chat_id, html)
    if not result.get("ok"):
        die(f"⚠ Telegram error: {result.get('description','unknown')}")

    return f"✓ {canonical}: карточка отправлена"


def main() -> None:
    ap = argparse.ArgumentParser(description="Send ship card to Telegram")
    ap.add_argument("--name",    help="Ship name (canonical or alias)")
    ap.add_argument("--chat-id", dest="chat_id", help="Telegram chat ID")
    ap.add_argument("--json",    help="JSON payload")
    args = ap.parse_args()

    if args.json or (not args.name and not sys.stdin.isatty()):
        raw = args.json or sys.stdin.read()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            die(f"⚠ invalid JSON: {e}")
        name    = payload.get("name", "").strip()
        chat_id = str(payload.get("chat_id", "")).strip()
    else:
        name    = (args.name or "").strip()
        chat_id = (args.chat_id or "").strip()

    if not name:
        die("⚠ --name required")
    if not chat_id:
        die("⚠ --chat-id required")

    print(run(name, chat_id))


if __name__ == "__main__":
    main()
