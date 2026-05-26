## Система и инфраструктура


### ОС и окружение
- Windows 11 хост
- WSL2 Ubuntu 26.04 LTS, ядро 6.6.87.2-microsoft-standard
- Пользователь: apbrandom (uid 1000, есть sudo)
- Docker НЕ используется
- OpenClaw работает прямо в WSL2 через systemd
- .wslconfig: memory=22GB, processors=10, swap=8GB

### Локальная LLM
- Ollama serve на порту 11434 (loopback only)
- Активная модель: Qwen3 14B FP8 (занимает ~16 GB: 12.6 GB VRAM + 3.4 GB RAM)
- Контекст модели: 40960 токенов (max); num_ctx (configured): 32768
- Температура для агентских задач: 0.1-0.3
- Дополнительные модели: qwen3-vl (6.1 GB), nomic-embed-text (0.27 GB)

### OpenClaw
- Версия: 2026.5.12
- Gateway: Node.js, порты 18789 и 18791 (loopback)
- Установлен через npm: ~/.npm-global/lib/node_modules/openclaw/
- Каталог данных: ~/.openclaw/
- Запускается автоматически через systemd при старте WSL2
- Подключён Telegram бот: @LisaDaemonBot
- Имя ассистента: Лиза
- Память: LanceDB (autoCapture: true, autoRecall: true)
- Embeddings: nomic-embed-text через Ollama
- Веб-поиск: SearXNG
- Скиллы активные: mcporter, oracle, notion

### Облачная LLM
- Claude Opus через подписку claude.ai
- Используется для настройки и оптимизации OpenClaw

### Архитектура памяти
- MEMORY.md — долгосрочная память (этот файл)
- memory/YYYY-MM-DD.md — ежедневный дневник
- vault/ships/ — карточки судов (YAML + markdown)
- vault/ships_docs/ — детальные документы по судам
- vault/events/ — журнал важных событий
- ~/.openclaw/memory/main.sqlite — session storage
- ~/.openclaw/tools-venv/ — Python venv с PyMuPDF

### Системные инструменты
1. Извлечь текст из PDF:
   pdftotext /путь/к/файлу.pdf /путь/к/выводу.txt
2. Конвертировать PDF в PNG (для анализа чертежей):
   pdftoppm -r 150 -png /путь/к/файлу.pdf /tmp/страница
3. Python с PyMuPDF для сложной обработки:
   ~/.openclaw/tools-venv/bin/python -c "import fitz; ..."
✅ pdftotext и pdftoppm установлены (версия 26.01.0)
✅ PyMuPDF установлен в ~/.openclaw/tools-venv/

### Цели использования
1. База данных судов с автоматическим сбором информации
   - Активные суда: ATLAS 1, TISA, PRUT, TURAN
   - Хранение: vault/ships/ (карточки) + vault/ships_docs/ (документы)
   - Правила: Лиза автоматически обновляет карточки при упоминании судна
2. Анализ российского фондового рынка (МосБиржа)
   - Финансовая отчётность, мультипликаторы, дивиденды
   - Сводки для самостоятельного принятия решений
3. Инженерные консультации по морской тематике
   - Корпус, двигатели, электрика, навигация
4. Автоматизация бизнес-процессов суперинтенданта
   - Обработка входящих документов (счета, APO, отчёты ТО)
   - Контроль сроков сертификатов
   - Nextcloud интеграция (планируется)

### Профиль пользователя
- Имя: Вадим
- Профессия: суперинтендант, инженер-механик (судовые энергетические установки)
- Опыт: iOS разработка (написал несколько приложений)
- Стиль работы: любит разбираться глубоко, нужны пояснения по программированию
- Наставник по OpenClaw: Claude Opus (claude.ai)

### Состояние на 15.05.2026
- ✅ OpenClaw 2026.5.12 работает стабильно через systemd
- ✅ Ollama активна, Qwen3 14B FP8 загружена
- ✅ Compaction настроен (reserveTokensFloor: 8000)
- ✅ LanceDB активна (autoCapture + autoRecall)
- ✅ Все порты только loopback (безопасно)
- ✅ WSL2 ограничен 22 GB RAM через .wslconfig
- ✅ PDF инструменты установлены
- ✅ SOUL.md обновлён с правилами кратких ответов
- ⚠️ Карточки TISA, PRUT, TURAN требуют заполнения
- ⚠️ Nextcloud синхронизация не настроена
- ⚠️ Мониторинг МосБиржи не настроен
- ⚠️ Tailscale не настроен (удалённый доступ)
