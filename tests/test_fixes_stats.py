#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The figures of the Statistics tab and of the reports that read wrong: a
deposit inside a fall, a re-entry beside a copy, a target nobody could
judge, a ratio of two currencies, a zero day in red, a fee off the curve, a
name that broke the chart, and the shelf of reports read once."""
import html as _html
import importlib
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import html as H
from plainbook import reports, stats, store
from plainbook.balances import Journal
from plainbook.model import Account, Adjustment, Card, Trade


def trade(tid, pnl, day, account="broker", **over):
    fields = dict(id=tid, account=account, pair="EURUSD", direction="long",
                  style="swing", risk=1.0, opened=day,
                  result="Win" if pnl > 0 else "Lose" if pnl < 0 else "BE",
                  pnl=pnl, closed=day)
    fields.update(over)
    return Trade(**fields)


def series(svg):
    """The points the page script reads, decoded the way the browser does."""
    m = re.search(r'data-series=(?:"([^"]*)"|\'([^\']*)\')', svg)
    return json.loads(_html.unescape(m.group(1) or m.group(2)))


class FiguresCase(unittest.TestCase):
    def setUp(self):
        self.accounts = {"broker": Account(id="broker", start_balance=10000)}

    def test_a_deposit_inside_a_fall_does_not_hide_it(self):
        """The trading lost 4000 in a row; money put in between is not a gain."""
        trades = [trade("a", -2000, datetime(2026, 8, 2)),
                  trade("b", -2000, datetime(2026, 8, 4))]
        put = Adjustment(id="d", account="broker", kind="deposit", amount=2000,
                         day=datetime(2026, 8, 3))
        f = stats.money_fall(Journal(self.accounts, trades, [put]), "broker")
        self.assertEqual(f.worst, -4000)
        self.assertAlmostEqual(f.share, -40.0)
        # a deposit larger than the loss used to set a new high of its own
        put.amount = 5000
        f = stats.money_fall(Journal(self.accounts, trades, [put]), "broker")
        self.assertEqual(f.worst, -4000)

    def test_the_share_of_a_fall_is_of_the_real_balance(self):
        """Money put in before the high is part of the base of the share."""
        put = Adjustment(id="d", account="broker", kind="deposit", amount=40000,
                         day=datetime(2026, 8, 1))
        trades = [trade("a", -5000, datetime(2026, 8, 3))]
        f = stats.money_fall(Journal(self.accounts, trades, [put]), "broker")
        self.assertEqual(f.worst, -5000)
        self.assertAlmostEqual(f.share, -10.0)       # of 50 000, not of 10 000

    def test_a_reentry_beside_a_copy_stays_a_trade(self):
        """Two trades on one account and a copy of one on another are two
        ideas, and the switch counts the one copy it folds."""
        accounts = {"a": Account(id="a", start_balance=10000),
                    "b": Account(id="b", start_balance=10000)}
        day = datetime(2026, 9, 1)
        ts = [trade("t1", -100, day, "a"), trade("t2", 300, day, "a"),
              trade("t3", 300, day, "b")]
        j = Journal(accounts, ts, [])
        self.assertEqual(stats.copies(j.trades), 1)
        jj, folded = stats.ideas(j, j.trades)
        # the first of each account pair up, the re-entry stands alone
        self.assertEqual([t.id for t in folded], ["t1", "t2"])
        self.assertAlmostEqual(jj.r("t1"), (j.r("t1") + j.r("t3")) / 2)
        self.assertEqual(jj.r("t2"), j.r("t2"))
        # a scale-in copied to both accounts is two ideas, not four trades
        ts.append(trade("t4", -100, day, "b"))
        j = Journal(accounts, ts, [])
        self.assertEqual(stats.copies(j.trades), 2)
        self.assertEqual(len(stats.ideas(j, j.trades)[1]), 2)

    def test_a_target_with_nothing_to_judge_it_by_is_not_missed(self):
        prices = dict(entry_price=1.10, stop_price=1.09, target_price=1.13)
        ts = [trade("a", 300, datetime(2026, 8, 1), **prices),
              trade("b", 300, datetime(2026, 8, 2), **prices),
              trade("c", -100, datetime(2026, 8, 3), exit_price=1.09, **prices)]
        self.assertIsNone(stats.prices(ts[0]).reached)
        ps = stats.price_summary(ts)
        self.assertEqual((len(ps.planned), ps.judged, ps.reached), (3, 1, 0))

    def test_a_zero_weekday_is_amber(self):
        self.assertEqual(H._ev_fill(0.0), H.WARN)
        self.assertEqual(H._ev_fill(-0.001), H.WARN)
        self.assertIn(H._ev_fill(-0.5), H.LOSS_STEPS)
        self.assertIn(H._ev_fill(0.5), H.WIN_STEPS)

    def test_a_fee_is_in_the_end_figure_of_the_curve(self):
        """The curve says what the account result says: a fee is a loss, a
        deposit is not a gain."""
        trades = [trade("a", 500, datetime(2026, 9, 2))]
        moved = [Adjustment(id="f", account="broker", kind="fee", amount=-50,
                            day=datetime(2026, 9, 3)),
                 Adjustment(id="d", account="broker", kind="deposit", amount=1000,
                            day=datetime(2026, 9, 4))]
        j = Journal(self.accounts, trades, moved)
        svg = H.equity_svg([("broker", "#fff", stats.equity_events(j, "broker"))],
                           base=10000)
        last = series(svg)[0]["points"][-1]
        self.assertEqual(last[3], 11450)
        self.assertEqual(last[5], j.result("broker"))
        self.assertEqual(last[5], 450)

    def test_a_name_with_quotes_does_not_break_the_chart(self):
        name = "Alex's account\"'><b id=pwn>"
        pts = [(datetime(2026, 9, 1), 5000.0, "start"), (datetime(2026, 9, 2), 5100.0, None)]
        svg = H.equity_svg([(name, "#fff", pts)])
        self.assertNotIn("<b id=pwn>", svg)
        self.assertEqual(series(svg)[0]["name"], name)


class ServerFiguresCase(unittest.TestCase):
    """The parts of the pages that read the figures above, on a journal of
    their own."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        os.environ["PLAINBOOK_ROOT"] = cls.root
        import plainbook.server
        cls.S = importlib.reload(plainbook.server)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("PLAINBOOK_ROOT", None)

    def test_no_profit_factor_across_currencies(self):
        accounts = {"eur": Account(id="eur", start_balance=10000, currency="EUR"),
                    "jpy": Account(id="jpy", start_balance=1500000, currency="JPY")}
        won = [trade(f"w{i}", 100, datetime(2026, 8, i + 1), "eur") for i in range(3)]
        ts = won + [trade(f"l{i}", -15000, datetime(2026, 8, i + 5), "jpy") for i in range(3)]
        j = Journal(accounts, ts, [])
        tile = self.S.payoff_tile(j, j.trades, stats.summary(j, j.trades), None)
        self.assertIn("payoff", tile)
        self.assertNotIn("profit factor", tile)
        ts = won + [trade(f"l{i}", -50, datetime(2026, 8, i + 5), "eur") for i in range(3)]
        j = Journal(accounts, ts, [])
        tile = self.S.payoff_tile(j, j.trades, stats.summary(j, j.trades), None)
        self.assertIn("profit factor 2.00 in money", tile)

    def test_no_profit_factor_across_currencies_in_ideas(self):
        # the same position on a euro and a yen account folds into one idea
        # under the euro account, its money summed across both
        accounts = {"eur": Account(id="eur", start_balance=10000, currency="EUR"),
                    "jpy": Account(id="jpy", start_balance=1500000, currency="JPY")}
        ts = []
        for i in range(6):
            day, sign = datetime(2026, 8, i + 3), 1 if i % 2 else -1
            ts += [trade(f"e{i}", 100 * sign, day, "eur"),
                   trade(f"y{i}", 15000 * sign, day, "jpy")]
        j = Journal(accounts, ts, [])
        ij, its = stats.ideas(j, j.trades)
        tile = self.S.payoff_tile(ij, its, stats.summary(ij, its), None, j.trades)
        self.assertNotIn("profit factor", tile)

    def test_the_shelf_reads_the_cards_once_and_says_the_same(self):
        store.save_account(self.root, Account(id="broker", start_balance=10000))
        for i, (month, pnl) in enumerate(((6, 200), (7, -100), (7, 300), (8, 150))):
            day = datetime(2025, month, 3 + i)
            store.save_trade(self.root, trade(f"2025-0{month}-0{3 + i}-01-eurusd", pnl, day))
            store.save_card(self.root, Card(day=day, grade="B", pnl=pnl))
        store.save_adjustment(self.root, Adjustment(
            id="2025-07-10-deposit", account="broker", kind="deposit", amount=500,
            day=datetime(2025, 7, 10)))
        j = self.S.journal()
        shelf = reports.Shelf(self.root, j)
        for p in ("2025-06", "2025-07", "2025-08", "2025-Q2", "2025-Q3"):
            alone, shared = reports.compose(self.root, j, p), reports.compose(self.root, j, p, shelf=shelf)
            self.assertEqual([t.id for t in alone.trades], [t.id for t in shared.trades])
            self.assertEqual([t.id for t in alone.was_trades], [t.id for t in shared.was_trades])
            self.assertEqual(alone.balances, shared.balances)
            self.assertEqual([k.day for k in alone.cards], [k.day for k in shared.cards])
        with mock.patch.object(store, "all_cards", wraps=store.all_cards) as cards:
            self.assertIn("July 2025", self.S.reports_page())
        self.assertEqual(cards.call_count, 1)


