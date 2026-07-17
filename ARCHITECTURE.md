# ARCHITECTURE.md

Карта того, **как система устроена сейчас**: компоненты, кто кого вызывает, где границы. Не история (это `memory/YYYY-MM-DD.md`) и не спецификация поведения (это `ROADMAP.md`, R-XX). Синкать при структурных изменениях — новый скрипт, новая Notion-база, новый Program в AGENTS.md.

**Кто это читает:** только Claude Code, в начале своей сессии (см. `CLAUDE.md` → Session Protocol). Лиза этот файл в рантайме НЕ грузит — не раздувать её system prompt (см. `project_context_optimization_goal` в памяти).

**Если нужно узнать «что сломается, если я переименую файл X»** — не ищи ответ здесь, документ устареет быстрее кода. Используй `grep -rl "имя_файла" workspace/`.

---

## Два разных агента в одном воркспейсе

| | Claude Code (я) | Лиза |
|---|---|---|
| Модель | Opus (claude.ai) | Ollama qwen3:14b, thinking="low" |
| Роль | Настройка OpenClaw, инфраструктура, код | Повседневная работа: диспетч, документы, чат |
| Системный промпт | `CLAUDE.md` | `AGENTS.md` + `SOUL.md` + `IDENTITY.md` + `USER.md` + сегодняшний/вчерашний daily |
| Права на файлы | Read везде, Write/Edit по `settings.local.json` | Пишет vault/memory через свои скрипты, не руками (Red Lines в AGENTS.md) |
| Канал | Терминал / claude.ai | Telegram `@Lisa_Local_Bot`, два чата (299387691 личный, 7622255068 рабочий/суда) |

Границы: только Claude Code трогает `openclaw.json`, `AGENTS.md`, `SOUL.md`, скиллы (структурный слой). Лиза — повседневные данные (vault, memory, Notion) через уже написанные скрипты.

---

## Инфраструктура (процессы)

```
systemd --user
├── openclaw-gateway   Node.js, порты 18789/18791 (loopback)
│   └── agents/telegram/  — сессии Лизы (JSONL + trajectory JSONL)
├── ollama              порт 11434 (loopback), модели: qwen3:14b (primary),
│                        qwen3-vl:8b-instruct (VL-экстракция), qwen3-vl:latest (thinking-вариант,
│                        НЕ использовать для JSON-задач — см. project_qwen3vl_thinking_bug)
└── openclaw-pdf-night.timer → night_runner.py (00:00-07:00, очередь больших PDF)

cron (openclaw cron list): inbound-dedup, system-health-nightly, fleet-morning-brief
   + dream-nightly/dream-morning-report (память, см. project_qmd_memory_migration)
```

Конфиг: `~/.openclaw/openclaw.json` (структура, модели, каналы) + `~/.openclaw/.env` (секреты: NOTION_API_KEY, TELEGRAM_BOT_TOKEN, GATEWAY_AUTH_TOKEN — JSON-формат, не .env-синтаксис).

Диагностика живого хода агента без похода в Telegram: `openclaw agent --to <chat_id> --message "..." --deliver --json [--thinking off|low|medium|high|max]` — гоняет один ход через живой gateway, возвращает `executionTrace`/`toolSummary`/`systemPromptReport`.

---

## Программы (Programs) — что Лиза делает и чем

### 1. Диспетч-пайплайн (`AGENTS.md` → Program: Обработка диспетч-сообщений)

Вход: пересланное TG-сообщение с оперативным фактом о судне.

```
Лиза → tool ship__update → skills/ship-update/
  ├── tier1_pipeline.py   orchestration
  ├── resolve_ship.py     имя → каноничный stem (alias-резолв)
  ├── update_ship.py      пишет vault/ships/{myship,craneship}/{STEM}.md
  ├── render_card.py      md → HTML карточка
  └── card_mcp_server.py  MCP-сервер, шлёт карточку в TG (рабочий чат 7622255068)
```

Чтение статуса (без новых фактов) → tool `ship__card` → `send_card.py`. Новое судно → предлагает `create_ship.py`, не создаёт сама.

