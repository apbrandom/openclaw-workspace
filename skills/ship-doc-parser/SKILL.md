---
name: ship-doc-parser
description: Парсинг входящих PDF судовых документов (АПП, сертификаты, акты снабжения склад→судно) через vision LLM qwen3-vl → обновление vault/ships карточек И/ИЛИ запись позиций в Notion-инвентарь судна (АТЛАС 1/ТИСА/ПРУТ)
---

# SKILL: ship-doc-parser

**Version:** 2.0 (vision-primary)
**Author:** built from real АПП sample (CRANESHIP 117/OPS)
**Scope:** Parse incoming PDF documents related to vessel operations and update vault cards
**Called by:** AGENTS.md → `Program: Ship Document Intake`
**Primary extraction:** `qwen3-vl:latest` via Ollama (vision LLM)
**Fallback extraction:** `pdftotext -layout` + `ocrmypdf` (если Ollama недоступен)

---

## INTAKE DECISION (обязательно перед обработкой)

**Шаг 0 — определи подтип документа** (до выбора точки входа). Открой первую страницу (или спроси владельца, если прислано с подписью). Признаки:

| Подтип | Признаки | Точка входа |
|--------|----------|-------------|
| **APP_SUPPLY** (склад→судно, снабжение) | Одно поле «Наименование» под датой = получатель. Штамп «СКЛАД» в блоке «Передал». Часто МНОГО страниц, где **каждая страница — отдельный акт на своё судно/баржу** | `supply_intake.py` напрямую, **минуя `intake.py`** |
| **APP 117/OPS** (два судна/лица) | Отдельные поля ship_from/ship_to, Ф.И.О. передающего и принимающего, форма 117/OPS | `intake.py` (как раньше) |
| Не ясно / нестандартная форма | — | эскалация Вадиму, не гадать |

```bash
# APP_SUPPLY — обрабатывает все страницы сам, пишет в Notion-инвентарь (АТЛАС 1/ТИСА/ПРУТ)
/home/apbrandom/.openclaw/tools-venv/bin/python \
  /home/apbrandom/.openclaw/workspace/skills/ship-doc-parser/supply_intake.py \
  /path/to/file.pdf
```

**Почему отдельная точка входа:** `intake.py` считает страницы как «одна длинная мысль» (page-count-порог калибровался под старую форму 117/OPS, ~22 сек/стр thinking-моделью). Для APP_SUPPLY это неверно — там каждая страница независима и быстра (~13 сек/стр на `qwen3-vl:8b-instruct`), 20-страничный файл — это ~4-5 минут, а не повод в ночную очередь.

**Большой пакет (архив за несколько месяцев, 50+ страниц, разовый бэклог):** это НЕ живой TG-сценарий — не пытайся прогнать сама в разговоре (сессия и ожидание пользователя не рассчитаны на десятки минут). Сообщи Вадиму: «Файл большой (`N` стр, ≈`M` мин) — предлагаю прогнать отдельно (Claude Code / ночной прогон), не в этом чате» и не запускай сама.

**Для APP 117/OPS — точка входа не изменилась**, всегда `intake.py`, не `process_app.py` напрямую:

```bash
/home/apbrandom/.openclaw/tools-venv/bin/python \
  /home/apbrandom/.openclaw/workspace/skills/ship-doc-parser/intake.py \
  /path/to/file.pdf
```

| Условие | Действие |
|---------|----------|
| ≤ 5 страниц **или** ≤ 2 мин оценка | `process_app.py` — немедленно |
| > 5 страниц | Добавить в `queue.json` + Telegram уведомление |

**Оценка:** ~22 сек/страница (qwen3-vl, RTX 5070 Ti). Файл 200 стр ≈ 73 мин.

**Ночной runner** (`night_runner.py`) запускается автоматически в 00:00 (systemd таймер `openclaw-pdf-night.timer`), останавливается в 07:00 с сохранением checkpoint. Утром шлёт итог в Telegram. Если не успел за ночь — продолжит следующей ночью.

**Проверить очередь:**
```bash
/home/apbrandom/.openclaw/tools-venv/bin/python \
  /home/apbrandom/.openclaw/workspace/skills/ship-doc-parser/pdf_queue.py
```

**Ручной запуск ночного runner (тест):**
```bash
/home/apbrandom/.openclaw/tools-venv/bin/python \
  /home/apbrandom/.openclaw/workspace/skills/ship-doc-parser/night_runner.py --force
```

**Результаты** большого файла → `vault/ships_docs/queue_results/{id}/`  
**Логи** ночного runner → `~/.openclaw/logs/night-runner.log`

---

## WHEN TO ACTIVATE

