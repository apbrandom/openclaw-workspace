#!/usr/bin/env /home/apbrandom/.openclaw/tools-venv/bin/python
"""
PDF Queue manager — add, pop, checkpoint, status.
Queue file: skills/ship-doc-parser/queue.json
"""
import json, uuid
from datetime import datetime
from pathlib import Path

QUEUE_FILE = Path(__file__).parent / "queue.json"
SECONDS_PER_PAGE = 22  # empirical for qwen3-vl on RTX 5070 Ti


def _load() -> dict:
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text())
    return {"version": 1, "items": []}


def _save(q: dict):
    QUEUE_FILE.write_text(json.dumps(q, indent=2, ensure_ascii=False))


def add(pdf_path: str, pages: int) -> dict:
    q = _load()
    estimated_minutes = round(pages * SECONDS_PER_PAGE / 60)
    item = {
        "id": str(uuid.uuid4())[:8],
        "path": str(pdf_path),
        "filename": Path(pdf_path).name,
        "pages": pages,
        "estimated_minutes": estimated_minutes,
        "added_at": datetime.now().isoformat(timespec="seconds"),
        "status": "pending",
        "checkpoint_page": 0,
        "result_dir": None,
        "error": None,
    }
    q["items"].append(item)
    _save(q)
    return item


def get_pending() -> list:
    return [i for i in _load()["items"] if i["status"] in ("pending", "processing")]


def update_checkpoint(item_id: str, page: int):
    q = _load()
    for item in q["items"]:
        if item["id"] == item_id:
            item["checkpoint_page"] = page
            item["status"] = "processing"
            break
    _save(q)


def mark_done(item_id: str, result_dir: str = None):
    q = _load()
    for item in q["items"]:
        if item["id"] == item_id:
            item["status"] = "done"
            item["result_dir"] = result_dir
            item["done_at"] = datetime.now().isoformat(timespec="seconds")
            break
    _save(q)


def mark_failed(item_id: str, reason: str):
    q = _load()
    for item in q["items"]:
        if item["id"] == item_id:
            item["status"] = "failed"
            item["error"] = reason
            break
    _save(q)


def status_summary() -> str:
    items = _load()["items"]
    if not items:
        return "Очередь пуста."
    counts = {"pending": 0, "processing": 0, "done": 0, "failed": 0}
    total_min = 0
    for i in items:
        counts[i["status"]] = counts.get(i["status"], 0) + 1
        if i["status"] in ("pending", "processing"):
            done = i.get("checkpoint_page", 0)
            remaining = max(0, i["pages"] - done)
            total_min += round(remaining * SECONDS_PER_PAGE / 60)
    lines = [
        f"pending={counts['pending']} processing={counts['processing']} "
        f"done={counts['done']} failed={counts['failed']}",
        f"Осталось ~{total_min} мин суммарно",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(status_summary())
    print("\nДетали:")
    for i in _load()["items"]:
        print(f"  [{i['status']:10}] {i['filename']} ({i['pages']} стр, ≈{i['estimated_minutes']} мин) cp={i['checkpoint_page']}")
