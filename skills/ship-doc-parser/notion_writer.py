"""
Запись строк инвентаря в Notion (3 базы: АТЛАС 1, ТИСА, ПРУТ).
Используется supply_intake.py.
"""
import json, re
from pathlib import Path

import requests

HERE = Path(__file__).parent
CONFIG = json.loads((HERE / "notion_inventory.json").read_text(encoding="utf-8"))
STATE_FILE = HERE / "notion_processed.json"

NOTION_KEY = json.loads(Path("/home/apbrandom/.openclaw/.env").read_text())["NOTION_API_KEY"]
H = {"Authorization": f"Bearer {NOTION_KEY}", "Notion-Version": "2022-06-28",
     "Content-Type": "application/json"}

SHIP_STEMS = {"АТЛАС 1": "ATLAS_1", "ТИСА": "TISA", "ПРУТ": "PRUT"}
UNITS = set(CONFIG["units"])
PLACES = set(CONFIG["places"])


def normalize(s: str) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"^(м/б|т/х|м/в|т/б|m/v|m/b|barge|vessel|ship|теплоход|буксир)\s*", "", s)
    s = re.sub(r"[\s\-_.\"«»]+", "", s)
    return s


_TARGET_KEYS = {normalize(name): name for name in CONFIG["databases"]}


def resolve_ship(raw_name: str) -> str | None:
    """Вернуть точное имя базы (АТЛАС 1/ТИСА/ПРУТ) или None если судно не отслеживается."""
    return _TARGET_KEYS.get(normalize(raw_name))


def normalize_unit(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip().lower()
    aliases = {"шт": "шт", "шт.": "шт", "компл": "компл", "компл.": "компл",
               "место": "место", "мест": "место", "пар": "пар", "пара": "пар",
               "кг": "кг", "л": "л", "м": "м"}
    return aliases.get(raw)


def resolve_place(raw_name: str) -> str:
    """Резолвит склад/суда/цеха в фикс. список PLACES. Неизвестное — возвращает как есть (для Примечания)."""
    key = normalize(raw_name)
    for p in PLACES:
        if normalize(p) == key:
            return p
    if "склад" in key or "краншип" in key:
        return "Склад"
    return raw_name  # неизвестное место — пишем как есть, не блокируем запись


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def already_written(dedup_key: str) -> bool:
    return dedup_key in _load_state()


def mark_written(dedup_key: str, page_id: str):
    state = _load_state()
    state[dedup_key] = page_id
    _save_state(state)


def find_existing(ship: str, name: str, qty: float | None) -> dict | None:
    """Смысловой дедуп: та же позиция (имя+кол-во) на том же судне уже есть в базе?
    Ловит случай «тот же акт прислан второй раз» (черновик → подписанный оригинал) —
    файл другой (другой хэш), но факт передачи один и тот же. Возвращает найденную
    страницу (Notion page dict) или None."""
    db_id = CONFIG["databases"][ship]
    r = requests.post(f"https://api.notion.com/v1/databases/{db_id}/query", headers=H,
                      json={"filter": {"property": "Запчасть", "title": {"equals": name[:200]}}},
                      timeout=30)
    if r.status_code != 200:
        return None
    for row in r.json().get("results", []):
        existing_qty = row["properties"].get("Кол-во", {}).get("number")
        if qty is None or existing_qty == qty:
            return row
    return None


def confirm_existing(page_id: str, апп_номер: str):
    """Пометить уже существующую строку как подтверждённую повторным документом
    (напр. пришла подписанная копия акта, черновик уже был записан ранее)."""
    requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=H,
                  json={"properties": {"Проверено": {"checkbox": True}}}, timeout=30)


def write_row(ship: str, *, name: str, qty: float | None, qty_raw: str, unit: str | None,
              откуда: str, дата: str | None, апп_номер: str, примечание: str,
              статус: str = "В пути") -> str:
    """Создать строку в базе инвентаря судна. Возвращает id созданной страницы."""
    db_id = CONFIG["databases"][ship]

    props = {
        "Запчасть": {"title": [{"text": {"content": name[:200]}}]},
        "Куда": {"select": {"name": ship}},
        "Статус": {"select": {"name": статус}},
        "Проверено": {"checkbox": False},
        "АПП №": {"rich_text": [{"text": {"content": апп_номер[:100]}}]},
    }
    if qty is not None:
        props["Кол-во"] = {"number": qty}
    if unit:
        props["Ед."] = {"select": {"name": unit}}
    if откуда:
        props["Откуда"] = {"select": {"name": откуда}} if откуда in PLACES else None
    if дата:
        props["Дата"] = {"date": {"start": дата}}
    note_parts = [примечание] if примечание else []
    if qty_raw and str(qty) != qty_raw:
        note_parts.append(f"сырое кол-во: {qty_raw}")
    if props.get("Откуда") is None and откуда:
        note_parts.append(f"откуда (не в списке): {откуда}")
        del props["Откуда"]
    if note_parts:
        props["Примечание"] = {"rich_text": [{"text": {"content": " · ".join(note_parts)[:500]}}]}

    r = requests.post("https://api.notion.com/v1/pages", headers=H,
                      json={"parent": {"database_id": db_id}, "properties": props},
                      timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Notion write failed ({ship}/{name}): {r.status_code} {r.text[:300]}")
    return r.json()["id"]