- PDF в `~/.openclaw/media/inbound/*.pdf`
- Команды владельца: «обработай файл», «разбери АПП», «пришёл документ»
- Имя файла содержит: АПП, акт, передача, приём, накладная, сертификат, снабжение

---

## DOCUMENT TYPES

| Код | Название | Форма | Идентификатор | Обработчик |
|-----|----------|-------|---------------|------------|
| APP | Акт Приёма-Передачи (два судна) | 117/OPS (CRANESHIP) | По полю «Судно» (ship_from/ship_to) | `process_app.py` |
| APP_SUPPLY | Акт приёма-передачи (склад→судно, снабжение) | Многостраничный, страница=акт | Одно поле «Наименование» = получатель, штамп «Передал» = склад | `supply_intake.py` |
| CERT | Certificate (class/survey) | varies | По IMO Number | — |
| PSC | Port State Control | varies | По IMO Number | — |
| UNKNOWN | Нераспознанный тип | — | escalate | — |

**Различить APP vs APP_SUPPLY:** если в документе одно поле «Наименование» (получатель) и штамп «СКЛАД» в «Передал» — это APP_SUPPLY, писать в Notion-инвентарь (`supply_intake.py`). Если есть отдельные поля ship_from/ship_to с Ф.И.О. передающего и принимающего — это старая форма 117/OPS, пайплайн vault (`process_app.py`).

---

## APP_SUPPLY → NOTION INVENTORY (снабжение склад→судно)

**Запуск:**
```bash
/home/apbrandom/.openclaw/tools-venv/bin/python \
  /home/apbrandom/.openclaw/workspace/skills/ship-doc-parser/supply_intake.py \
  /path/to/file.pdf
```

**Что делает:** рендерит каждую страницу PDF (одна страница = один акт на одно судно/баржу), извлекает через `qwen3-vl:8b-instruct` (не thinking-вариант — см. NOTES), резолвит получателя в одну из 3 отслеживаемых баз (АТЛАС 1 / ТИСА / ПРУТ — конфиг `notion_inventory.json`), разбивает составные строки таблицы, пишет черновые строки (`Статус=В пути`, `Проверено=false`) в Notion, шлёт сводку в Telegram.

**Не наш флот** (Гриндейл, Риана, Корсак, Сайга, Титан-3, Сироко, Модус, Ван Гог, Феникс-1 и т.п.) — пропускается молча (это не ошибка, просто вне текущего охвата 3 судов), фигурирует в сводке как «пропущено».

**Эскалация в TG** (сводка после каждого файла), не блокирует запись:
- строка не разбилась (счёт имён ≠ счёту количеств) — пишется одной строкой с пометкой
- строка перечёркнута в скане — пишется с пометкой «проверить актуальность»
- дата нечитаема или в будущем — не проставляется, дата=null
- `Ед.` вне {шт,компл,место,пар,кг,л,м} — пишется как есть с пометкой в `Примечание`

**Дедуп:** `skills/ship-doc-parser/notion_processed.json` — ключ `sha256(pdf)+стр+судно+имя+qty`. Повторный запуск на том же файле ничего не дублирует. **Ручные правки строк в Notion делать через API с тем же ключом** (или просто руками в UI) — не пересоздавать вручную с произвольным ключом, иначе следующий запуск задублирует (см. инцидент 17.07 в ROADMAP).

---

## STEP 1 — FIND PDF AND RENDER → PNG

**Inbound directory (абсолютный путь, не менять):**
```
/home/apbrandom/.openclaw/media/inbound/
```

```bash
# Найти свежий PDF (исключить manual/)
PDF=$(find /home/apbrandom/.openclaw/media/inbound -maxdepth 1 -name "*.pdf" | sort | tail -1)
echo "Processing: $PDF"

# Рендер в PNG — НЕ pdftotext напрямую
pdftoppm -r 200 -png "$PDF" /tmp/app_page
ls /tmp/app_page-*.png
```

Если только одна страница — используется `/tmp/app_page-1.png`.
Если страниц несколько — обрабатывать каждую отдельно (как правило в АПП одна страница).

**ВАЖНО: pdftotext не использовать как первый шаг.** АПП — сканы, текстового слоя нет. Сначала всегда pdftoppm → PNG → qwen3-vl.

---

## STEP 2 — EXTRACT FIELDS VIA qwen3-vl

### Python helper (рекомендуемый способ)

```python
import json, base64, requests

def vl_extract(image_path, prompt):
    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()
    req = {
        "model": "qwen3-vl:latest",
        "prompt": prompt,
        "images": [img_b64],
        "stream": False,
        "options": {"temperature": 0.1}
    }
    r = requests.post("http://localhost:11434/api/generate", json=req, timeout=120)
    return r.json()["response"]
```

### Bash через файловый запрос (для CLI)

