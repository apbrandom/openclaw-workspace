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

## Nightly cron (03:00) — separate job, not here

- Vault consistency (required fields in vault/ships/*.md)
- Temp files cleanup (`/tmp/page-*.png`, etc.)
- SQLite size check (`~/.openclaw/memory/main.sqlite`)
- Disk usage (`df -h`)
- Memory distillation: recent `memory/YYYY-MM-DD.md` → `MEMORY.md`

## Hourly cron (:00) — separate job, not here

- Telegram chat → distill to `memory/YYYY-MM-DD.md`
- Clear/archive processed messages

---

*Heavy tasks → nightly cron. Exact timing → cron. Batch periodic → here.*
