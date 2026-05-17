#!/usr/bin/env python3
"""
Дедупликация inbound/ по basename (часть до ---).
Оставляет самый новый файл, остальные перемещает в inbound/manual/.
"""
import os
import shutil
from collections import defaultdict

INBOUND = "/home/apbrandom/.openclaw/media/inbound"
MANUAL = os.path.join(INBOUND, "manual")
os.makedirs(MANUAL, exist_ok=True)

groups = defaultdict(list)
for fname in os.listdir(INBOUND):
    fpath = os.path.join(INBOUND, fname)
    if not os.path.isfile(fpath):
        continue
    key = fname.split("---")[0]
    groups[key].append(fpath)

moved = 0
for key, files in groups.items():
    if len(files) < 2:
        continue
    files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    for dup in files[1:]:
        dest = os.path.join(MANUAL, os.path.basename(dup))
        shutil.move(dup, dest)
        print(f"moved: {os.path.basename(dup)}")
        moved += 1

print(f"done: {moved} duplicates moved to manual/")
