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

# SHIP_WORKSPACE: тестовый override; в проде не задан — боевой vault
WORKSPACE = Path(os.environ.get("SHIP_WORKSPACE", "/home/apbrandom/.openclaw/workspace"))
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

VALID_STATUSES = {
    "на якоре", "на ходу", "грузовые",
    "швартовка", "ожидание", "в ремонте", "буксировка",
}

# Связка буксир↔баржа: у баржи «Буксир:», у буксира зеркальное «Ведёт:».
# Источник правды — карточка баржи; «Ведёт:» пишет только этот скрипт.
LINK_MARKER = "Ведёт:"
LINK_CLEAR = {"—", "-", "нет"}  # значения tugboat, означающие разрыв связки
# Статусы, в которых баржа физически движется — без буксира невозможны (R-06)
BARGE_MOVING_STATUSES = {"на ходу", "буксировка"}


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


def find_ship_file_optional(name: str) -> Path | None:
    """Как find_ship_file, но без die — для линкованного судна, которого может не быть."""
    if not name or "/" in name or ".." in name:
        return None
    for d in SHIPS_DIRS:
        p = d / f"{name}.md"
        if p.is_file():
            return p
    return None


def read_field(body: str, marker: str) -> str | None:
    """Текущее значение строки '- <marker> <value>' или None, если строки нет."""
    m = re.search(rf"^- {re.escape(marker)}[ \t]*(.*)$", body, re.MULTILINE)
    return m.group(1).strip() if m else None


def set_or_insert_field(body: str, marker: str, new_value: str) -> str:
    """replace_status_field, но при отсутствии строки вставляет её перед «Обновлено:»."""
    pattern = re.compile(rf"^(- {re.escape(marker)})[ \t]*.*$", re.MULTILINE)
    if pattern.search(body):
        return pattern.sub(rf"\1 {new_value}", body, count=1)
    upd = re.search(r"^- Обновлено:", body, re.MULTILINE)
    if not upd:
        die(f"⚠ cannot insert '{marker}': 'Обновлено:' line missing")
    return body[:upd.start()] + f"- {marker} {new_value}\n" + body[upd.start():]


def ship_type_of(body: str) -> str:
    m = re.search(r"^type:[ \t]*(\S.*)$", body, re.MULTILINE)
    return m.group(1).strip() if m else ""


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

    status = payload.get("status")
    if status is not None and status.strip() not in VALID_STATUSES:
        die(f"⚠ invalid status {status.strip()!r}, allowed: {', '.join(sorted(VALID_STATUSES))}")

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


def _apply(body: str, payload: dict[str, Any]) -> str:
    """Мутация тела карточки одним payload'ом. Без записи на диск и без связки."""
    for key, marker in STATUS_FIELDS.items():
        v = payload.get(key)
        if v is not None:
            if key == "tugboat":
                # у старых карточек барж строки «Буксир:» может не быть
                body = set_or_insert_field(body, marker, v.strip())
            else:
                body = replace_status_field(body, marker, v.strip())

    events = payload.get("events", [])
    events = _normalize_event_dates(events, payload.get("last_update_dt"))
    body = append_events(body, events)

    dt = payload.get("last_update_dt")
    if dt:
        body = update_frontmatter_date(body, dt.split(" ", 1)[0])

    type_str = payload.get("type")
    if type_str:
        body = update_frontmatter_type(body, type_str.strip())
    return body


def _set_link_field(ship_name: str, marker: str, value: str) -> list[str]:
    """Выставить «Буксир:»/«Ведёт:» на другой карточке. Судна нет — молча пропустить."""
    path = find_ship_file_optional(ship_name)
    if not path:
        return []
    body = path.read_text(encoding="utf-8")
    new_body = set_or_insert_field(body, marker, value)
    if new_body != body:
        atomic_write(path, new_body)
        return [f"✓ {ship_name} updated ({path.relative_to(WORKSPACE)})"]
    return []


# Статус линкованного судна vs статус исходного (упрощение, 15.07 — сознательно
# оставлено место для правок: физически «швартовка» буксира не всегда значит,
# что баржа тоже ошвартована, но пока зеркалим как есть). Отсутствие пары в
# словаре = статус передаётся без изменений (см. _propagated_status).
TUG_TO_BARGE_STATUS = {"на ходу": "буксировка"}
BARGE_TO_TUG_STATUS = {"буксировка": "на ходу"}


