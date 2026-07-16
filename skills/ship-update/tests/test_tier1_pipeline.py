#!/usr/bin/env python3
"""Тест дедупа карточек в tier1_pipeline.py.

Не гоняет send_card.py (реально шлёт в Telegram, нет dry-run/SHIP_WORKSPACE
override) — только чистую функцию разбора вывода update_ship.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tier1_pipeline import updated_ships  # noqa: E402


class UpdatedShipsTest(unittest.TestCase):
    def test_single(self) -> None:
        out = "✓ TISA updated (vault/ships/myship/TISA.md)"
        self.assertEqual(updated_ships(out), ["TISA"])

    def test_two_distinct(self) -> None:
        out = (
            "✓ TISA updated (vault/ships/myship/TISA.md)\n"
            "✓ SAIGA updated (vault/ships/craneship/SAIGA.md)"
        )
        self.assertEqual(updated_ships(out), ["TISA", "SAIGA"])

    def test_duplicate_collapsed_keeps_first_order(self) -> None:
        """Реальный кейс 15.07: связка перепривязывается (SIROKO отвязан, SAIGA
        привязан) и следом прокачивается движение — SAIGA попадает в вывод
        дважды. Карточка должна уйти в чат один раз."""
        out = (
            "✓ TISA updated (vault/ships/myship/TISA.md)\n"
            "✓ SIROKO updated (vault/ships/craneship/SIROKO.md)\n"
            "✓ SAIGA updated (vault/ships/craneship/SAIGA.md)\n"
            "✓ SAIGA updated (vault/ships/craneship/SAIGA.md)"
        )
        self.assertEqual(updated_ships(out), ["TISA", "SIROKO", "SAIGA"])

    def test_empty_output(self) -> None:
        self.assertEqual(updated_ships(""), [])


if __name__ == "__main__":
    unittest.main()
