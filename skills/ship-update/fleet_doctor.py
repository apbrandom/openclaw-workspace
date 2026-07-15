#!/usr/bin/env python3
"""Детерминированная проверка целостности всех карточек судов (vault/ships/*.md).

Ловит порчу без участия модели — чистый структурный линт. Что проверяет на
каждой карточке:
  - файл не обрезан (размер ≥ MIN_SIZE);
  - frontmatter на месте (--- блок), есть `name:`, name == имя файла;
  - есть секции `## Текущее положение` и `## История событий`;
  - в положении есть строки Позиция / Статус / Обновлено;
  - статус из списка VALID_STATUSES (контракт update_ship.py);
  - type:баржа → задан Буксир;
  - каждый алиас/имя резолвится через resolve_ship именно в СВОЮ карточку
    (ловит и битый frontmatter, и коллизии алиасов между судами).

Запуск: `python fleet_doctor.py`  (Лиза гоняет по cron или по запросу).
Exit 0 — замечаний нет. Exit 1 — найдены проблемы (отчёт в stdout).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

WORKSPACE = Path("/home/apbrandom/.openclaw/workspace")
SHIPS_DIRS = [
    WORKSPACE / "vault" / "ships" / "myship",
    WORKSPACE / "vault" / "ships" / "craneship",
]
SKILLS = Path(__file__).parent

# Контракт update_ship.py — держать синхронным
VALID_STATUSES = {
    "на якоре", "на ходу", "грузовые",
    "швартовка", "ожидание", "в ремонте", "буксировка",
}
MIN_SIZE = 200  # байт; меньше — почти наверняка обрезан/повреждён

FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
NAME_RE = re.compile(r"^name:[ \t]*(.+)$", re.MULTILINE)
TYPE_RE = re.compile(r"^type:[ \t]*(\S.*)$", re.MULTILINE)
POS_RE = re.compile(r"^- Позиция:[ \t]*(.*)$", re.MULTILINE)
STATUS_RE = re.compile(r"^- Статус:[ \t]*(.*)$", re.MULTILINE)
TUG_RE = re.compile(r"^- Буксир:[ \t]*(.*)$", re.MULTILINE)
UPD_RE = re.compile(r"^- Обновлено:[ \t]*(.*)$", re.MULTILINE)


def load_resolver():
    spec = importlib.util.spec_from_file_location("resolve_ship", SKILLS / "resolve_ship.py")
    mod = importlib.util.module_from_spec(spec)            # type: ignore[arg-type]
    spec.loader.exec_module(mod)                            # type: ignore[union-attr]
    return mod


def all_cards() -> list[Path]:
    out: list[Path] = []
    for d in SHIPS_DIRS:
        if d.is_dir():
            out.extend(sorted(d.glob("*.md")))
    return out


def check_structure(p: Path, text: str) -> list[str]:
    problems: list[str] = []
    if len(text.encode("utf-8")) < MIN_SIZE:
        problems.append(f"CRITICAL: файл подозрительно мал ({len(text.encode('utf-8'))} б) — вероятна порча")

    fm = FM_RE.match(text)
    if not fm:
        problems.append("CRITICAL: нет frontmatter (--- блок) — структура разрушена")
        return problems  # остальное парсить бессмысленно

    fmtext = fm.group(1)
    nm = NAME_RE.search(fmtext)
    if not nm:
        problems.append("CRITICAL: нет поля 'name:' в frontmatter")
    elif nm.group(1).strip() != p.stem:
        problems.append(f"name '{nm.group(1).strip()}' != имя файла '{p.stem}'")

    for sec in ("## Текущее положение", "## История событий"):
        if not re.search(rf"^{re.escape(sec)}[ \t]*$", text, re.MULTILINE):
            problems.append(f"нет секции '{sec}'")

    # Наличие строк-полей = структура (отсутствие = порча).
    # Значения-плейсхолдеры ("[не задано]"/пусто) = незаполнено, НЕ порча — не ругаемся.
    PLACEHOLDERS = ("", "-", "[не задано]")
    if not POS_RE.search(text):
        problems.append("нет строки '- Позиция:'")
    if not UPD_RE.search(text):
        problems.append("нет строки '- Обновлено:'")
    st = STATUS_RE.search(text)
    if not st:
        problems.append("нет строки '- Статус:'")
    elif st.group(1).strip() not in PLACEHOLDERS and st.group(1).strip() not in VALID_STATUSES:
        problems.append(f"статус '{st.group(1).strip()}' не из списка {sorted(VALID_STATUSES)}")

    # Для баржи строка Буксир должна существовать (значение может быть ещё не задано).
    tm = TYPE_RE.search(fmtext)
    if tm and tm.group(1).strip() == "баржа" and not TUG_RE.search(text):
        problems.append("type:баржа, но нет строки '- Буксир:'")

    return problems


def main() -> None:
    resolver = load_resolver()
    cards = all_cards()
    report: list[str] = []
    total = 0

    for p in cards:
        text = p.read_text(encoding="utf-8")
        probs = check_structure(p, text)

        # Резолв-проверка: имя и каждый алиас должны вести в СВОЮ карточку
        fm = resolver._parse_frontmatter(text)
        for token in [fm.get("name", "")] + fm.get("aliases", []):
            token = (token or "").strip()
            if not token:
                continue
            res = resolver.resolve(token)
            if not res.get("found"):
                probs.append(f"алиас '{token}' не резолвится НИ ВО ЧТО")
            elif res.get("canonical") != p.stem:
                probs.append(f"алиас '{token}' резолвится в чужую карточку '{res.get('canonical')}'")

        if probs:
            report.append(f"✗ {p.stem}:")
            report.extend(f"    - {x}" for x in probs)
            total += len(probs)

    if total == 0:
        print(f"✓ Замечаний нет — {len(cards)} карточек целы и резолвятся.")
        sys.exit(0)

    print(f"⚠ Проблемы целостности карточек: {total} (всего карточек: {len(cards)})\n")
    print("\n".join(report))
    sys.exit(1)


if __name__ == "__main__":
    main()
