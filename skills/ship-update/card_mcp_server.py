#!/usr/bin/env python3
"""MCP server: детерминированные операции с карточками судов в обход модели.

Два tool'а:
- `card`   — показать существующую карточку (read-only) → send_card.py
- `update` — записать новые Tier-1 факты и прислать свежую карточку
             → tier1_pipeline.py (resolve → update vault → send card)

`card` зовётся и slash-командой `/ship_card` (command-dispatch: tool,
см. skills/ship-card/SKILL.md), и моделью по голому имени судна.
`update` зовёт модель, когда в сообщении есть новые оперативные факты.

Запуск (stdio) задаётся регистрацией в openclaw.json через `openclaw mcp set`.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

PYTHON = "/home/apbrandom/.openclaw/tools-venv/bin/python"
SEND_CARD = Path(__file__).parent / "send_card.py"
TIER1_PIPELINE = Path(__file__).parent / "tier1_pipeline.py"

mcp = FastMCP("ship")


@mcp.tool()
def card(command: str = "", commandName: str = "", skillName: str = "") -> str:
    """ПОКАЗАТЬ существующую карточку судна (read-only): отрендерить и отправить в чат. command = имя судна (алиас или каноническое). После успешного вызова ответь ровно NO_REPLY — карточка уже в чате. ⛔ НЕ для новых фактов: если в сообщении есть свежие данные (позиция, статус, времена, «ошвартовались/встал/отошёл») — это ОБНОВЛЕНИЕ, зови tool update, а не сюда."""
    name = (command or "").strip()
    if not name:
        return "⚠ укажите имя судна: /card <судно>"
    try:
        result = subprocess.run(
            [PYTHON, str(SEND_CARD), "--name", name],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:  # noqa: BLE001 — surface any spawn failure to the chat
        return f"⚠ не удалось запустить send_card: {e}"
    err = (result.stderr or "").strip()
    out = (result.stdout or "").strip()
    if result.returncode != 0:
        return f"⚠ {err or out or 'send_card failed'}"
    # Карточка уже ушла в чат через send_card (Bot API). Явная директива
    # вместо пустой строки — пустой tool-result модель дописывает от себя.
    return "Карточка уже отправлена в чат. Ответь ровно: NO_REPLY"


@mcp.tool()
def update(
    name: str,
    position: str = "",
    status: str = "",
    tugboat: str = "",
    last_update_dt: str = "",
    events: list[str] | None = None,
) -> str:
    """ОБНОВИТЬ карточку судна новыми оперативными фактами (ошвартовались/встал/отошёл, позиция, статус, времена) и прислать свежую карточку в чат. Зови при ЛЮБОМ новом факте о судне. name = имя судна (алиас или каноническое, в т.ч. из шапки пересылки). status строго из: на якоре, на ходу, грузовые, швартовка, ожидание, в ремонте, буксировка. last_update_dt = 'YYYY-MM-DD HH:MM' — время ТЕКУЩЕГО сообщения/факта, не выдумывай будущую дату. events = список строк 'HH:MM — факт', одно время = одно событие. tugboat = буксир баржи: передавай ВСЕГДА, когда в сообщении баржа и буксир названы вместе («Тиса + Ирбис идут», «передача баржи Корсаку», «Корсак повёл Прут»); tugboat='—' = буксир отдал баржу. Связку и обновление второго судна пары скрипт делает сам — второй вызов НЕ нужен.
    ⛔ КАЖДЫЙ ВЫЗОВ ИЗОЛИРОВАН. position/status/events заполняй ТОЛЬКО тем, что явно сказано в ЭТОМ КОНКРЕТНОМ сообщении, которое обрабатываешь прямо сейчас. НИКОГДА не копируй значения полей из твоего предыдущего вызова этого тула для другого судна или сообщения — каждое сообщение своё, факты одного судна в карточку другого не попадают. Планы/намерения («планируем», «будут», «по прибытии») — это НЕ факт, эти поля для них не заполняй.
    После успешного вызова ответь ровно NO_REPLY — карточки уже в чате, текстовые подтверждения («карточка обновлена») запрещены. ⛔ НЕ для простого показа без новых фактов — там tool card."""
    payload: dict = {"name": (name or "").strip()}
    if not payload["name"]:
        return "⚠ 'name' обязателен: имя судна"
    if position.strip():
        payload["position"] = position.strip()
    if status.strip():
        payload["status"] = status.strip()
    if tugboat.strip():
        payload["tugboat"] = tugboat.strip()
    if last_update_dt.strip():
        payload["last_update_dt"] = last_update_dt.strip()
    if events:
        payload["events"] = [e.strip() for e in events if e and e.strip()]
    try:
        result = subprocess.run(
            [PYTHON, str(TIER1_PIPELINE)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:  # noqa: BLE001 — surface any spawn failure to the chat
        return f"⚠ не удалось запустить tier1_pipeline: {e}"
    if result.returncode != 0:
        err = (result.stderr or "").strip() or (result.stdout or "").strip()
        return f"⚠ {err or 'tier1_pipeline failed'}"
    # Свежая карточка уже ушла в рабочий чат. Явная директива вместо пустой
    # строки: пустой tool-result 14b «дописывает» сочинённым подтверждением.
    return "Карточка уже отправлена в чат. Ответь ровно: NO_REPLY"


if __name__ == "__main__":
    mcp.run()
