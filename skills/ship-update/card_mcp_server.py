#!/usr/bin/env python3
"""MCP server: детерминированный показ карточки судна в обход модели.

Один tool `card`. OpenClaw зовёт его через slash-команду с `command-dispatch:
tool` (см. SKILL.md), передавая `{command, commandName, skillName}`, где
`command` = сырой текст после слэша (имя судна). Tool запускает send_card.py —
тот резолвит алиас, рендерит HTML-карточку и шлёт её в рабочий чат.

Запуск (stdio) задаётся регистрацией в openclaw.json через `openclaw mcp set`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

PYTHON = "/home/apbrandom/.openclaw/tools-venv/bin/python"
SEND_CARD = Path(__file__).parent / "send_card.py"

mcp = FastMCP("ship")


@mcp.tool()
def card(command: str = "", commandName: str = "", skillName: str = "") -> str:
    """ПОКАЗАТЬ существующую карточку судна (read-only): отрендерить и отправить в чат. command = имя судна (алиас или каноническое). ⛔ НЕ для новых фактов: если в сообщении есть свежие данные (позиция, статус, времена, «ошвартовались/встал/отошёл») — это ОБНОВЛЕНИЕ, гони его через tier1_pipeline.py (скилл ship-update), а не сюда."""
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
    # Карточка уже ушла в чат через send_card (Bot API). Возвращаем пусто,
    # чтобы не было второго сообщения «карточка отправлена» поверх карточки.
    return ""


if __name__ == "__main__":
    mcp.run()
