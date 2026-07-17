#!/usr/bin/env /home/apbrandom/.openclaw/tools-venv/bin/python
"""
Intake для формы «Акт приема-передачи №» (снабжение, склад КРАНШИП → суда).
Многостраничный PDF: каждая страница = отдельный акт на одно судно/баржу.
Пишет позиции ТОЛЬКО для отслеживаемых судов (АТЛАС 1, ТИСА, ПРУТ) в Notion.

Запуск: python3 supply_intake.py /path/to/file.pdf
"""
import sys, json, re, subprocess, hashlib, time, shutil
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import vl_utils
from vl_utils import log, call_ollama_vl
import notion_writer as nw

SHIPS_DOCS = Path("/home/apbrandom/.openclaw/workspace/vault/ships_docs/_supply")

vl_utils.VL_MODEL = "qwen3-vl:8b-instruct"  # instruct-вариант — thinking-модель не отдаёт response (см. ROADMAP)
TELEGRAM_CHAT_ID = 299387691

PROMPT = """Это скан документа «Акт приема-передачи» (снабжение флота, склад → судно).
Извлеки в JSON:
- date: поле «Дата» (DD.MM.YYYY)
- receiver: значение поля «Наименование» под датой (кому передают)
- sender: текст штампа или Ф.И.О. в блоке «Передал» внизу
- items: массив ЗАПОЛНЕННЫХ строк таблицы (пустые не включай), каждая:
  {"n": номер строки, "name": наименование ТОЧНО как написано (включая внутренние запятые), "unit": ед. измерения, "qty": количество ТОЧНО как написано (включая разделители \\ и /), "crossed_out": true если строка перечёркнута линией поверх текста, иначе false}
Только валидный JSON, без markdown, без пояснений."""


def get_bot_token() -> str | None:
    try:
        data = json.loads((Path.home() / ".openclaw/openclaw.json").read_text())
        return data["channels"]["telegram"]["accounts"]["default"]["botToken"]
    except Exception:
        return None


def send_telegram(msg: str):
    token = get_bot_token()
    if not token:
        print(f"[tg] {msg}")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                     json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
                     timeout=10)
    except Exception as e:
        print(f"[tg error] {e}")


def render_pages(pdf: Path) -> list[Path]:
    subprocess.run(["pdftoppm", "-r", "150", "-png", str(pdf), "/tmp/supply_page"],
                   check=True, capture_output=True)
    return sorted(Path("/tmp").glob("supply_page-*.png"))


def sanitize(s, maxlen=300):
    if not s or not isinstance(s, str):
        return None
    s = re.sub(r"[\x00-\x08\x0a-\x1f\x7f]", " ", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:maxlen] if s else None


def vl_extract(png: Path) -> dict:
    raw = call_ollama_vl(png, PROMPT, retries=2, retry_delay=15, timeout=120,
                         req_file="/tmp/supply_vl_req.json", num_ctx=8192, num_predict=3072)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            raise ValueError(f"VL вернул не-JSON: {raw[:150]!r}")
        data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise ValueError("VL ответ не dict")
    clean = {
        "date": sanitize(data.get("date"), 20),
        "receiver": sanitize(data.get("receiver"), 100),
        "sender": sanitize(data.get("sender"), 100),
    }
    items = []
    for it in (data.get("items") or [])[:30]:
        if not isinstance(it, dict):
            continue
        items.append({
            "name": sanitize(it.get("name"), 200) or "?",
            "unit": sanitize(it.get("unit"), 20) or "",
            "qty": sanitize(str(it.get("qty", "")), 30) or "",
            "crossed_out": bool(it.get("crossed_out")),
        })
    clean["items"] = items
    return clean


def parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
    if not m:
        return None
    d, mo, y = m.groups()
    try:
        dt = datetime(int(y), int(mo), int(d))
    except ValueError:
        return None
    if dt.date() > datetime.today().date():
        return None  # будущая дата — не доверяем OCR, эскалируем выше
    return dt.strftime("%Y-%m-%d")


def split_item(name: str, qty: str, unit: str):
    """Разбить составную строку («A, B, C» + «1\\2\\3») на отдельные позиции.
    Возвращает (list[(name,qty_str)], ok:bool)."""
    # comma+space = разделитель позиций; comma без пробела (напр. "7,6") — десятичный разделитель, не режем
    names = [n.strip() for n in re.split(r",\s+", name) if n.strip()]
    qtys = [q.strip() for q in re.split(r"[\\/]", qty) if q.strip()]
    if len(names) <= 1 or len(qtys) <= 1:
        return [(name, qty)], True
    if len(names) == len(qtys):
        return list(zip(names, qtys)), True
    return [(name, qty)], False  # не сходится — не режем, эскалируем


def to_number(qty_str: str) -> float | None:
    m = re.search(r"\d+(?:[.,]\d+)?", qty_str)
    if not m:
        return None
    return float(m.group(0).replace(",", "."))