Хранилище: `vault/ships/{myship,craneship}/*.md` (Tier-1, каноничные данные) + `vault/ship_cards/*.html` (рендер) + `vault/events/*.md` (журнал) + `vault/tugboats.md`/`locations.md` (справочники).

**Известный риск (17.07):** `NO_REPLY` — директива, которую обязан вернуть tool, не то, что модель выбирает сама. `thinking="off"` эту гарантию не держал (см. `project_dispatch_no_reply_incident`). R-01e в ROADMAP.

### 2. Приём документов (`skills/ship-doc-parser/`)

Две независимые формы, **разные точки входа** (см. SKILL.md → INTAKE DECISION, Шаг 0):

```
PDF в inbound/
├── форма 117/OPS (два судна, ship_from/ship_to)
│   intake.py → process_app.py → vault/ships_docs/{SHIP}/{YEAR}/ + vault/events/
│   (VL-модель: qwen3-vl:latest — thinking-вариант, работает т.к. промпт короче)
│
└── форма «снабжение» (склад→судно, N страниц = N актов)
    supply_intake.py → notion_writer.py → Notion (3 базы-инвентаря)
    (VL-модель: qwen3-vl:8b-instruct — instruct-вариант, обязателен для JSON-задач)
    PDF после обработки → vault/ships_docs/_supply/{YEAR-MM}/
```

Большие пакеты (>5 стр форма 117/OPS) → `pdf_queue.py` → ночной `night_runner.py`. Форма «снабжение» быстрее (~13 сек/стр instruct vs ~22 сек/стр thinking) — свой порог, см. SKILL.md.

### 3. Судовой инвентарь (Notion) — `notion_inventory.json`

```
3 базы (АТЛАС 1 / ТИСА / ПРУТ), под страницей SuperIntendent.
Схема: Запчасть(title) · Кол-во · Ед. · Статус(В пути/В запасе/Установлено/Передано) ·
       Откуда · Куда · Дата · Проверено(checkbox) · АПП № · Примечание
Строка = позиция СЕЙЧАС (не леджер движений — решение 17.07, было по-другому).
Дедуп: skills/ship-doc-parser/notion_processed.json (по файлу) +
       nw.find_existing() (по смыслу: судно+имя+кол-во — ловит «тот же акт, другой скан»)
```

Старая база «АПП — Передачи запчастей» (леджер) архивирована 17.07, не используется.

### 4. Obsidian/Notion sync (`skills/obsidian/`)

Отдельно от инвентаря — синкает vault/ships карточки (характеристики, не остаток запчастей) в Notion per-ship страницы. `notion_sync.py sync <SHIP>`.

---

## Слой памяти

```
Лиза (рантайм)        MEMORY.md (главная сессия) + memory/YYYY-MM-DD.md (дневник) + QMD (BM25 поиск по vault)
Claude Code (я)        ~/.claude/projects/.../memory/*.md + MEMORY.md (индекс), см. system prompt правила
```

Это ДВЕ разные системы памяти с одинаковым названием файла — не путать. Лизина `MEMORY.md` в `workspace/`, моя — в `~/.claude/projects/.../memory/`.

---

## Агентская граница (принцип, не менять без обсуждения)

Детерминированные скрипты — ПОД агентской границей (валидация, запись файлов, рендер). Интерпретация входящего текста (диспетч vs документ, какое судно, какой факт) — НЕ скриптуется, это работа модели через вызов tools. Скрипт может отказать/эскалировать по чётким правилам (exit 2, partial match), но не подменяет суждение агента. См. `feedback_agentic_layers` в памяти.

---

## Известные слепые пятна / TODO

- `process_app.py`/`night_runner.py` не мигрированы на `qwen3-vl:8b-instruct` — держатся на thinking-варианте, который может не ответить на более сложном промпте (см. `project_qwen3vl_thinking_bug`).
- Нет единого health-check «Лиза реально отвечает на входящие» — баг 17.07 нашли только руками через grep по session-логам.
- `thinking="low"` глобально с 17.07 — не протестировано на реальном суточном трафике (см. task в памяти `project_dispatch_no_reply_incident`).