```bash
python3 -c "
import json, base64
with open('/tmp/app_page-1.png', 'rb') as f:
    img = base64.b64encode(f.read()).decode()
req = {
    'model': 'qwen3-vl:latest',
    'prompt': open('/tmp/prompt.txt').read(),
    'images': [img],
    'stream': False,
    'options': {'temperature': 0.1}
}
json.dump(req, open('/tmp/req.json', 'w'))
"
curl -s http://localhost:11434/api/generate -d @/tmp/req.json | python3 -c "import json,sys; print(json.load(sys.stdin)['response'])"
```

### Промпт для АПП (type: APP)

```
Это скан Акта Приёма-Передачи (АПП, форма 117/OPS, CRANESHIP).
Извлеки все поля в JSON. Если поле пустое или нечитаемо — поставь null.

Поля:
- date (DD.MM.YYYY)
- form_number (например "117/OPS")
- ship_from
- person_from (Ф.И.О.)
- role_from (должность)
- ship_to
- person_to
- role_to
- destination (поле "Для последующей передачи на:")
- items: [{name, unit, qty}]

Отвечай ТОЛЬКО валидным JSON, без markdown, без пояснений.
```

### Время выполнения

~20–30 секунд на страницу на текущем железе (RTX 5070 Ti, qwen3-vl:latest 6.1 GB).
Если выполнение > 120 сек — Ollama завис, fallback на tesseract (см. Step 2-fallback).

### Step 2-fallback — если Ollama недоступен

Проверить:
```bash
curl -sf http://localhost:11434/api/tags >/dev/null || echo "OLLAMA_DOWN"
```

Если `OLLAMA_DOWN` — использовать tesseract:
```bash
ocrmypdf --language rus+eng --force-ocr --deskew --clean --quiet /path/to/file.pdf /tmp/ocr.pdf
pdftotext -layout /tmp/ocr.pdf /tmp/parsed.txt
```

Затем извлечь поля regex'ом или вызовом `qwen3:14b` (текстовая модель) с промптом «Извлеки JSON из текста АПП».

Качество fallback хуже: вертикальная черта `|` часто означает цифру `1`, единица измерения путается. Делать только если vision-pipeline недоступен.

---

## STEP 3 — CLASSIFY DOCUMENT TYPE

VL обычно возвращает поля сразу — тип ясен из контекста. Для дополнительной защиты:

- Если `form_number == "117/OPS"` или в тексте видно `АКТ ПРИЁМА-ПЕРЕДАЧИ` → `type: APP`
- Если `CERTIFICATE OF CLASS` → `type: CERT`
- Если `PORT STATE CONTROL` → `type: PSC`
- Иначе → `type: UNKNOWN` → эскалация (Step 6)

---

## STEP 4 — IDENTIFY VESSEL IN VAULT

### Алгоритм

```
Для каждого имени из [ship_from, ship_to, destination], где значение не null:
  1. NORMALIZE(имя) — см. ниже
  2. Для каждой карточки в vault/ships/*.md:
       сравнить NORMALIZE(имя) против NORMALIZE(name) и NORMALIZE каждого alias
  3. Совпадение → судно нашего флота, переход к Step 5
  4. Нет совпадений → внешнее судно, только логировать в событие
```

### Функция NORMALIZE

```python
import re

def normalize(s: str) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    # Префиксы типа судна
    s = re.sub(r'^(м/б|т/х|м/в|т/б|m/v|m/b|barge|vessel|ship|теплоход|буксир)\s*', '', s)
    # Разделители и точки
    s = re.sub(r'[\s\-_.]+', '', s)
    return s
```

### Примеры

| Из VL | NORMALIZE | Совпадение |
|-------|-----------|------------|
| `Атлас 1` | `атлас1` | ATLAS_1 (alias `АТЛАС 1` → `атлас1`) ✅ |
| `Atlas-1` | `atlas1` | ATLAS_1 (name `ATLAS_1` → `atlas1`) ✅ |
| `м/б ТИСА` | `тиса` | TISA ✅ |
| `Prut` | `prut` | PRUT ✅ |

### Edge case: латиница vs кириллица

`атлас1` ≠ `atlas1` после lowercase. Перекрытие — за счёт кириллических aliases в каждой карточке. Если не сопоставилось — эскалация (Step 6, «Новое судно»).

---

## STEP 5 — UPDATE VAULT

### 5a. Update ship frontmatter

Перед правкой:
```bash
wc -c /home/apbrandom/.openclaw/workspace/vault/ships/{SHIP}.md
```

Targeted edit поля `last_updated`:
```yaml
last_updated: {date from document}
```

**Правило:** обновлять только если `date документа > current last_updated`. Если `date == null` — пропустить обновление frontmatter, событие всё равно записать.

