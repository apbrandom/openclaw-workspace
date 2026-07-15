#!/usr/bin/env python3
"""Golden-тесты update_ship.py (R-05, R-06, R-01c).

Запуск:
  cd skills/ship-update && python3 -m unittest discover tests -v

Боевой vault не трогается: каждый тест собирает временный workspace
(fixtures/cards/*.md → tmp/vault/ships/{myship,craneship}/) и гоняет
update_ship.py через subprocess с SHIP_WORKSPACE=tmp.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).parent
SKILL = TESTS.parent
FIXTURES = TESTS / "fixtures" / "cards"
UPDATE_PY = SKILL / "update_ship.py"
PYTHON = sys.executable


class UpdateShipTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = Path(tempfile.mkdtemp(prefix="ship-test-"))
        myship = self.ws / "vault" / "ships" / "myship"
        craneship = self.ws / "vault" / "ships" / "craneship"
        myship.mkdir(parents=True)
        craneship.mkdir(parents=True)
        shutil.copy(FIXTURES / "TESTBARGE.md", myship / "TESTBARGE.md")
        shutil.copy(FIXTURES / "TESTTUG.md", craneship / "TESTTUG.md")
        self.barge = myship / "TESTBARGE.md"
        self.tug = craneship / "TESTTUG.md"

    def tearDown(self) -> None:
        shutil.rmtree(self.ws)

    def run_update(self, payload: dict) -> subprocess.CompletedProcess:
        env = dict(os.environ, SHIP_WORKSPACE=str(self.ws))
        return subprocess.run(
            [PYTHON, str(UPDATE_PY)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True, env=env,
        )

    # --- R-05: фиксированный вход → фиксированный diff ---

    def test_golden_update(self) -> None:
        payload = {
            "name": "TESTTUG",
            "position": "Мост",
            "status": "на ходу",
            "last_update_dt": "2026-01-02 16:45",
            "events": ["16:45 — прошёл мост"],
        }
        r = self.run_update(payload)
        self.assertEqual(r.returncode, 0, r.stderr)
        body = self.tug.read_text(encoding="utf-8")
        self.assertIn("- Позиция: Мост", body)
        self.assertIn("- Статус: на ходу", body)
        self.assertIn("- Обновлено: 2026-01-02 16:45", body)
        self.assertIn("last_updated: 2026-01-02", body)
        self.assertIn("- 2026-01-02 16:45 — прошёл мост", body)

    def test_idempotent(self) -> None:
        payload = {
            "name": "TESTTUG",
            "position": "Мост",
            "last_update_dt": "2026-01-02 16:45",
            "events": ["16:45 — прошёл мост"],
        }
        self.assertEqual(self.run_update(payload).returncode, 0)
        first = self.tug.read_bytes()
        self.assertEqual(self.run_update(payload).returncode, 0)
        self.assertEqual(first, self.tug.read_bytes(), "повторный прогон изменил файл")

    def test_events_sorted_chronologically(self) -> None:
        payload = {
            "name": "TESTTUG",
            "last_update_dt": "2026-01-02 18:00",
            "events": ["18:00 — событие позже", "12:00 — событие раньше"],
        }
        self.assertEqual(self.run_update(payload).returncode, 0)
        body = self.tug.read_text(encoding="utf-8")
        self.assertLess(
            body.index("12:00 — событие раньше"),
            body.index("18:00 — событие позже"),
        )

    def test_bare_time_expanded_with_date(self) -> None:
        payload = {
            "name": "TESTTUG",
            "last_update_dt": "2026-01-03 09:15",
            "events": ["09:15 — отошёл от причала"],
        }
        self.assertEqual(self.run_update(payload).returncode, 0)
        self.assertIn(
            "- 2026-01-03 09:15 — отошёл от причала",
            self.tug.read_text(encoding="utf-8"),
        )

    # --- Валидация ---

    def test_invalid_status_rejected(self) -> None:
        r = self.run_update({"name": "TESTTUG", "status": "летит"})
        self.assertEqual(r.returncode, 2)
        self.assertIn("invalid status", r.stderr)
        self.assertIn("- Статус: на якоре", self.tug.read_text(encoding="utf-8"))

    def test_unknown_ship_rejected(self) -> None:
        r = self.run_update({"name": "NOSUCHSHIP", "status": "на ходу"})
        self.assertEqual(r.returncode, 2)
        self.assertIn("not found", r.stderr)

    def test_invalid_datetime_rejected(self) -> None:
        r = self.run_update({"name": "TESTTUG", "last_update_dt": "вчера"})
        self.assertEqual(r.returncode, 2)

    def test_invalid_event_format_rejected(self) -> None:
        r = self.run_update({"name": "TESTTUG", "events": ["просто текст без времени"]})
        self.assertEqual(r.returncode, 2)

    # --- R-01c: факт судна X не попадает в карточку Y ---

    def test_no_cross_ship_leak(self) -> None:
        barge_before = self.barge.read_bytes()
        payload = {
            "name": "TESTTUG",
            "position": "Мост",
            "last_update_dt": "2026-01-02 16:45",
            "events": ["16:45 — прошёл мост"],
        }
        self.assertEqual(self.run_update(payload).returncode, 0)
        self.assertEqual(
            barge_before, self.barge.read_bytes(),
            "обновление буксира изменило карточку баржи (связка ещё не включена)",
        )

    # --- R-06: инвариант баржи ---

    def test_barge_keeps_tugboat_line(self) -> None:
        payload = {
            "name": "TESTBARGE",
            "position": "Причал 2",
            "status": "швартовка",
            "tugboat": "TESTTUG",
            "last_update_dt": "2026-01-02 11:00",
        }
        self.assertEqual(self.run_update(payload).returncode, 0)
        self.assertIn("- Буксир: TESTTUG", self.barge.read_text(encoding="utf-8"))

    @unittest.expectedFailure
    def test_barge_underway_without_tugboat_rejected(self) -> None:
        """R-06: баржа не ходит сама — «на ходу» без буксира должно отклоняться.
        Пока НЕ реализовано в update_ship.py (задача «связка буксир↔баржа»)."""
        r = self.run_update({"name": "TESTBARGE", "status": "на ходу"})
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
