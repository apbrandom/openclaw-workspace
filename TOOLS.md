# TOOLS.md

Заметки о локальных инструментах. Какие инструменты существуют — OpenClaw знает сам.

## Vault

- **Путь:** `/home/apbrandom/.openclaw/workspace/vault`
- Obsidian: Open Folder as Vault → выбрать эту папку

### Карта папок

| Папка / файл | Что это | Кто пишет | Руками? |
|---|---|---|---|
| `ships/myship/` | MD-карточки своих барж (ATLAS_1, TISA, PRUT, TURAN). Источник истины: Tier-1 (позиция/статус/журнал) + Tier-2 (тех.характеристики) | скрипты (`tier1_pipeline.py`) | ❌ только скрипты |
| `ships/craneship/` | MD-карточки крановых/прочих судов | скрипты | ❌ только скрипты |
| `ship_cards/` | HTML-рендер карточек под Telegram. Пересобирается из `ships/*.md` при каждом прогоне | `tier1_pipeline.py` | ❌ выход пайплайна, перезапишется |
| `ships_docs/{SHIP}/{YEAR}/` | Детальные документы судов из PDF-интейка (АПП, сертификаты) | `process_app.py` | ⚠️ выход скрипта |
| `events/` | Журнал важных событий (АПП-акты и пр.) | смешанно | ✅ можно |
| `locations.md`, `tugboats.md` | Справочники: локации, буксиры | вручную | ✅ можно |
| `ship_audit.md` | Отчёт ночного аудита целостности карточек | аудит-скрипт | ❌ выход скрипта |

**«Руками не трогать»** = файл является выходом пайплайна. Ручная правка теряется при следующем прогоне скрипта и рассинхронит MD↔HTML. Правка таких данных — только через скрипты.

## Ship Document Intake

- **Inbound PDF:** `/home/apbrandom/.openclaw/media/inbound/`
- **Скрипт:** `/home/apbrandom/.openclaw/workspace/skills/ship-doc-parser/process_app.py`
- **Запуск:** `/home/apbrandom/.openclaw/tools-venv/bin/python .../process_app.py`
- **Vision model:** `qwen3-vl:latest` через Ollama

## Python venv

- **Путь:** `/home/apbrandom/.openclaw/tools-venv/bin/python`
- Установлены: PyMuPDF (fitz), requests, и скрипты ship-update
