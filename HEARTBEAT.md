# HEARTBEAT.md

Checklist for the main heartbeat loop (~15 min intervals).
State is tracked in `memory/heartbeat-state.json`.

---

## Every run (~15 min)

### 1. Health checks
```bash
curl -s http://localhost:11434/api/tags > /dev/null && echo OK || echo FAIL
systemctl --user is-active openclaw-gateway
```
**If either fails:** send Telegram to `299387691` → "⚠️ [service] is down, waiting for manual restart." Do NOT repeat until it recovers.

### 2. Inbound documents
```bash
ls /home/apbrandom/.openclaw/media/inbound/
```
If files found → run intake pipeline (AGENTS.md → Ship Document Intake).

### 3. VRAM / RAM
```bash
nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader
free -h | grep Mem
```
Log anomalies to daily memory note. No action unless critical (VRAM >14 GB or RAM >20 GB).

---

## Every 30 min (gate: `last30` in state.json)

### 4. Queue check
```bash
cat /home/apbrandom/.openclaw/workspace/skills/ship-doc-parser/queue.json
```
If any entry is stuck >30 min → report to Vadim.

### 5. Workspace git status
```bash
git -C /home/apbrandom/.openclaw/workspace status --short
```
If uncommitted changes → note it, report if non-trivial.

---

## Cron jobs (отдельные задания, не heartbeat)

| Время | Задание | Что делает |
|---|---|---|
| `02:07` | `system-health-nightly` | temp cleanup, SQLite size, disk, port check |
| `03:00` | `dream-nightly` | vault health, memory distillation, inbound дедупликация, git commit |
| `03:00` | `Memory Dreaming Promotion` | managed by memory-core, LanceDB |
| `09:00` | `dream-morning-report` | отчёт о ночном dream → Telegram |
| `09:00 пн-пт` | `fleet-morning-brief` | сводка по флоту → Telegram |
| `21:00` | `evening-system-report` | вечерний отчёт систем → Telegram |
| `23:00` | `daily-telegram-memory` | дистиллировать Telegram-чат в daily memory |

---

*Heavy tasks → cron. Batch periodic checks → here (heartbeat). Exact timing → cron.*
