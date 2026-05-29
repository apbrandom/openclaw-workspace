---
name: ship-update
description: Детерминированное создание и обновление карточек судов (vault/ships/*.md)
---

# ship-update

Пять детерминированных скриптов:

- **`tier1_pipeline.py`** — **ГЛАВНЫЙ** для Tier-1 forwarded-сообщений: resolve → update → send_card одним вызовом
- `resolve_ship.py` — резолвит свободный текст → каноническое имя
- `update_ship.py` — обновляет существующую карточку (Tier-1 поля + история)
- `render_card.py` — рендерит HTML-карточку для Telegram (Шаблон 2)
- `create_ship.py` — создаёт пустую craneship-карточку из шаблона

**Используй ТОЛЬКО эти скрипты для правки/создания `vault/ships/*.md`.** НЕ используй Edit/Write напрямую — frontmatter и секции легко повредить.

## tier1_pipeline.py

Для Tier-1 (forwarded dispatcher message) — ЕДИНСТВЕННЫЙ правильный инструмент. Делает всё: resolve → update vault → send card к указанному chat_id.

```bash
echo '{
  "name": "BP_01",
  "position": "РПР №3",
  "status": "на якоре",
  "last_update_dt": "2026-05-20 14:10",
  "events": ["14:10 — встали на якорь в РПР №3"]
}' | /home/apbrandom/.openclaw/tools-venv/bin/python \
  /home/apbrandom/.openclaw/workspace/skills/ship-update/tier1_pipeline.py \
  --chat-id {CHAT_ID}
```

Выход: `✓ {CANONICAL}: карточка отправлена`. Это и есть твой ответ пользователю.

## render_card.py

Читает vault-файл → выводит готовую HTML-строку для Telegram (parse_mode=HTML). **Используй вместо ручного форматирования карточки.**

### Вызов

```bash
/home/apbrandom/.openclaw/tools-venv/bin/python \
  /home/apbrandom/.openclaw/workspace/skills/ship-update/render_card.py \
  --name MODUS
```

С резолвингом алиаса (кириллица, любой регистр):

```bash
/home/apbrandom/.openclaw/tools-venv/bin/python \
  /home/apbrandom/.openclaw/workspace/skills/ship-update/render_card.py \
  --name Модус --auto-resolve
```

Или через JSON stdin:

```bash
echo '{"name":"MODUS"}' | /home/apbrandom/.openclaw/tools-venv/bin/python \
  /home/apbrandom/.openclaw/workspace/skills/ship-update/render_card.py
```

### Ответ

Готовая HTML-строка на stdout. Отправь её в Telegram дословно с `parse_mode=HTML`.
Exit 0 — успех. Exit 2 — ошибка (сообщение в stderr).

## resolve_ship.py

Резолвит любое написание имени судна (кириллица, латиница, любой регистр) → каноническое имя файла. Проверяет имена файлов, frontmatter `name:` и `aliases:`. **Всегда вызывай перед update_ship.py или create_ship.py.**

### Вызов

```bash
echo '{"query":"Модус"}' | /home/apbrandom/.openclaw/tools-venv/bin/python \
  /home/apbrandom/.openclaw/workspace/skills/ship-update/resolve_ship.py
```

### Ответ

```json
{"found": true, "canonical": "MODUS", "path": "vault/ships/craneship/MODUS.md"}
```
или
```json
{"found": false, "query": "Неизвестное"}
```

- `found: true` → используй `canonical` как `name` для `update_ship.py`
- `found: false` → судно не наше. Для Tier-1 (forwarded msg): упомяни имя в событии нашего судна. Не задавай вопросов.
- Если ответ содержит `"partial": true` → совпадение нечёткое, уточни у пользователя

## update_ship.py

Заменяет 2 поля в `## Текущее положение`, добавляет события в `## История событий`, обновляет `last_updated:` в frontmatter.

## Вызов

```bash
echo '<JSON>' | /home/apbrandom/.openclaw/tools-venv/bin/python \
  /home/apbrandom/.openclaw/workspace/skills/ship-update/update_ship.py [--auto-resolve]
```

Флаг `--auto-resolve`: если `name` не совпадает с именем файла напрямую, скрипт автоматически ищет по aliases и frontmatter `name:`. Позволяет передавать кириллические имена без предварительного вызова `resolve_ship.py`.

## Параметры (JSON)

| Поле              | Обязат. | Формат                                | Описание                                          |
|-------------------|---------|---------------------------------------|---------------------------------------------------|
| `name`            | да      | `"TISA"`                              | Имя файла без `.md` (из `ls vault/ships/`)        |
| `position`        | нет     | `"Причал 24"`                         | Заменяет поле `Позиция:` — район/локация из списка в AGENTS.md |
| `status`          | нет     | `"грузовые"`                          | Заменяет поле `Статус:` — операционный статус из списка в AGENTS.md |
| `tugboat`         | нет (но обязат. для барж) | `"SIROKO"`              | Заменяет поле `Буксир:` — каноническое имя буксира. Только для type=баржа. |
| `last_update_dt`  | нет     | `"2026-05-18 14:58"`                  | Формат `YYYY-MM-DD HH:MM`. Заменяет `Обновлено:` + frontmatter `last_updated:` |
| `events`          | нет     | `["2026-05-17 12:30 — ...", ...]`     | Каждый элемент → новая строка в `## История событий`. Дубли игнорируются. |
| `type`            | нет     | `"буксир"`, `"баржа"`, `"контейнеровоз"`, ... | Заменяет `type:` в frontmatter. Свободный текст. |

## Семантика полей

- **Позиция** — где судно находится физически. Канонические значения из списка локаций в AGENTS.md: `Причал 1..24`, `Рейд-1/2/3`, `Пролив`, `Канал`, `Док`, и т.д. Незнакомая локация — пиши как услышал и предупреди.
- **Статус** — что судно сейчас делает. Канонические значения из списка статусов: `на якоре`, `на ходу`, `грузовые`, `швартовка`, `ожидание`, `в ремонте`, `буксировка`. Свободного текста избегай.

## Поведение

- Ищет файл в `vault/ships/myship/{name}.md` затем в `vault/ships/craneship/{name}.md`
- Если не нашёл — ошибка с листингом известных имён
- Каждое поле заменяется ЦЕЛИКОМ (никакой склейки старого + нового)
- События дедуплицируются по точному совпадению строки
- Событие без даты (`HH:MM — ...`) автоматически расширяется до `YYYY-MM-DD HH:MM — ...` используя дату из `last_update_dt` (или сегодня). Полный формат (`YYYY-MM-DD HH:MM — ...`) тоже принимается.
- Атомарная запись через tempfile
- Идемпотентно: повтор тех же данных = тот же результат

## Примеры

**Минимальный update:**
```bash
echo '{"name":"TISA","position":"Причал 24","status":"грузовые","last_update_dt":"2026-05-18 14:58"}' \
  | /home/apbrandom/.openclaw/tools-venv/bin/python /home/apbrandom/.openclaw/workspace/skills/ship-update/update_ship.py
```

**С событиями:**
```bash
echo '{
  "name":"PRUT",
  "position":"Пролив",
  "status":"на ходу",
  "last_update_dt":"2026-05-18 05:50",
  "events":[
    "2026-05-17 22:10 — начало выгрузки в Риану (буксир: Корсак)",
    "2026-05-18 04:30 — выгрузка завершена",
    "2026-05-18 05:50 — отошли от Рианы, следуют в пролив"
  ]
}' | /home/apbrandom/.openclaw/tools-venv/bin/python /home/apbrandom/.openclaw/workspace/skills/ship-update/update_ship.py
```

## Ошибки (exit code 2)

- `⚠ ship file not found: X.md (known: ...)` — имя из листинга, не угадывай
- `⚠ 'last_update_dt' must be 'YYYY-MM-DD HH:MM'` — формат жёсткий
- `⚠ status field not found in card` — карточка повреждена (нужен `## Текущее положение` с полями `Где:` и `Обновлено:`)
- `⚠ invalid JSON` — синтаксис
- `⚠ invalid event format (expected 'HH:MM — text' or 'YYYY-MM-DD HH:MM — text'): ...` — событие не прошло валидацию

## Анти-примеры событий (НЕЛЬЗЯ передавать в `events`)

Эти форматы завалят `update_ship.py` с exit 2 или (в старых версиях) записывали мусор в карточку:

| ✗ Неправильно | ✓ Правильно |
|---|---|
| `"15:00-16:00 драфт 16:00 погрузка"` | `"15:00 — драфт"` + `"16:00 — начало погрузки"` |
| `"15:00 погрузка"` (нет `— `) | `"15:00 — начало погрузки"` |
| `"погрузка в 16:00"` (слово перед временем) | `"16:00 — начало погрузки"` |
| `"18-30 окончание выгрузки"` (дефис вместо `:`) | `"18:30 — окончание выгрузки"` |

**Инцидент 18.05.2026 (MODUS):** пять forwarded-сообщений → в `events` попала строка `"15:00-16:00 драфт 16:00 начало погрузки"` (склейка двух событий) и дубль с qwen3-галлюцинацией символа `壳`. Оба теперь отклоняются на валидации.

**Правило расщепления:** несколько `HH:MM` в одном сообщении → несколько элементов в `events[]`, по одному на каждое время.

## Что update_ship.py НЕ делает

- Не создаёт новые карточки (см. `create_ship.py` ниже)
- Не правит `## Технические характеристики` (Tier 2, ночной dream-job)
- Не правит aliases в frontmatter
- Не отправляет в Notion (это `skills/obsidian/notion_sync.py`)

## add_location.py

Добавляет или обновляет строку в `vault/locations.md` — справочнике локаций (причалы, рейды, проливы → к каким портам относятся). Используй когда Вадим даёт уточнение: «24 причал — это порт Кавказ», «Рейд-3 — Кавказ», «Пролив — это Керченский».

### Вызов

```bash
echo '{"location":"Причал 24","port":"Порт Кавказ","aliases":["24 причал","у 24"]}' \
  | /home/apbrandom/.openclaw/tools-venv/bin/python \
    /home/apbrandom/.openclaw/workspace/skills/ship-update/add_location.py
```

### Параметры (JSON)

| Поле       | Обязат. | Формат                      | Описание                              |
|------------|---------|-----------------------------|---------------------------------------|
| `location` | да      | `"Причал 24"`               | Канонический. Идёт в `Позиция:` карточек. |
| `port`     | да      | `"Порт Кавказ"`             | Родительский порт/район.              |
| `aliases`  | нет     | `["24 причал","у 24"]`      | Варианты написания в сообщениях.      |

### Поведение

- Существующая локация (match по имени, регистр-нечувствительно) → port обновляется, алиасы мерджатся
- Каноническое написание сохраняется от первой записи. Если в новом запросе регистр другой — variant добавляется в алиасы.
- Новая локация → строка appended в конец таблицы
- Идемпотентно

## create_ship.py

Создаёт пустую craneship-карточку в `vault/ships/craneship/{NAME}.md` из шаблона.

**Когда вызывать:** только после явного подтверждения от владельца («да, это судно Craneship»). НЕ создавай по своей инициативе.

### Вызов

```bash
echo '{"name":"RIANA","aliases":["Riana","Риана","Рианой","Риану"]}' \
  | /home/apbrandom/.openclaw/tools-venv/bin/python \
    /home/apbrandom/.openclaw/workspace/skills/ship-update/create_ship.py
```

### Параметры (JSON)

| Поле      | Обязат. | Формат                  | Описание                                       |
|-----------|---------|-------------------------|------------------------------------------------|
| `name`    | да      | `"RIANA"`               | UPPERCASE_WITH_UNDERSCORES. Это будет имя файла. |
| `aliases` | нет     | `["Riana","Риана",...]` | Все падежи и варианты написания (Лиза будет матчить по ним) |

### Поведение

- Отказ, если файл уже есть в `vault/ships/{name}.md` или `vault/ships/craneship/{name}.md`
- Шаблон: frontmatter с пустыми полями, секции `## Текущее положение`, `## История событий`, `## Технические характеристики`, `## Документы`
- `last_updated:` = сегодня
- После создания вызывай `update_ship.py` для записи первого положения и событий
