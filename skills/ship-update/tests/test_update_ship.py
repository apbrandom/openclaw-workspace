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

    def test_future_last_update_dt_rejected(self) -> None:
        from datetime import datetime, timedelta
        future = (datetime.now() + timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
        r = self.run_update({"name": "TESTTUG", "last_update_dt": future})
        self.assertEqual(r.returncode, 2)
        self.assertIn("future", r.stderr)

    def test_future_event_rejected(self) -> None:
        from datetime import datetime, timedelta
        future = (datetime.now() + timedelta(hours=5)).strftime("%H:%M")
        r = self.run_update({"name": "TESTTUG", "events": [f"{future} — событие из будущего"]})
        self.assertEqual(r.returncode, 2)
        self.assertIn("future", r.stderr)

    def test_near_future_within_tolerance_accepted(self) -> None:
        """Небольшой рассинхрон часов (< 3ч) — не повод отклонять."""
        from datetime import datetime, timedelta
        soon = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        r = self.run_update({"name": "TESTTUG", "last_update_dt": soon})
        self.assertEqual(r.returncode, 0, r.stderr)

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

    def test_barge_underway_without_tugboat_rejected(self) -> None:
        """R-06: баржа не ходит сама — «на ходу» без буксира отклоняется."""
        r = self.run_update({"name": "TESTBARGE", "status": "на ходу", "tugboat": "—"})
        self.assertEqual(r.returncode, 2)
        self.assertIn("R-06", r.stderr)

    # --- Связка буксир↔баржа ---

    def test_link_mirrors_to_tug(self) -> None:
        """tugboat на барже → зеркальное «Ведёт:» на буксире."""
        r = self.run_update({"name": "TESTBARGE", "tugboat": "TESTTUG",
                             "status": "буксировка", "last_update_dt": "2026-01-02 12:00"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("- Ведёт: TESTBARGE", self.tug.read_text(encoding="utf-8"))

    def test_tug_movement_propagates_to_barge(self) -> None:
        """Главное правило: «Корсак прошёл мост» обновляет и баржу."""
        self.run_update({"name": "TESTBARGE", "tugboat": "TESTTUG"})
        r = self.run_update({
            "name": "TESTTUG",
            "position": "Мост",
            "status": "на ходу",
            "last_update_dt": "2026-01-02 16:45",
            "events": ["16:45 — прошёл мост"],
        })
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("TESTBARGE", r.stdout, "баржа не в списке обновлённых")
        barge = self.barge.read_text(encoding="utf-8")
        self.assertIn("- Позиция: Мост", barge)
        self.assertIn("- Статус: буксировка", barge, "у баржи должен быть статус «буксировка», не «на ходу»")
        self.assertIn("- 2026-01-02 16:45 — прошёл мост", barge)
        self.assertIn("- Обновлено: 2026-01-02 16:45", barge)

    def test_barge_movement_propagates_to_tug(self) -> None:
        r = self.run_update({
            "name": "TESTBARGE",
            "tugboat": "TESTTUG",
            "position": "Пролив",
            "status": "буксировка",
            "last_update_dt": "2026-01-02 14:00",
            "events": ["14:00 — вошли в пролив"],
        })
        self.assertEqual(r.returncode, 0, r.stderr)
        tug = self.tug.read_text(encoding="utf-8")
        self.assertIn("- Позиция: Пролив", tug)
        self.assertIn("- Статус: на ходу", tug, "у буксира «на ходу», не «буксировка»")
        self.assertIn("- 2026-01-02 14:00 — вошли в пролив", tug)

    def test_unlink_clears_both_sides(self) -> None:
        self.run_update({"name": "TESTBARGE", "tugboat": "TESTTUG"})
        r = self.run_update({"name": "TESTBARGE", "tugboat": "—",
                             "status": "ожидание", "last_update_dt": "2026-01-03 08:00"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("- Буксир: —", self.barge.read_text(encoding="utf-8"))
        self.assertIn("- Ведёт: —", self.tug.read_text(encoding="utf-8"))

    def test_unlinked_tug_does_not_propagate(self) -> None:
        self.run_update({"name": "TESTBARGE", "tugboat": "TESTTUG"})
        self.run_update({"name": "TESTBARGE", "tugboat": "—", "status": "ожидание"})
        barge_before = self.barge.read_bytes()
        r = self.run_update({"name": "TESTTUG", "position": "Рейд-2",
                             "last_update_dt": "2026-01-03 10:00"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(barge_before, self.barge.read_bytes(),
                         "разорванная связка не должна прокачивать факты")

    def test_rebind_breaks_old_link(self) -> None:
        """Буксир ведёт одну баржу: перепривязка рвёт старую связку."""
        barge2 = self.ws / "vault" / "ships" / "myship" / "TESTBARGE2.md"
        barge2.write_text(
            self.barge.read_text(encoding="utf-8").replace("TESTBARGE", "TESTBARGE2"),
            encoding="utf-8")
        self.run_update({"name": "TESTBARGE", "tugboat": "TESTTUG"})
        r = self.run_update({"name": "TESTBARGE2", "tugboat": "TESTTUG"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("- Ведёт: TESTBARGE2", self.tug.read_text(encoding="utf-8"))
        self.assertIn("- Буксир: —", self.barge.read_text(encoding="utf-8"),
                      "старая баржа должна отвязаться")


if __name__ == "__main__":
    unittest.main()
