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
- Версия: 2026.5.20
- Gateway: Node.js, порты 18789/18791 (loopback), systemd
- Telegram бот: @Lisa_Local_Bot
- Память: LanceDB (autoCapture: false, autoRecall: false)
- Embeddings: nomic-embed-text через Ollama
- Веб-поиск: SearXNG

### Системные инструменты
```bash
# PDF → текст
pdftotext /path/file.pdf /path/out.txt
# PDF → PNG (для анализа чертежей)
pdftoppm -r 150 -png /path/file.pdf /tmp/page
# Python PyMuPDF для сложной обработки
~/.openclaw/tools-venv/bin/python -c "import fitz; ..."
```

## Promoted From Short-Term Memory (2026-06-01)

<!-- openclaw-memory-promotion:memory:memory/2026-05-26-1230.md:9:12 -->
- assistant: Привет, Вадим! Что делаем? assistant: ⚠️ Something went wrong while processing your request. Please try again, or use /new to start a fresh session. user: [OpenClaw heartbeat poll] assistant: HEARTBEAT_OK [score=0.883 recalls=0 avg=0.620 source=memory/2026-05-26-1230.md:9-12]
<!-- openclaw-memory-promotion:memory:memory/2026-05-26-1230.md:13:16 -->
- user: [OpenClaw heartbeat poll] assistant: HEARTBEAT_OK user: [OpenClaw heartbeat poll] assistant: HEARTBEAT_OK [score=0.883 recalls=0 avg=0.620 source=memory/2026-05-26-1230.md:13-16]

## Promoted From Short-Term Memory (2026-06-02)

<!-- openclaw-memory-promotion:memory:memory/2026-05-28-2231.md:9:9 -->
- user: Conversation info (untrusted metadata): [score=0.853 recalls=0 avg=0.620 source=memory/2026-05-28-2231.md:9-9]
<!-- openclaw-memory-promotion:memory:memory/2026-05-28-2231.md:12:15 -->
- "chat_id": "telegram:299387691", "message_id": "1131", "sender_id": "299387691", "sender": "Vadim Vin", [score=0.853 recalls=0 avg=0.620 source=memory/2026-05-28-2231.md:12-15]
