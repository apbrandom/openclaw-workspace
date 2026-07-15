---
name: ship-card
description: Показать карточку судна по имени — детерминированно, в обход модели
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: ship__card
command-arg-mode: raw
---

# ship-card

Слэш-команда `/ship_card <судно>` для показа карточки судна.

Это **детерминированная** команда: `command-dispatch: tool` направляет её
напрямую в MCP-tool `ship__card` (сервер `ship`, см. `card_mcp_server.py` в
скилле `ship-update`), минуя модель. Tool запускает `send_card.py --name <судно>`,
который резолвит алиас, рендерит HTML-карточку и шлёт её в рабочий чат.

Аргумент после `/ship_card` (имя судна) передаётся в tool как поле `command`.

Примеры: `/ship_card Тиса`, `/ship_card BP-01`, `/ship_card MODUS`.

`disable-model-invocation: true` — команда работает только как слэш (из меню
Telegram или набором), модель её не вызывает и не видит в системном промпте.