После правки:
```bash
wc -c /home/apbrandom/.openclaw/workspace/vault/ships/{SHIP}.md
```

Если размер уменьшился — откатить, эскалировать.

### 5b. Create event record

`vault/events/YYYY-MM-DD_APP_{SHIP_FROM}_{SHIP_TO}.md`

Имена файлов — **канонический name из карточки** (`ATLAS_1`, `TISA`). Внешние суда — нормализованное имя из документа (`КОРСАК`). Если `ship_to == null` — суффикс `_NA`.

```markdown
---
type: APP
date: 2026-05-16
form: 117/OPS
ship_from: ATLAS_1
ship_to: null
destination: "Мех цех (берег)"
source_pdf: ~/.openclaw/media/processed/2026-05/file.pdf
extraction_method: qwen3-vl
---

## Акт приёма-передачи

**Передал:** Кибкалов А.А. (СМХ, ATLAS_1)
**Принял:** —
**Для передачи:** Мех цех (берег)

## Позиции

| № | Наименование | Ед. | Кол-во |
|---|--------------|-----|--------|
| 1 | Шланги гидравлические (РВД) крана Liebherr. Б.У. | Шт. | 7 |
```

### 5c. Move processed PDF

```bash
YEAR_MONTH=$(date -d "${DOC_DATE:-today}" +%Y-%m 2>/dev/null || date +%Y-%m)
mkdir -p ~/.openclaw/media/processed/$YEAR_MONTH
mv ~/.openclaw/media/inbound/{file.pdf} ~/.openclaw/media/processed/$YEAR_MONTH/
```

---

## STEP 6 — ESCALATION RULES

Эскалация owner'у в Telegram (`telegram:299387691`):

| Condition | Message |
|-----------|---------|
| Ollama упал и нет `ocrmypdf` | «❌ Vision-LLM недоступен и OCR не установлен. Не могу обработать `{filename}`.» |
| VL вернул невалидный JSON 2 раза подряд | «⚠️ Vision-LLM нестабилен на `{filename}`. Файл в `inbound/manual/`.» |
| Тип документа UNKNOWN | «❓ Неизвестный тип документа: `{filename}`. Подскажи как классифицировать.» |
| Судно не найдено в vault | «🚢 Новое судно: `{ship_name}` в `{filename}`. Создать карточку или добавить alias?» |
| Конфликт данных | «⚠️ Конфликт: `{ship_name}` — старое `{X}`, новое `{Y}` в `{filename}`. Что оставить?» |
| Все ключевые поля null | «📄 `{filename}` обработан, но почти все поля пусты. Документ не дозаполнен? Проверь.» |

**Не эскалировать** если штатно — Step 7.

---

## STEP 7 — SUCCESS RESPONSE

Краткий ответ в чат:

```
✅ АПП обработан (16.05.2026)
• ATLAS_1 → берег (Мех цех): Шланги РВД Liebherr × 7
• Передал: Кибкалов А.А. (СМХ)
• Событие: vault/events/2026-05-16_APP_ATLAS_1_NA.md
• PDF: processed/2026-05/
```

Без объяснений процесса.

---

## NOTES

- **`qwen3-vl:latest` (thinking-вариант) непригоден для JSON-экстракции** — модель уходит в бесконечный внутренний `thinking`-стрим (виден в отдельном поле ответа Ollama) и не успевает выдать `response` даже с бюджетом 12 288 токенов на генерацию. `supply_intake.py` использует `qwen3-vl:8b-instruct` (тот же класс 8.8B, ~6 GB, тот же VRAM) — отвечает сразу, ~12–13 сек/страница. `process_app.py`/`night_runner.py` пока НЕ мигрированы на instruct-вариант (используют старую `vl_utils.VL_MODEL`) — если форма 117/OPS тоже перестанет отвечать, причина та же.
- Vision-pipeline тестировался на реальном АПП 117/OPS — даёт почти все поля корректно за ~22 сек.
- Если в документе **рукописная дата** — VL может её прочитать (tesseract не может).
- Поле «Принял» часто пустое в первичном АПП — это норма, не эскалировать.
- Подписи и печати игнорировать.
- Два судна в одном АПП — оба логировать, оба искать в vault.
- `wc -c` до/после правки vault — обязателен (SOUL.md).
- Никогда не удалять исходный PDF — только перемещать в `processed/` или `inbound/manual/`.
- Большие PDF (> 5 стр) **не обрабатывать вручную** — только через `intake.py` → очередь → ночной runner.
- Если `qty` или `unit` чтение явно некорректно (например `qty: 0` для строки с наименованием) — оставить в событии с пометкой `?` и эскалация на проверку.
