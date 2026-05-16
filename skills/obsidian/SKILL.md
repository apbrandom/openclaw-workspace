# obsidian — Obsidian Vault Skill

> **Важно:** OpenClaw bundled skill "obsidian" (obsidian-cli) на этой системе **не работает** — нет obsidian-cli.
> Используй скрипты из этой папки напрямую (skill.py, notion_sync.py).

**Vault:** `/home/apbrandom/.openclaw/workspace/vault`  
**Ships:** `vault/ships/` (ATLAS_1, PRUT, TISA, TURAN)  
**Script:** `skills/obsidian/skill.py`  
**Approach:** file-based (без REST API; Local REST API плагин не установлен)

Obsidian на Windows видит vault через `\\wsl.localhost\Ubuntu\home\apbrandom\.openclaw\workspace\vault`.

## Команды

```bash
SKILL="/home/apbrandom/.openclaw/tools-venv/bin/python /home/apbrandom/.openclaw/workspace/skills/obsidian/skill.py"

# Создать заметку
$SKILL new "Название заметки"
$SKILL new "Inspection report" --folder inspections --ship ATLAS_1

# Поиск по vault
$SKILL search "главный двигатель"
$SKILL search "TURAN" --folder ships

# Список заметок
$SKILL list
$SKILL list ships

# Переместить заметку (обновляет [[wikilinks]] во всём vault)
$SKILL move "old/note" "new/folder/note"

# Удалить заметку (через trash если есть)
$SKILL delete "folder/note"

# Открыть заметку в Windows Obsidian (WSL2 → powershell URI)
$SKILL open ships/ATLAS_1
```

## Флаги `new`

| Флаг | Описание |
|---|---|
| `--folder <folder>` | Подпапка внутри vault (создаётся автоматически) |
| `--ship <SHIP>` | Добавить wikilink `[[ships/SHIP]]` и frontmatter `ship:` |

## Формат создаваемых заметок

```markdown
---
date: 2026-05-16
title: "Название"
ship: ATLAS_1          # если указан --ship
---

# Название

Судно: [[ships/ATLAS_1]]
```

## Vault/Ships — имена файлов

`ATLAS_1`, `PRUT`, `TISA`, `TURAN` — точное имя для `--ship`.

---

## Notion Sync

**Script:** `skills/obsidian/notion_sync.py`  
**State:** `skills/obsidian/notion_state.json` (page IDs, не удалять)  
**Parent:** Notion → SuperIntendent page

```bash
# Синхронизировать одно судно (после обновления vault/ships/<SHIP>.md)
/home/apbrandom/.openclaw/tools-venv/bin/python skills/obsidian/notion_sync.py sync ATLAS_1

# Синхронизировать все суда
/home/apbrandom/.openclaw/tools-venv/bin/python skills/obsidian/notion_sync.py sync

# Проверить статус (URL страниц в Notion)
/home/apbrandom/.openclaw/tools-venv/bin/python skills/obsidian/notion_sync.py status
```

**Когда запускать:** автоматически после каждого обновления `vault/ships/*.md` — см. AGENTS.md → Ship Document Intake, шаг 4.  
**Если sync упал** — сообщить owner'у, не блокировать основной флоу.
