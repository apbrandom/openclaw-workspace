#!/usr/bin/env /home/apbrandom/.openclaw/tools-venv/bin/python
"""
notion_sync.py — sync vault/ships/*.md → Notion (Superintendent page)
Commands:
  init          create all ship pages (first run)
  sync [SHIP]   update all or one ship
  status        show state
"""
import sys
import json
import re
import yaml
import urllib.request
import urllib.error
from pathlib import Path

NOTION_KEY = "ntn_b5610931076ls0R6ceSFkEbOGNeCd30LOOspi4GdyUc7di"
SUPERINTENDENT_PAGE = "1ad14e700384807e89d6e13c8bdb5a26"
SHIPS_DIR = Path("/home/apbrandom/.openclaw/workspace/vault/ships")
STATE_FILE = Path("/home/apbrandom/.openclaw/workspace/skills/obsidian/notion_state.json")

HEADERS = {
    "Authorization": f"Bearer {NOTION_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

SHIP_DISPLAY = {
    "ATLAS_1": "ATLAS 1",
    "PRUT": "ПРУТ",
    "TISA": "ТИСА",
    "TURAN": "ТУРАН",
}


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _req(method, path, body=None):
    url = f"https://api.notion.com/v1{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        print(f"  API error {e.code}: {err.get('message', err)}")
        sys.exit(1)

def post(path, body): return _req("POST", path, body)
def patch(path, body): return _req("PATCH", path, body)
def get(path): return _req("GET", path)


# ── State ─────────────────────────────────────────────────────────────────────

def load_state():
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


# ── Parsing ───────────────────────────────────────────────────────────────────

def parse_ship(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not m:
        return {}
    fm = yaml.safe_load(m.group(1)) or {}
    fm["_body"] = m.group(2).strip()
    fm["_file"] = path.stem
    return fm


# ── Notion block builders ─────────────────────────────────────────────────────

def rt(text, bold=False):
    r = {"type": "text", "text": {"content": str(text)}}
    if bold:
        r["annotations"] = {"bold": True}
    return r

def heading2(text):
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [rt(text)]}}

def heading3(text):
    return {"object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [rt(text)]}}

def para(text, bold=False):
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [rt(text, bold)] if text else []}}

def divider():
    return {"object": "block", "type": "divider", "divider": {}}

def table_row(cells):
    return {
        "type": "table_row",
        "table_row": {"cells": [[rt(str(c or "—"))] for c in cells]}
    }

def make_ship_blocks(fm: dict) -> list:
    ship_id = fm.get("_file", "")
    display = SHIP_DISPLAY.get(ship_id, fm.get("name", ship_id))

    blocks = []

    # Info table
    blocks.append(heading2("Характеристики"))
    blocks.append({
        "object": "block", "type": "table",
        "table": {
            "table_width": 2,
            "has_column_header": False,
            "has_row_header": True,
            "children": [
                table_row(["Тип",          fm.get("type") or "—"]),
                table_row(["Год постройки", fm.get("year") or "—"]),
                table_row(["Вместимость",   f"{fm['capacity_teu']} TEU" if fm.get("capacity_teu") else "—"]),
                table_row(["IMO",           fm.get("imo") or "—"]),
                table_row(["Флаг",          fm.get("flag") or "—"]),
                table_row(["Владелец",      fm.get("owner") or "—"]),
                table_row(["Статус",        fm.get("status") or "—"]),
                table_row(["Обновлено",     str(fm.get("last_updated") or "—")]),
            ]
        }
    })

    blocks.append(divider())
    blocks.append(heading2("Текущий статус"))
    blocks.append(para("порт, рейс, ETA"))

    blocks.append(divider())
    blocks.append(heading2("Технические характеристики"))
    blocks.append(para("двигатель, корпус, навигация"))

    blocks.append(divider())
    blocks.append(heading2("История событий"))
    blocks.append(para(""))

    blocks.append(divider())
    blocks.append(heading2("Документы"))
    blocks.append(para("PDF, сертификаты"))

    return blocks


