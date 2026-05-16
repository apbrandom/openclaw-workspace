#!/usr/bin/env /home/apbrandom/.openclaw/tools-venv/bin/python
"""
Night PDF runner — запускается в 00:00 systemd таймером, останавливается в 07:00.
Обрабатывает очередь из queue.json, сохраняет checkpoint после каждой страницы.
Утром шлёт итог в Telegram.
"""
import sys, json, base64, subprocess, re, time, argparse
from datetime import datetime, time as dtime
from pathlib import Path

import fitz  # PyMuPDF
import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import pdf_queue

STOP_AT   = dtime(7, 0)
OLLAMA    = "http://localhost:11434/api/generate"
VL_MODEL  = "qwen3-vl:latest"
VAULT     = Path("/home/apbrandom/.openclaw/workspace/vault")
SHIPS_DOCS = VAULT / "ships_docs"
TELEGRAM_CHAT_ID = 299387691

GENERIC_PROMPT = (
    "Это страница технического судового документа. "
    "Извлеки: номер раздела/страницы если видно, заголовок, тип (акт/инструкция/сертификат/схема/таблица/прочее), "
    "ключевые данные (даты, имена, числа, характеристики).\n"
    "Формат: JSON. Поля: section, title, doc_type, key_data, text_summary.\n"
    "Только JSON, без markdown, без пояснений."
)


def get_bot_token() -> str | None:
    try:
        data = json.loads((Path.home() / ".openclaw/openclaw.json").read_text())
        return data.get("channels", {}).get("telegram", {}).get("botToken")
    except Exception:
        return None


def send_telegram(msg: str):
    token = get_bot_token()
    if not token:
        print(f"[tg] {msg}")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        print(f"[tg error] {e}")


def should_stop() -> bool:
    return datetime.now().time() >= STOP_AT


def render_page_png(pdf_path: Path, page_num: int) -> Path:
    doc = fitz.open(str(pdf_path))
    page = doc[page_num]
    mat = fitz.Matrix(2.0, 2.0)  # 2x scale ≈ 150 dpi
    pix = page.get_pixmap(matrix=mat)
    out = Path(f"/tmp/night_page_{page_num:04d}.png")
    pix.save(str(out))
    doc.close()
    return out


def vl_extract(png: Path) -> dict:
    img_b64 = base64.b64encode(png.read_bytes()).decode()
    req = {
        "model": VL_MODEL,
        "prompt": GENERIC_PROMPT,
        "images": [img_b64],
        "stream": False,
        "options": {"temperature": 0.1},
    }
    req_file = Path("/tmp/night_vl_req.json")
    req_file.write_text(json.dumps(req))
    r = subprocess.run(
        ["curl", "-s", OLLAMA, "-d", f"@{req_file}"],
        capture_output=True, text=True, timeout=300,
    )
    raw = json.loads(r.stdout)["response"].strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw, "parse_error": True}


def load_checkpoint(result_dir: Path) -> dict:
    cp = result_dir / ".checkpoint.json"
    if cp.exists():
        return json.loads(cp.read_text())
    return {"results": []}


