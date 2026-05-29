# TOOLS.md

Заметки о локальных инструментах. Какие инструменты существуют — OpenClaw знает сам.

## Vault

- **Путь:** `/home/apbrandom/.openclaw/workspace/vault`
- Структура: `ships/myship/`, `ships/craneship/`, `ships_docs/`, `events/`
- Obsidian: Open Folder as Vault → выбрать эту папку

## Ship Document Intake

- **Inbound PDF:** `/home/apbrandom/.openclaw/media/inbound/`
- **Скрипт:** `/home/apbrandom/.openclaw/workspace/skills/ship-doc-parser/process_app.py`
- **Запуск:** `/home/apbrandom/.openclaw/tools-venv/bin/python .../process_app.py`
- **Vision model:** `qwen3-vl:latest` через Ollama

## Python venv

- **Путь:** `/home/apbrandom/.openclaw/tools-venv/bin/python`
- Установлены: PyMuPDF (fitz), requests, и скрипты ship-update