def dedup_key(pdf_hash: str, page_num: int, ship: str, name: str, qty: str) -> str:
    raw = f"{pdf_hash}:{page_num}:{ship}:{name}:{qty}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def process_pdf(pdf: Path):
    pdf_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()[:16]
    pages = render_pages(pdf)
    total = len(pages)
    log("INIT", f"{pdf.name}: {total} страниц")

    written, skipped_ships, escalations = [], set(), []

    for i, png in enumerate(pages, 1):
        try:
            t = time.time()
            data = vl_extract(png)
        except Exception as e:
            log("ERROR", f"стр {i}/{total}: {e}")
            escalations.append(f"стр {i}: ошибка извлечения — {e}")
            continue
        finally:
            png.unlink(missing_ok=True)

        receiver = data.get("receiver")
        ship = nw.resolve_ship(receiver) if receiver else None
        date_iso = parse_date(data.get("date"))
        if data.get("date") and not date_iso:
            escalations.append(f"стр {i} ({receiver}): дата «{data['date']}» нечитаема/в будущем — не проставлена")

        if not ship:
            skipped_ships.add(receiver or "?")
            log("SKIP", f"стр {i}/{total}: «{receiver}» — не отслеживаемое судно")
            continue

        откуда = nw.resolve_place(data.get("sender") or "Склад")
        апп_номер = f"{pdf.name}#{i}"
        n_written = 0
        for it in data["items"]:
            pieces, ok = split_item(it["name"], it["qty"], it["unit"])
            for name, qty_raw in pieces:
                key = dedup_key(pdf_hash, i, ship, name, qty_raw)
                if nw.already_written(key):
                    continue
                unit = nw.normalize_unit(it["unit"])
                qty_num = to_number(qty_raw)
                note = ""
                if not ok:
                    note = "⚠ не разбито (кол-во строк не совпало с именами) — проверить"
                    escalations.append(f"стр {i} ({ship}): «{name}» qty=«{qty_raw}» — не удалось разбить")
                if it["crossed_out"]:
                    note = (note + " · " if note else "") + "⚠ строка перечёркнута в акте — проверить актуальность"
                    escalations.append(f"стр {i} ({ship}): «{name}» — перечёркнуто в скане")
                if not unit:
                    note = (note + " · " if note else "") + f"ед.изм. вне списка: «{it['unit']}»"

                existing = nw.find_existing(ship, name, qty_num)
                if existing:
                    already_confirmed = existing["properties"].get("Проверено", {}).get("checkbox")
                    if not already_confirmed:
                        nw.confirm_existing(existing["id"], апп_номер)
                        log("CONFIRM", f"стр {i}/{total}: {ship} — «{name}» уже был записан, помечаю Проверено")
                    nw.mark_written(key, existing["id"])
                    continue

                page_id = nw.write_row(ship, name=name, qty=qty_num, qty_raw=qty_raw,
                                       unit=unit, откуда=откуда, дата=date_iso,
                                       апп_номер=апп_номер, примечание=note)
                nw.mark_written(key, page_id)
                n_written += 1
        written.append((ship, n_written))
        log("WRITE", f"стр {i}/{total}: {ship} — {n_written} строк за {time.time()-t:.0f}с")

    return written, skipped_ships, escalations


def summarize(pdf_name: str, written, skipped_ships, escalations):
    by_ship = {}
    for ship, n in written:
        by_ship[ship] = by_ship.get(ship, 0) + n
    lines = [f"📦 *Снабжение обработано* `{pdf_name}`"]
    if by_ship:
        lines.append("Записано в Notion: " + ", ".join(f"{s} ({n})" for s, n in by_ship.items()))
    if skipped_ships:
        lines.append(f"Пропущено (не наш флот): {', '.join(sorted(skipped_ships))}")
    if escalations:
        lines.append(f"\n⚠️ Требует проверки ({len(escalations)}):")
        lines.extend(f"• {e}" for e in escalations[:15])
    return "\n".join(lines)


def move_processed(pdf: Path) -> Path:
    """Убрать обработанный PDF из inbound — не удалять, только переместить (SOUL.md)."""
    year_month = datetime.today().strftime("%Y-%m")
    dest_dir = SHIPS_DOCS / year_month
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / pdf.name
    if dest.exists():
        ts = datetime.now().strftime("%H%M%S")
        dest = dest_dir / f"{pdf.stem}_{ts}{pdf.suffix}"
    shutil.move(str(pdf), str(dest))
    return dest


def main():
    if len(sys.argv) < 2:
        sys.exit("Использование: supply_intake.py /path/to/file.pdf")
    pdf = Path(sys.argv[1])
    written, skipped_ships, escalations = process_pdf(pdf)
    summary = summarize(pdf.name, written, skipped_ships, escalations)
    print("\n" + summary)
    send_telegram(summary)
    dest = move_processed(pdf)
    log("MOVE", f"→ {dest.relative_to(Path.home() / '.openclaw')}")


if __name__ == "__main__":
    main()