class IdeasFiguresCase(unittest.TestCase):
    """Under Ideas the copies of a position fold into one: the money and the
    rest of the journal must still be read from the right set."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        os.environ["PLAINBOOK_ROOT"] = cls.root
        import plainbook.server
        cls.S = importlib.reload(plainbook.server)
        store.save_account(cls.root, Account(id="a", start_balance=10000))
        store.save_account(cls.root, Account(id="b", start_balance=100000))
        day = datetime(2026, 8, 3)
        store.save_trade(cls.root, trade("2026-08-03-01-eurusd-a", 100, day, "a"))
        store.save_trade(cls.root, trade("2026-08-03-01-eurusd-b", 3000, day, "b"))
        other = datetime(2026, 8, 4)
        store.save_trade(cls.root, trade("2026-08-04-01-gbpusd-a", -50, other, "a",
                                         pair="GBPUSD"))
        third = datetime(2026, 8, 5)
        for acc in ("a", "b"):
            store.save_trade(cls.root, trade(f"2026-08-05-01-usdjpy-{acc}", 10, third,
                                             acc, pair="USDJPY", style="day"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("PLAINBOOK_ROOT", None)

    def page(self, **q):
        return self.S.stats_page({k: [v] for k, v in q.items()})

    def test_the_account_slice_keeps_each_accounts_money(self):
        j = self.S.journal()
        key = dict(reports.SLICES)["By account"]
        want = {v: s.sum_pnl for v, s in stats.by_values(j, j.trades, key)}
        self.assertEqual(want, {"a": 60, "b": 3010})
        text = self.page(count="ideas")
        # the 3010 of the second account is not on the first one's row
        self.assertIn("+3 010", text)

    def test_the_title_has_no_money_across_two_accounts(self):
        text = self.page(count="ideas", pair="EURUSD")
        self.assertIn("1 closed position,", text)
        # the line of the head, not the tiles below it, which show the money
        line = text.split("1 closed position,", 1)[1].split("</p>", 1)[0]
        self.assertNotIn("3 100", line)

    def test_the_filter_form_keeps_the_count(self):
        text = self.page(count="ideas")
        self.assertRegex(text, r'<input type="hidden" name="count" value="ideas"')

    def test_the_rest_is_read_in_ideas_too(self):
        # the rest is the EURUSD idea, mean R of its copies
        j = self.S.journal()
        mean = (j.r("2026-08-03-01-eurusd-a") + j.r("2026-08-03-01-eurusd-b")) / 2
        ij, its = stats.ideas(j, [t for t in j.trades if t.pair == "EURUSD"])
        self.assertAlmostEqual(stats.summary(ij, its).average_r, mean)
        gbp = j.r("2026-08-04-01-gbpusd-a")
        text = self.page(count="ideas", style="day")
        self.assertIn("the other 2 closed trades", text)
        self.assertIn(f"{(mean + gbp) / 2:+.2f}", text)


class RoundingCase(unittest.TestCase):
    def test_money_has_no_negative_zero(self):
        self.assertEqual(H.money(-0.4), "0")
        self.assertEqual(H.money(-0.4, signed=True), "+0")

    def test_the_balance_change_is_the_difference_of_the_printed_figures(self):
        accounts = {"broker": Account(id="broker", start_balance=1000.40)}
        day = datetime(2026, 8, 3)
        ts = [trade("a", 1.20, day)]
        j = Journal(accounts, ts, [])
        with tempfile.TemporaryDirectory() as root:
            r = reports.compose(root, j, "2026-08")
            text = reports.to_markdown(r, j, "")
        self.assertIn("| broker | 1 000 | 1 002 | +2 |", text)

    def test_a_slice_of_break_evens_has_no_winrate(self):
        s = stats.summary(Journal({"broker": Account(id="broker", start_balance=1000)},
                                  [trade("a", 0, datetime(2026, 8, 3))], []),
                          [trade("a", 0, datetime(2026, 8, 3))])
        self.assertFalse(s.decided)
        self.assertTrue(reports._figures(s).startswith("1 | - |"))


if __name__ == "__main__":
    unittest.main()
