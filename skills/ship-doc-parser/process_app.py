#!/usr/bin/env /home/apbrandom/.openclaw/tools-venv/bin/python
"""
Ship Document Intake — полный pipeline.
Запуск: python3 process_app.py [path/to/file.pdf]
Без аргумента — берёт последний PDF из inbound/.
"""
import sys, os, json, base64, subprocess, re, shutil
from datetime import datetime
from pathlib import Path

INBOUND    = Path("/home/apbrandom/.openclaw/media/inbound")
VAULT      = Path("/home/apbrandom/.openclaw/workspace/vault")
SHIPS      = VAULT / "ships"
EVENTS     = VAULT / "events"
SHIPS_DOCS = VAULT / "ships_docs"
OLLAMA     = "http://localhost:11434/api/generate"
VL_MODEL   = "qwen3-vl:latest"
PROMPT     = ("Это скан Акта Приёма-Передачи (АПП, форма 117/OPS, CRANESHIP). "
              "Извлеки все поля в JSON. Пустые/нечитаемые — null.\n"
              "Поля: date (DD.MM.YYYY), form_number, ship_from, person_from, role_from, "
              "ship_to, person_to, role_to, destination, items:[{name,unit,qty}].\n"
              "Только JSON, без markdown, без пояснений.")

TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z',
    'и':'i','й':'j','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r',
    'с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh',
    'щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
    '«':'','»':'','№':'N','"':"",'"':"",'\'':''
}

def translit(s):
    result = ""
    for c in s.lower():
        result += TRANSLIT.get(c, c)
    result = re.sub(r'[^a-z0-9\-]', '-', result)
    result = re.sub(r'-{2,}', '-', result).strip('-')
    return result[:40]

def find_pdfs():
    if len(sys.argv) > 1:
        return [Path(sys.argv[1])]
    pdfs = sorted(INBOUND.glob("*.pdf"))
    if not pdfs:
        sys.exit("❌ Нет PDF в inbound/")
    return pdfs

def render_png(pdf):
    subprocess.run(["pdftoppm", "-r", "200", "-png", str(pdf), "/tmp/app_page"],
                   check=True, capture_output=True)
    pages = sorted(Path("/tmp").glob("app_page-*.png"))
    if not pages:
        sys.exit("❌ pdftoppm не создал PNG")
    return pages[0]

def vl_extract(png):
    img_b64 = base64.b64encode(png.read_bytes()).decode()
    req = {"model": VL_MODEL, "prompt": PROMPT,
           "images": [img_b64], "stream": False, "options": {"temperature": 0.1}}
    req_file = Path("/tmp/vl_req.json")
    req_file.write_text(json.dumps(req))
    r = subprocess.run(["curl", "-s", OLLAMA, "-d", f"@{req_file}"],
                       capture_output=True, text=True, timeout=120)
    raw = json.loads(r.stdout)["response"].strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
    return json.loads(raw)

def normalize(s):
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"^(м/б|т/х|м/в|т/б|m/v|m/b|barge|vessel|ship|теплоход|буксир)\s*", "", s)
    s = re.sub(r"[\s\-_.\"«»]+", "", s)
    return s

def load_ships():
    ships = {}
    for f in SHIPS.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
        if not m:
            continue
        name = m.group(1).strip()
        aliases_raw = re.search(r"^aliases:\s*\n((?:  - .+\n)+)", text, re.MULTILINE)
        aliases = re.findall(r"  - (.+)", aliases_raw.group(1)) if aliases_raw else []
        keys = [normalize(name)] + [normalize(a) for a in aliases]
        ships[f.stem] = {"file": f, "name": name, "keys": keys, "text": text}
    return ships

def match_ship(raw_name, ships):
    key = normalize(raw_name)
    for stem, info in ships.items():
        if key in info["keys"]:
            return stem, info
    return None, None

def update_last_updated(info, doc_date):
    f = info["file"]
    old_size = f.stat().st_size
    text = info["text"]
    m = re.search(r"^last_updated:\s*(.+)$", text, re.MULTILINE)
    if m:
        current = m.group(1).strip()
        if doc_date and doc_date > current:
            new_text = text.replace(f"last_updated: {current}", f"last_updated: {doc_date}")
            f.write_text(new_text, encoding="utf-8")
            assert f.stat().st_size >= old_size, f"❌ {f} уменьшился!"
            return True
    return False

def canonical_ship(data, matched):
    """Вернуть канонический stem судна для именования файла."""
    for field in ("ship_from", "ship_to", "destination"):
        if field in matched:
            return matched[field]
    return "UNKNOWN"

def build_pdf_name(doc_type, doc_date, ship_stem, data):
    """Формирует имя файла вида APP_2026-05-16_ATLAS_1_Shlang-RVD.pdf"""
    items = data.get("items") or []
    desc = translit(items[0]["name"]) if items else "document"
    date_str = doc_date or datetime.today().strftime("%Y-%m-%d")
    return f"{doc_type}_{date_str}_{ship_stem}_{desc}.pdf"

