#!/bin/bash
# evening-report.sh — system health snapshot for Telegram
# Output: ready-to-send Telegram message, no LLM formatting needed

DATE=$(date +%Y-%m-%d)
DAILY="/home/apbrandom/.openclaw/workspace/memory/${DATE}.md"

# Service health
curl -sf http://localhost:11434/api/tags >/dev/null 2>&1 && OLLAMA="✅" || OLLAMA="⚠️ DOWN"
systemctl --user is-active openclaw-gateway 2>/dev/null | grep -q "^active$" && GW="✅" || GW="⚠️ DOWN"

# Disk
DISK_PCT=$(df /home/apbrandom --output=pcent 2>/dev/null | tail -1 | tr -d ' %')
[ "${DISK_PCT:-0}" -gt 85 ] && DISK="⚠️ ${DISK_PCT}%" || DISK="✅ ${DISK_PCT}%"

# VRAM (optional, skip if nvidia-smi absent)
VRAM=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null \
    | awk -F', ' '{printf "%s/%s MB", $1, $2}')
[ -z "$VRAM" ] && VRAM="н/д"

# Inbound count (PDFs only — voice/images handled separately)
PDF_COUNT=$(find /home/apbrandom/.openclaw/media/inbound -maxdepth 1 -name "*.pdf" 2>/dev/null | wc -l)
[ "$PDF_COUNT" -eq 0 ] && DOCS="нет" || DOCS="${PDF_COUNT} PDF"

# Incidents: lines with warning markers in today's daily note
INCIDENTS="нет"
if [ -f "$DAILY" ]; then
    FOUND=$(grep -i "⚠️\|ошибка\|error\|упал\|failed\|DOWN" "$DAILY" 2>/dev/null \
        | grep -v "^#\|SysHealth" | head -2 | sed 's/^[[:space:]]*//' | tr '\n' ' ')
    [ -n "${FOUND// }" ] && INCIDENTS="$FOUND"
fi

printf "🌙 Вечерняя сводка %s\n" "$DATE"
printf "• Ollama: %s  Gateway: %s\n" "$OLLAMA" "$GW"
printf "• Диск: %s  VRAM: %s\n" "$DISK" "$VRAM"
printf "• Входящих PDF: %s\n" "$DOCS"
printf "• Инциденты: %s\n" "$INCIDENTS"
