# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

## Vault & Obsidian

- **OBSIDIAN_VAULT:** `/home/apbrandom/.openclaw/workspace/vault`
  Открыть в Obsidian: Open Folder as Vault → выбрать эту папку.
  Структура: `ships/` (карточки), `events/` (АПП и события), `ships_docs/` (PDF по судам).

## Ship Document Intake

- **Inbound PDF:** `/home/apbrandom/.openclaw/media/inbound/`
- **Скрипт обработки:** `/home/apbrandom/.openclaw/workspace/skills/ship-doc-parser/process_app.py`
- **Запуск:** `/home/apbrandom/.openclaw/tools-venv/bin/python /home/apbrandom/.openclaw/workspace/skills/ship-doc-parser/process_app.py`
- **Vision model:** `qwen3-vl:latest` через `http://localhost:11434`

## Related

- [Agent workspace](/concepts/agent-workspace)
