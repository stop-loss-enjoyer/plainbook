#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The shelf of reports: composed with what it read once, and alone."""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import demo_journal
from plainbook import reports, stats, store
from plainbook.balances import Journal
from plainbook.model import Card, Week


class ShelfCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        demo_journal.build(cls.root, months=8)
        cls.j = Journal.load(cls.root)
        # cards and weeks spread over the months the trades closed in
        closed = sorted({t.closed for t in cls.j.trades if t.closed and not t.is_open})
        for moment in closed[::9]:
            day = moment.replace(hour=0, minute=0, second=0, microsecond=0)
            store.save_card(cls.root, Card(day=day, grade="B"))
            store.save_week(cls.root, Week(week=stats.week(moment), grade="A"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_a_report_composed_on_the_shelf_equals_one_composed_alone(self):
        shelf = reports.Shelf(self.root, self.j)
        periods = reports.periods(self.j, "month") + reports.periods(self.j, "quarter")
        self.assertTrue(periods)
        seen_cards = seen_weeks = 0
        for period in periods:
            alone = reports.compose(self.root, self.j, period)
            on_shelf = reports.compose(self.root, self.j, period, shelf=shelf)
            self.assertEqual([k.id for k in on_shelf.cards], [k.id for k in alone.cards], period)
            self.assertEqual([k.id for k in on_shelf.weeks], [k.id for k in alone.weeks], period)
            self.assertEqual(on_shelf.days_traded, alone.days_traded, period)
            seen_cards += len(alone.cards)
            seen_weeks += len(alone.weeks)
        # the test means something only if the periods held cards and weeks
        self.assertTrue(seen_cards and seen_weeks)


class ConclusionsCase(unittest.TestCase):
    def test_a_stub_and_a_missing_file_say_nothing(self):
        self.assertEqual(reports.conclusions_of(None), "")
        self.assertEqual(reports.conclusions_of("# Report\n\n## Conclusions\n\n_(empty)_\n"), "")
        self.assertEqual(reports.conclusions_of("# Report\n\nno such heading"), "")

    def test_a_written_body_gives_its_text(self):
        body = "# Report\n\n## Conclusions\n\n  Kept the rules.\nSecond line.\n"
        self.assertEqual(reports.conclusions_of(body), "Kept the rules.\nSecond line.")

    def test_previous_conclusions_reads_the_file_through_it(self):
        root = tempfile.mkdtemp()
        try:
            self.assertEqual(reports.previous_conclusions(root, "2026-08"), "")
            os.makedirs(os.path.dirname(reports.path(root, "2026-08")))
            with open(reports.path(root, "2026-08"), "w", encoding="utf-8") as f:
                f.write("# August\n\n## Conclusions\n\nHeld.\n")
            self.assertEqual(reports.previous_conclusions(root, "2026-08"), "Held.")
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