def _propagated_status(status: str | None, to_barge: bool) -> str | None:
    """Статус для линкованного судна, с учётом маппинга выше."""
    if not status:
        return None
    status = status.strip()
    mapping = TUG_TO_BARGE_STATUS if to_barge else BARGE_TO_TUG_STATUS
    if status in mapping:
        return mapping[status]
    return status if status in VALID_STATUSES else None


def update(payload: dict[str, Any], auto_resolve: bool = False) -> list[str]:
    """Обновить карточку + поддержать связку буксир↔баржа.

    Возвращает список '✓ NAME updated (...)' — по строке на каждую
    изменённую карточку (цель + линкованное судно). Карточку больше НЕ
    кэшируем в vault/ship_cards/*.html: send_card.py рендерит на лету.
    """
    validate(payload)
    name = payload["name"].strip()
    if auto_resolve:
        canonical = _try_resolve(name)
        if canonical:
            name = canonical
    ship_path = find_ship_file(name)
    body = ship_path.read_text(encoding="utf-8")
    is_barge = "барж" in ship_type_of(body).lower()
    old_tug = read_field(body, "Буксир:") if is_barge else None

    # tugboat: канонизировать имя буксира / распознать разрыв связки
    tug_req = payload.get("tugboat")
    if tug_req is not None:
        tug_req = tug_req.strip()
        if tug_req in LINK_CLEAR:
            payload["tugboat"] = "—"
            tug_req = "—"
        else:
            tug_req = _try_resolve(tug_req) or tug_req
            payload["tugboat"] = tug_req

    new_body = _apply(body, payload)

    # R-06: движущаяся баржа обязана иметь буксир
    if is_barge:
        eff_status = read_field(new_body, "Статус:") or ""
        eff_tug = read_field(new_body, "Буксир:") or ""
        if eff_status in BARGE_MOVING_STATUSES and (not eff_tug or eff_tug in LINK_CLEAR):
            die(f"⚠ R-06: баржа {name} не может быть «{eff_status}» без буксира — "
                "укажи tugboat (или tugboat='—' + статус стоянки)")

    atomic_write(ship_path, new_body)
    messages = [f"✓ {name} updated ({ship_path.relative_to(WORKSPACE)})"]

    # --- Связка: зеркалим «Ведёт:» на буксире -------------------------------
    if is_barge and tug_req is not None:
        if tug_req == "—":
            if old_tug and old_tug not in LINK_CLEAR:
                messages += _set_link_field(old_tug, LINK_MARKER, "—")
        else:
            tug_path = find_ship_file_optional(tug_req)
            if tug_path:
                tug_body = tug_path.read_text(encoding="utf-8")
                prev_barge = read_field(tug_body, LINK_MARKER)
                # буксир ведёт одну баржу: старую связку рвём
                if prev_barge and prev_barge not in LINK_CLEAR and prev_barge != name:
                    messages += _set_link_field(prev_barge, "Буксир:", "—")
                messages += _set_link_field(tug_req, LINK_MARKER, name)
            # у баржи сменился буксир — старый больше не ведёт её
            if old_tug and old_tug not in LINK_CLEAR and old_tug != tug_req:
                messages += _set_link_field(old_tug, LINK_MARKER, "—")

    # --- Прокачка движения на линкованное судно ------------------------------
    movement = {k: payload.get(k) for k in ("position", "status", "last_update_dt", "events")
                if payload.get(k)}
    if movement:
        if is_barge:
            linked = read_field(new_body, "Буксир:")
            linked_is_barge = False
        else:
            linked = read_field(new_body, LINK_MARKER)
            linked_is_barge = True
        if linked and linked not in LINK_CLEAR:
            linked_path = find_ship_file_optional(linked)
            if linked_path:
                lp: dict[str, Any] = {}
                if movement.get("position"):
                    lp["position"] = movement["position"]
                if movement.get("last_update_dt"):
                    lp["last_update_dt"] = movement["last_update_dt"]
                if movement.get("events"):
                    lp["events"] = movement["events"]
                st = _propagated_status(movement.get("status"), to_barge=linked_is_barge)
                if st:
                    lp["status"] = st
                if lp:
                    linked_body = _apply(linked_path.read_text(encoding="utf-8"), lp)
                    atomic_write(linked_path, linked_body)
                    messages.append(
                        f"✓ {linked} updated ({linked_path.relative_to(WORKSPACE)})")

    return messages


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

    print("\n".join(update(payload, auto_resolve=args.auto_resolve)))


if __name__ == "__main__":
    main()