def save_checkpoint(result_dir: Path, data: dict):
    cp = result_dir / ".checkpoint.json"
    cp.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def process_item(item: dict) -> str:
    """Process one queue item. Returns 'done' | 'stopped' | 'failed'."""
    pdf = Path(item["path"])
    if not pdf.exists():
        pdf_queue.mark_failed(item["id"], "файл не найден")
        return "failed"

    doc = fitz.open(str(pdf))
    total_pages = doc.page_count
    doc.close()

    result_dir = SHIPS_DOCS / "queue_results" / item["id"]
    result_dir.mkdir(parents=True, exist_ok=True)

    cp_data = load_checkpoint(result_dir)
    start_page = item.get("checkpoint_page", 0)

    def log(tag, msg):
        print(f"[{tag:<8}] {msg}", flush=True)

    log("PDF", f"Получен файл: {item['filename']} ({item['pages']} стр, ≈{item['estimated_minutes']} мин)")
    if start_page > 0:
        log("RESUME", f"Продолжаю с checkpoint: стр {start_page}/{total_pages}")
    else:
        log("INIT", f"Старт обработки — {total_pages} страниц")

    for page_num in range(start_page, total_pages):
        if should_stop():
            pdf_queue.update_checkpoint(item["id"], page_num)
            save_checkpoint(result_dir, cp_data)
            log("STOP", f"07:00 — сохраняю checkpoint на стр {page_num}/{total_pages}")
            return "stopped"

        t = time.time()
        log("RENDER", f"Стр {page_num + 1}/{total_pages} — конвертирую в PNG...")
        try:
            png = render_page_png(pdf, page_num)
            log("VL", f"Запускаю {VL_MODEL} для стр {page_num + 1}...")
            extracted = vl_extract(png)
            elapsed = time.time() - t
            title = extracted.get("title") or extracted.get("doc_type") or "—"
            log("VL", f"Готово за {elapsed:.0f} сек  →  {title}")
            png.unlink(missing_ok=True)
        except Exception as e:
            log("ERROR", f"Стр {page_num + 1}: {e}")
            extracted = {"error": str(e)}

        cp_data["results"].append({"page": page_num, "data": extracted})
        pdf_queue.update_checkpoint(item["id"], page_num + 1)
        save_checkpoint(result_dir, cp_data)
        log("CP", f"Checkpoint сохранён: {page_num + 1}/{total_pages} стр")

    # Write final summary markdown
    summary_path = result_dir / f"{item['filename']}_summary.md"
    lines = [f"# {item['filename']}\n\n{total_pages} страниц · обработано {datetime.now().strftime('%Y-%m-%d')}\n\n"]
    for r in cp_data["results"]:
        d = r["data"]
        lines.append(f"## Стр {r['page'] + 1}\n")
        if "parse_error" in d:
            lines.append(f"```\n{d.get('raw','')}\n```\n")
        else:
            if d.get("title"):
                lines.append(f"**{d['title']}**\n")
            if d.get("doc_type"):
                lines.append(f"Тип: {d['doc_type']}\n")
            if d.get("text_summary"):
                lines.append(f"{d['text_summary']}\n")
        lines.append("\n")
    summary_path.write_text("".join(lines), encoding="utf-8")

    pdf_queue.mark_done(item["id"], str(result_dir))
    log("DONE", f"Файл обработан полностью → {result_dir.relative_to(VAULT.parent.parent)}")
    return "done"


def syslog(msg):
    print(f"[SYSTEM  ] {msg}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="запустить без проверки времени")
    args = parser.parse_args()

    now = datetime.now()
    syslog(f"Night runner запущен: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    if not args.force and should_stop():
        syslog("Время после 07:00 — плановый выход. Для ручного запуска: --force")
        sys.exit(0)

    items = pdf_queue.get_pending()
    if not items:
        syslog("Очередь пуста — нечего обрабатывать.")
        send_telegram("🌙 Ночная обработка: очередь пуста.")
        return

    total = len(items)
    total_pages = sum(i["pages"] - i.get("checkpoint_page", 0) for i in items)
    syslog(f"Очередь: {total} файлов · ~{total_pages} стр · плановый стоп в 07:00")
    send_telegram(
        f"🌙 *Ночная обработка началась*\n"
        f"{total} файлов · ~{total_pages} стр · стоп в 07:00"
    )

    stats = {"done": [], "stopped": [], "failed": []}

    for item in items:
        if should_stop():
            stats["stopped"].append(item["filename"])
            continue
        result = process_item(item)
        stats[result].append(item["filename"])

    remaining = pdf_queue.get_pending()
    remaining_min = sum(
        round((i["pages"] - i.get("checkpoint_page", 0)) * pdf_queue.SECONDS_PER_PAGE / 60)
        for i in remaining
    )

    syslog("─" * 48)
    if stats["done"]:
        syslog(f"Завершено: {len(stats['done'])} файлов — " + ", ".join(stats["done"]))
    if stats["stopped"]:
        syslog(f"Прервано по таймеру (07:00): " + ", ".join(stats["stopped"]))
    if stats["failed"]:
        syslog(f"Ошибки: " + ", ".join(stats["failed"]))
    if remaining:
        syslog(f"В очереди осталось: {len(remaining)} файлов · ~{remaining_min} мин → следующей ночью")
    else:
        syslog("Очередь очищена полностью.")

    lines = ["🌅 *Ночная обработка завершена*\n"]
    if stats["done"]:
        lines.append(f"✅ Готово ({len(stats['done'])}): " + ", ".join(f"`{f}`" for f in stats["done"]))
    if stats["stopped"]:
        lines.append(f"⏸ Прервано (07:00): " + ", ".join(f"`{f}`" for f in stats["stopped"]))
    if stats["failed"]:
        lines.append(f"❌ Ошибки: " + ", ".join(f"`{f}`" for f in stats["failed"]))
    if remaining:
        lines.append(f"\nОсталось {len(remaining)} файлов · ~{remaining_min} мин → следующей ночью")
    else:
        lines.append("\nОчередь очищена 🎉")
    send_telegram("\n".join(lines))


if __name__ == "__main__":
    main()
