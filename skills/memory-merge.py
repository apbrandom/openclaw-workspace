#!/usr/bin/env python3
"""
Дефрагментация дневных файлов: memory/YYYY-MM-DD-HHMM.md → memory/YYYY-MM-DD.md.
Оригиналы переносятся в memory/.archived/.
Идемпотентен: уже архивированные файлы не трогает.
"""
import re
from pathlib import Path
from collections import defaultdict

MEMORY = Path("/home/apbrandom/.openclaw/workspace/memory")
ARCHIVE = MEMORY / ".archived"
ARCHIVE.mkdir(exist_ok=True)

SUFFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{4})\.md$")

groups = defaultdict(list)
for f in MEMORY.glob("*.md"):
    m = SUFFIX.match(f.name)
    if m:
        groups[m.group(1)].append((m.group(2), f))

merged_total = 0
for date, sessions in groups.items():
    sessions.sort(key=lambda x: x[0])
    target = MEMORY / f"{date}.md"

    if target.exists():
        out = target.read_text(encoding="utf-8").rstrip() + "\n"
    else:
        out = f"# {date}\n"

    for time, f in sessions:
        hh, mm = time[:2], time[2:]
        body = f.read_text(encoding="utf-8").strip()
        out += f"\n## Session {hh}:{mm}\n\n{body}\n"

    target.write_text(out, encoding="utf-8")
    for _, f in sessions:
        f.rename(ARCHIVE / f.name)
    print(f"merged: {date}.md ← {len(sessions)} sessions")
    merged_total += len(sessions)

print(f"done: {merged_total} files merged into daily notes")
