# Program: Ship Document Intake

**Authority:** Принимать судовые PDF из Telegram-ingress, парсить, обновлять `vault/ships/*.md` и создавать события в `vault/events/`. Перемещать обработанные файлы в `~/.openclaw/media/processed/`.

**Trigger:**
- Входящее сообщение в Telegram с прикреплённым PDF
- Новый файл в `/home/apbrandom/.openclaw/media/inbound/` (абсолютный путь)
- Команды владельца: «обработай файл», «разбери АПП», «пришёл документ»

**Inbound directory (абсолютный путь):** `/home/apbrandom/.openclaw/media/inbound/`
**Processed directory:** `/home/apbrandom/.openclaw/media/processed/`

**Approval gate:**
- Штатная обработка (распознанный тип, судно найдено по name/alias) — **без аппрува**.
- Создание новой карточки судна — **требует аппрува** owner'a.
- Перезапись существующих полей карточки при конфликте — **требует аппрува**.

**Escalation:** owner на Telegram `telegram:299387691`

## Execution steps

1. Выполни команду:
   `/home/apbrandom/.openclaw/tools-venv/bin/python /home/apbrandom/.openclaw/workspace/skills/ship-doc-parser/process_app.py`
2. Дождись завершения (20–60 сек — работает qwen3-vl).
3. Перескажи вывод скрипта owner'у кратко: что передано, кем, кому, позиции, куда сохранено.
4. Синхронизируй обновлённую карточку судна в Notion:
   `/home/apbrandom/.openclaw/tools-venv/bin/python /home/apbrandom/.openclaw/workspace/skills/obsidian/notion_sync.py sync <ИМЯ_СУДНА>`
   Например: `notion_sync.py sync ATLAS_1`. Если sync упал — сообщи owner'у, не блокируй основной флоу.

Детали логики — в `skills/ship-doc-parser/SKILL.md`. Скрипт — в `skills/ship-doc-parser/process_app.py`.
Notion sync — в `skills/obsidian/notion_sync.py`, state — в `skills/obsidian/notion_state.json`.

## What NOT to do

- Не удалять исходный PDF. Только перемещать в `processed/` или `inbound/manual/`.
- Не создавать новые карточки судов автоматически — только через эскалацию.
- Не перезаписывать `last_updated` если дата документа меньше текущей.
- Не пересоздавать карточку целиком — только targeted edit полей.
- Не объяснять процесс в чате. Только результат.
- Не повторять эскалацию по тому же файлу — если owner не ответил, оставить в `inbound/manual/` и ждать.
