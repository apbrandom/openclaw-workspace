## Система и инфраструктура

### ОС и окружение
- WSL2 Ubuntu 26.04 LTS, ядро 6.6.87.2-microsoft-standard
- Пользователь: apbrandom, Docker НЕ используется
- .wslconfig: memory=22GB, processors=10, swap=8GB
- Железо: Minisforum X1 Pro, HX370, 32 GB DDR5, RTX 5070 Ti eGPU (16 GB VRAM)

### Локальная LLM
- Ollama на порту 11434 (loopback only)
- Активная модель: Qwen3 14B FP8 (~12.6 GB VRAM + 3.4 GB RAM)
- num_ctx: 32768, thinking: off
- Дополнительные: qwen3-vl (VL задачи), nomic-embed-text (embeddings)

### OpenClaw
- Версия: 2026.5.28
- Gateway: Node.js, порты 18789/18791 (loopback), systemd
- Telegram бот: @Lisa_Local_Bot (username/адрес; display name — «LisaDaemonBot», это НЕ адрес)
- Память: миграция LanceDB→QMD в процессе (см. project_qmd_memory_migration)
- Embeddings: nomic-embed-text через Ollama
- Веб-поиск: SearXNG сконфигурирован, но НЕ установлен — web_search мёртв

### Системные инструменты
```bash
# PDF → текст
pdftotext /path/file.pdf /path/out.txt
# PDF → PNG (для анализа чертежей)
pdftoppm -r 150 -png /path/file.pdf /tmp/page
# Python PyMuPDF для сложной обработки
~/.openclaw/tools-venv/bin/python -c "import fitz; ..."
```