def move_pdf(pdf, data, matched, doc_date):
    """Переместить PDF в vault/ships_docs/{SHIP}/{YEAR}/APP_....pdf"""
    ship_stem = canonical_ship(data, matched)
    year = (doc_date or datetime.today().strftime("%Y-%m-%d"))[:4]
    dest_dir = SHIPS_DOCS / ship_stem / year
    dest_dir.mkdir(parents=True, exist_ok=True)
    new_name = build_pdf_name("APP", doc_date, ship_stem, data)
    dest = dest_dir / new_name
    # Если файл с таким именем уже есть — добавить timestamp
    if dest.exists():
        ts = datetime.now().strftime("%H%M%S")
        new_name = new_name.replace(".pdf", f"_{ts}.pdf")
        dest = dest_dir / new_name
    shutil.move(str(pdf), str(dest))
    return dest

def write_event(data, matched, pdf_dest, doc_date):
    sf = data.get("ship_from") or "NA"
    st = data.get("ship_to") or "NA"
    sf_key = matched.get("ship_from", sf)
    st_key = matched.get("ship_to", st)
    fname = f"{doc_date or datetime.today().strftime('%Y-%m-%d')}_APP_{sf_key}_{st_key}.md"
    items_md = "\n".join(
        f"| {i+1} | {it.get('name','')} | {it.get('unit','')} | {it.get('qty','')} |"
        for i, it in enumerate(data.get("items") or [])
    )
    content = f"""---
type: APP
date: {data.get('date') or doc_date or 'unknown'}
form: {data.get('form_number') or '117/OPS'}
ship_from: {sf_key}
ship_to: {st_key}
destination: {data.get('destination') or 'null'}
source_pdf: {pdf_dest}
extraction_method: qwen3-vl
---

## Акт приёма-передачи

**Передал:** {data.get('person_from') or '?'} ({data.get('role_from') or '?'}, {sf_key})
**Принял:** {data.get('person_to') or '—'} ({data.get('role_to') or '—'}, {st_key}){f"{chr(10)}**Для передачи:** {data.get('destination')}" if data.get('destination') else ''}

## Позиции

| № | Наименование | Ед. | Кол-во |
|---|--------------|-----|--------|
{items_md}
"""
    event_file = EVENTS / fname
    EVENTS.mkdir(exist_ok=True)
    event_file.write_text(content, encoding="utf-8")
    return event_file

def process_one(pdf, ships):
    print(f"\n📄 PDF: {pdf.name}")

    print("🖼  Рендер PNG…")
    png = render_png(pdf)

    print("🤖 qwen3-vl извлекает поля…")
    data = vl_extract(png)
    print("   →", json.dumps(data, ensure_ascii=False))

    matched = {}
    for field in ("ship_from", "ship_to", "destination"):
        raw = data.get(field)
        if not raw:
            continue
        stem, info = match_ship(raw, ships)
        if stem:
            matched[field] = stem
            print(f"   🚢 {field}: {raw} → {stem}")
        else:
            print(f"   ⚠️  {field}: '{raw}' — внешнее")

    doc_date = None
    raw_date = data.get("date")
    if raw_date:
        try:
            doc_date = datetime.strptime(raw_date, "%d.%m.%Y").strftime("%Y-%m-%d")
        except Exception:
            pass

    for field, stem in matched.items():
        _, info = match_ship(data.get(field, ""), ships)
        if info and update_last_updated(info, doc_date):
            print(f"   ✏️  {stem}: last_updated → {doc_date}")

    pdf_dest = move_pdf(pdf, data, matched, doc_date)
    print(f"📦 PDF → {pdf_dest.relative_to(VAULT.parent.parent)}")

    event_file = write_event(data, matched, str(pdf_dest), doc_date)
    print(f"📝 Событие: {event_file.name}")

    items = data.get("items") or []
    items_str = ", ".join(f"{it.get('name','')} × {it.get('qty','?')}" for it in items)
    ship_from = matched.get("ship_from", data.get("ship_from", "?"))
    ship_to   = matched.get("ship_to",   matched.get("destination", data.get("destination", "?")))
    print(f"✅ {ship_from} → {ship_to}: {items_str}")


def main():
    pdfs = find_pdfs()
    total = len(pdfs)
    print(f"📂 Найдено файлов: {total}")

    ships = load_ships()
    ok, failed = 0, []

    for i, pdf in enumerate(pdfs, 1):
        print(f"\n[{i}/{total}]", end="")
        try:
            process_one(pdf, ships)
            ok += 1
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            failed.append(pdf.name)

    print(f"\n{'='*40}")
    print(f"Итого: {ok}/{total} обработано", end="")
    if failed:
        print(f", ошибки: {', '.join(failed)}")
    else:
        print()

if __name__ == "__main__":
    main()
