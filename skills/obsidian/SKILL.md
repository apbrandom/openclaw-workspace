# obsidian — Obsidian Vault Skill

**Vault:** `/home/apbrandom/.openclaw/workspace/vault`  
**Ships:** `vault/ships/` (ATLAS_1, PRUT, TISA, TURAN)  
**Script:** `skills/obsidian/skill.py`  
**Approach:** file-based (без REST API; Local REST API плагин не установлен)

Obsidian на Windows видит vault через `\\wsl.localhost\Ubuntu\home\apbrandom\.openclaw\workspace\vault`.

## Команды

```bash
# Создать заметку
python skills/obsidian/skill.py new "Название заметки"
python skills/obsidian/skill.py new "Inspection report" --folder inspections --ship ATLAS_1

# Поиск по vault
python skills/obsidian/skill.py search "главный двигатель"
python skills/obsidian/skill.py search "TURAN"

# Список заметок
python skills/obsidian/skill.py list
python skills/obsidian/skill.py list ships
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
