#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The figures of a playbook: by playbook, by setup, what a rule costs."""
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import stats, store
from plainbook.balances import Journal
from plainbook.model import Account, Rule, Trade


def trade(n, result, pnl, **kw):
    t = Trade(id=f"2026-08-{n:02d}-01-eurusd", account="broker", pair="EURUSD",
              direction="long", style="swing", risk=1.0,
              opened=datetime(2026, 8, n), result=result, pnl=pnl,
              closed=datetime(2026, 8, n + 1))
    for k, v in kw.items():
        setattr(t, k, v)
    return t


class PlaybookStats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        store.save_account(root, Account(id="broker", start_balance=10000))
        self.trades = [
            trade(1, "Win", 200, playbook="pull", playbook_version="1.0", setup="A", deviations=[],
                  exit_deviations=[]),
            trade(3, "Lose", -100, playbook="pull", playbook_version="1.0", setup="A", deviations=[2],
                  exit_deviations=[8]),
            trade(5, "Lose", -100, playbook="pull", playbook_version="1.0", setup="B", deviations=[2, 4]),
            trade(7, "Win", 300, playbook="pull", playbook_version="1.0", setup="B"),   # not ticked
            trade(9, "Win", 100, playbook="pull", playbook_version="0.9", setup="A", deviations=[4]),
            trade(11, "Lose", -100),
            Trade(id="2026-08-13-01-eurusd", account="broker", pair="EURUSD",
                  direction="long", style="swing", opened=datetime(2026, 8, 13),
                  playbook="pull", playbook_version="1.0", setup="A", deviations=[4]),
        ]
        for t in self.trades:
            store.save_trade(root, t)
        self.j = Journal.load(root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_compliance_tells_the_three_kinds_apart(self):
        c = stats.compliance([t for t in self.j.trades if t.playbook == "pull"])
        self.assertEqual((c.clean, c.deviated, c.unticked), (1, 4, 1))
        self.assertEqual(c.ticked, 5)
        self.assertEqual(c.clean_share, 20.0)
        self.assertEqual((c.held, c.held_broken, c.held_unticked), (1, 1, 3))
        self.assertEqual(c.held_share, 50.0)
        self.assertIsNone(stats.compliance([self.trades[3]]).clean_share)

    def test_by_playbook_puts_the_playbook_first_and_none_last(self):
        rows = stats.by_playbook(self.j, self.j.trades)
        self.assertEqual([r[0] for r in rows], ["pull", stats.NO_PLAYBOOK])
        pid, s, c = rows[0]
        self.assertEqual((s.trades, s.wins, s.losses), (5, 3, 2))     # the open one is out
        self.assertEqual((c.clean, c.deviated, c.unticked), (1, 3, 1))
        self.assertEqual(rows[1][1].trades, 1)

    def test_by_setup(self):
        pull = [t for t in self.j.trades if t.playbook == "pull"]
        rows = stats.by_setup(self.j, pull)
        self.assertEqual([(name, s.trades) for name, s, _ in rows], [("A", 3), ("B", 2)])

    def test_rule_costs_count_only_ticked_trades_of_the_version(self):
        pull = [t for t in self.j.trades if t.playbook == "pull" and t.playbook_version == "1.0"]
        rules = [Rule(1, "one"), Rule(2, "two"), Rule(4, "four"), Rule(8, "held")]
        rows, clean = stats.rule_costs(self.j, pull, rules)
        by_number = {r.number: (n, s) for r, n, s in rows}
        self.assertEqual(by_number[1][0], 0)
        self.assertEqual(by_number[8][0], 1)                 # broken at the close
        self.assertEqual(by_number[2][0], 2)                 # trades 3 and 5
        self.assertAlmostEqual(by_number[2][1].sum_r, -2.0, places=1)
        self.assertEqual(by_number[4][0], 2)                 # trade 5 and the open one
        self.assertEqual(by_number[4][1].trades, 1)          # the open one has no R
        self.assertEqual(clean.trades, 1)
        self.assertAlmostEqual(clean.sum_r, 2.0, places=1)


class Frame(unittest.TestCase):
    def test_the_frame_counts_the_week_the_month_the_open_and_the_fuse(self):
        from plainbook.model import Playbook
        with tempfile.TemporaryDirectory() as root:
            store.save_account(root, Account(id="broker", start_balance=10000))
            now = datetime(2026, 8, 20, 12)                     # a Thursday
            for t in (trade(17, "Lose", -100, playbook="p"),   # Monday, closed Tuesday
                      trade(18, "Lose", -100, playbook="p"),
                      trade(11, "Win", 300, playbook="p"),     # the week before
                      Trade(id="2026-08-19-01-eurusd", account="broker", pair="EURUSD",
                            direction="long", style="swing", opened=datetime(2026, 8, 19),
                            playbook="p"),
                      trade(12, "Win", 100)):                  # another playbook
                store.save_trade(root, t)
            j = Journal.load(root)
            p = Playbook(id="p", name="P", block=40, limits=[("max per week", "3"), ("max per month", "10"),
                                                  ("weekly loss limit", "3"), ("open at once", "1"),
                                                  ("other thing", "5")])
            rows = {what: (value, limit, reached) for what, value, limit, reached
                    in stats.frame(j, p, now)}
            self.assertEqual(rows["trades this week"], (3, 3.0, True))
            self.assertEqual(rows["trades this month"], (4, 10.0, False))
            self.assertEqual(rows["R this week"][1:], (-3.0, False))
            # two stops on a balance that shrank between them: a little under -2
            self.assertLess(abs(rows["R this week"][0] + 2.0), 0.15)
            self.assertEqual(rows["open now"], (1, 1.0, True))
            self.assertEqual(stats.frame(j, Playbook(id="p", name="P"), now), [])

    def test_a_review_is_due_after_every_full_block(self):
        from plainbook.model import Playbook
        p = Playbook(id="p", block=40)
        self.assertFalse(stats.review_due(p, 39))
        self.assertTrue(stats.review_due(p, 40))
        p.review = "**01.09.2026**: block one reviewed.\n![](shots/review-01.png)\n**bold** inside"
        self.assertEqual(stats.reviews_written(p), 1)
        self.assertFalse(stats.review_due(p, 41))
        self.assertTrue(stats.review_due(p, 80))
        self.assertFalse(stats.review_due(Playbook(id="q"), 500))


if __name__ == "__main__":
    unittest.main()