# ── Core ──────────────────────────────────────────────────────────────────────

def create_ship_page(fm: dict, parent_id: str) -> str:
    ship_id = fm.get("_file", "")
    display = SHIP_DISPLAY.get(ship_id, fm.get("name", ship_id))
    blocks = make_ship_blocks(fm)

    page = post("/pages", {
        "parent": {"type": "page_id", "page_id": parent_id},
        "properties": {
            "title": {"title": [rt(display)]}
        },
        "children": blocks,
    })
    return page["id"]


def update_ship_page(fm: dict, page_id: str):
    """Append updated characteristics table to existing page."""
    # Get existing blocks and archive old ones if needed — for now just update title
    ship_id = fm.get("_file", "")
    display = SHIP_DISPLAY.get(ship_id, fm.get("name", ship_id))
    patch(f"/pages/{page_id}", {
        "properties": {"title": {"title": [rt(display)]}}
    })
    # Append fresh blocks
    blocks = make_ship_blocks(fm)
    post(f"/blocks/{page_id}/children", {"children": blocks})


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_init():
    state = load_state()
    if state.get("pages"):
        print("Страницы уже созданы. Используй 'sync' для обновления.")
        return

    ship_files = sorted(p for p in SHIPS_DIR.glob("*.md") if p.stem != "index")
    print(f"Создаю {len(ship_files)} страниц в Superintendent...\n")

    pages = {}
    for path in ship_files:
        fm = parse_ship(path)
        if not fm:
            continue
        ship_id = fm["_file"]
        display = SHIP_DISPLAY.get(ship_id, ship_id)
        print(f"  {display}...", end=" ", flush=True)
        page_id = create_ship_page(fm, SUPERINTENDENT_PAGE)
        pages[ship_id] = page_id
        print(f"OK ({page_id[:8]}...)")

    state["pages"] = pages
    save_state(state)
    print(f"\nГотово. State: {STATE_FILE}")


def cmd_sync(args):
    state = load_state()

    if args:
        target = args[0].upper().replace(" ", "_").replace("-", "_")
        ship_files = [SHIPS_DIR / f"{target}.md"]
        ship_files = [f for f in ship_files if f.exists()]
        if not ship_files:
            print(f"Не найдено: {target}.md")
            sys.exit(1)
    else:
        ship_files = sorted(p for p in SHIPS_DIR.glob("*.md") if p.stem != "index")

    pages = state.get("pages", {})
    print(f"Sync {len(ship_files)} судно(а)...\n")

    for path in ship_files:
        fm = parse_ship(path)
        if not fm:
            continue
        ship_id = fm["_file"]
        display = SHIP_DISPLAY.get(ship_id, ship_id)
        existing = pages.get(ship_id)
        print(f"  {display}...", end=" ", flush=True)
        if existing:
            update_ship_page(fm, existing)
            print(f"обновлено")
        else:
            page_id = create_ship_page(fm, SUPERINTENDENT_PAGE)
            pages[ship_id] = page_id
            print(f"создано ({page_id[:8]}...)")

    state["pages"] = pages
    save_state(state)
    print("\nГотово.")


def cmd_status():
    state = load_state()
    if not state:
        print("Нет данных. Запусти 'init'.")
        return
    pages = state.get("pages", {})
    print(f"Страницы ({len(pages)}):")
    for ship_id, pid in sorted(pages.items()):
        display = SHIP_DISPLAY.get(ship_id, ship_id)
        print(f"  {display:15s} → https://notion.so/{pid.replace('-','')}")


def main():
    cmds = {"init": cmd_init, "sync": cmd_sync, "status": cmd_status}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(f"Команды: {', '.join(cmds)}")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "sync":
        cmd_sync(sys.argv[2:])
    elif cmd == "init":
        cmd_init()
    else:
        cmds[cmd]()

if __name__ == "__main__":
    main()
