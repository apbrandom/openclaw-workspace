# УСТАРЕЛО — НЕ ИСПОЛЬЗОВАТЬ

Этот файл заменён правилами в `AGENTS.md` (раздел "Forwarded Message").

Для Tier-1 forwarded сообщений используй ТОЛЬКО `tier1_pipeline.py`:

```bash
echo '{
  "name": "{SHIP}",
  "position": "{ПОЗИЦИЯ}",
  "status": "{СТАТУС}",
  "last_update_dt": "{YYYY-MM-DD HH:MM}",
  "events": ["{HH:MM} — {текст}", ...]
}' | /home/apbrandom/.openclaw/tools-venv/bin/python \
  /home/apbrandom/.openclaw/workspace/skills/ship-update/tier1_pipeline.py \
  --chat-id {CHAT_ID}
```

НЕ редактируй vault/ships/*.md напрямую через Edit/Write.
НЕ создавай файлы в vault/events/ вручную.
