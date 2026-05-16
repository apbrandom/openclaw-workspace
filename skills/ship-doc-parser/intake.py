#!/usr/bin/env /home/apbrandom/.openclaw/tools-venv/bin/python
"""
Smart PDF intake.
Usage: intake.py /path/to/file.pdf

- Маленький файл (≤ 5 стр или ≤ 2 мин) → process_app.py немедленно
- Большой → в очередь + Telegram уведомление
"""
import sys, json, subprocess
from pathlib import Path
import fitz  # PyMuPDF

HERE    = Path(__file__).parent
PROCESS = HERE / "process_app.py"
QUEUE   = HERE / "pdf_queue.py"

SMALL_PAGES   = 5
SMALL_MINUTES = 2
SECONDS_PER_PAGE = 22
TELEGRAM_CHAT_ID = 299387691

OPENCLAW_JSON = Path.home() / ".openclaw/openclaw.json"


def get_bot_token() -> str | None:
    try:
        data = json.loads(OPENCLAW_JSON.read_text())
        return data.get("channels", {}).get("telegram", {}).get("botToken")
    except Exception:
        return None


def send_telegram(msg: str):
    token = get_bot_token()
    if not token:
        print(f"[telegram] нет токена, сообщение: {msg}")
        return
    import requests
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        print(f"[telegram] ошибка: {e}")


def count_pages(pdf_path: Path) -> int:
    doc = fitz.open(str(pdf_path))
    n = doc.page_count
    doc.close()
    return n


def human_size(path: Path) -> str:
    mb = path.stat().st_size / 1_048_576
    return f"{mb:.1f} MB"


def main():
    if len(sys.argv) < 2:
        sys.exit("Использование: intake.py /path/to/file.pdf")

    pdf = Path(sys.argv[1])
    if not pdf.exists():
        sys.exit(f"Файл не найден: {pdf}")

    pages = count_pages(pdf)
    estimated_min = round(pages * SECONDS_PER_PAGE / 60)
    size_str = human_size(pdf)

    print(f"📄 {pdf.name}  {size_str}  {pages} стр  ≈{estimated_min} мин")

    if pages <= SMALL_PAGES or estimated_min <= SMALL_MINUTES:
        print("▶ Быстрый файл — обрабатываю сразу…")
        subprocess.run(
            ["/home/apbrandom/.openclaw/tools-venv/bin/python", str(PROCESS), str(pdf)],
            check=True,
        )
        return

    # Большой файл — в очередь
    sys.path.insert(0, str(HERE))
    import pdf_queue
    item = pdf_queue.add(str(pdf), pages)

    nights_needed = ""
    if estimated_min > 420:  # > 7 hours
        nights = estimated_min / 420
        nights_needed = f" (~{nights:.1f} ночи)"

    msg = (
        f"📥 *Новый файл в очереди*\n"
        f"`{pdf.name}`\n"
        f"{size_str} · {pages} стр · ≈{estimated_min} мин{nights_needed}\n"
        f"Старт в 00:00. ID: `{item['id']}`"
    )
    print(msg)
    send_telegram(msg)


if __name__ == "__main__":
    main()
