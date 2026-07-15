# HEARTBEAT.md

Checklist for the heartbeat loop (default: every 30 min).
Alert dedup state: `memory/heartbeat-state.json`.

## Every run

### 1. Health checks
```bash
curl -s http://localhost:11434/api/tags > /dev/null && echo OK || echo FAIL
systemctl --user is-active openclaw-gateway
```
**If either fails:** send Telegram to `299387691` → "⚠️ [service] is down, waiting for manual restart." Write current unix timestamp to `lastOllamaAlert`/`lastGatewayAlert` in state.json and do NOT repeat the alert until the service recovers.

### 2. Inbound documents
```bash
ls /home/apbrandom/.openclaw/media/inbound/
```
If new files found → run intake pipeline (AGENTS.md → Ship Document Intake).

### 3. Parser queue
```bash
cat /home/apbrandom/.openclaw/workspace/skills/ship-doc-parser/queue.json
```
If an entry is stuck >30 min → report to Vadim.

## Rules

- If nothing needs attention, reply exactly `HEARTBEAT_OK`.
- **Never write results or reports into this file.** Findings go to daily memory (`memory/YYYY-MM-DD.md`). This file is instructions only.

## Cron jobs (reference — run by cron, NOT by heartbeat)

| Время | Задание |
|---|---|
| 01:00 | inbound-dedup |
| 02:07 | system-health-nightly (детерминированный скрипт) |
| 09:00 пн-пт | fleet-morning-brief |
| 23:00 | daily-telegram-memory |

<!-- 2026-07-02: удалены dream-morning-report, ship-audit-daily, evening-system-report — вне трёх основных функций (сводка, АПП, карточки). -->
