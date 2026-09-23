#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Balances are dynamic, R is measured against the balance at entry."""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook.balances import Journal
from plainbook.model import Trade, Account, Adjustment


def trade(id, day, pnl=None, result=None, risk=1.0, account="broker", closed=None):
    """`day` and `closed` are tuples; give them an hour and a minute and the
    journal knows the moment, which is what puts two trades of one day in
    order."""
    return Trade(id=id, account=account, pair="EURUSD", direction="long",
                 style="swing", entry_tf="H4", execution=["M15"], risk=risk,
                 opened=datetime(*day), opened_time=len(day) > 3,
                 result=result, pnl=pnl,
                 closed=datetime(*closed) if closed else None,
                 closed_time=bool(closed) and len(closed) > 3)


class Balances(unittest.TestCase):
    def setUp(self):
        self.accounts = {"broker": Account(id="broker", start_balance=10000)}

    def test_balance_grows_by_closed_pnl(self):
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25), pnl=1000, result="Win", closed=(2025, 6, 26)),
            trade("t2", (2025, 7, 1)),                     # open, not in the balance
        ], [])
        self.assertEqual(j.balance("broker"), 11000)

    def test_a_trade_closed_within_its_own_minute_is_not_in_its_own_balance(self):
        """Both hours known and equal: the close is not earlier than the entry,
        so the trade's own result must not be in the balance it was opened on."""
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25, 10, 0), pnl=500, result="Win",
                  closed=(2025, 6, 25, 10, 0)),
        ], [])
        self.assertEqual(j.computed["t1"].balance_at_entry, 10000)
        self.assertEqual(j.computed["t1"].r, 5.0)

    def test_balance_at_a_past_entry(self):
        """A trade written in a week late is sized on the balance of its own
        day: a win closed after that day is not in it, one closed before is."""
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 2, 9, 0), pnl=1000, result="Win",
                  closed=(2025, 6, 3, 12, 0)),
            trade("t2", (2025, 6, 10, 9, 0), pnl=500, result="Win",
                  closed=(2025, 6, 12, 12, 0)),
        ], [Adjustment(id="c1", account="broker", kind="deposit", amount=300,
                       day=datetime(2025, 6, 11))])
        self.assertEqual(j.balance("broker"), 11800)
        self.assertEqual(j.balance_at("broker", datetime(2025, 6, 11, 10, 0)), 11300)
        self.assertEqual(j.balance_at("broker", datetime(2025, 6, 3, 13, 0)), 11000)
        self.assertEqual(j.balance_at("broker", datetime(2025, 6, 3, 11, 0)), 10000)
        # a date with no hour does not see a close of that same day
        self.assertEqual(j.balance_at("broker", datetime(2025, 6, 3), False), 10000)
        # the trade being edited is not in its own balance
        self.assertEqual(j.balance_at("broker", datetime(2025, 6, 13), True, "t2"), 11300)
        self.assertEqual(j.balance_at("broker", datetime(2025, 6, 13), True, "t2"),
                         j.balance_at("broker", datetime(2025, 6, 13), True) - 500)

    def test_a_deposit_with_its_hour_misses_the_trade_of_that_morning(self):
        """Money moved at 18:00 is not in the balance of a trade opened at
        nine the same day; without its hour it counts from the day."""
        morning = trade("m", (2025, 6, 2, 9, 0))
        evening = trade("e", (2025, 6, 2, 19, 0))
        timed = Adjustment(id="d", account="broker", kind="deposit", amount=1000,
                           day=datetime(2025, 6, 2, 18, 0), day_time=True)
        j = Journal(self.accounts, [morning, evening], [timed])
        self.assertEqual(j.computed["m"].balance_at_entry, 10000)
        self.assertEqual(j.computed["e"].balance_at_entry, 11000)
        dated = Adjustment(id="d", account="broker", kind="deposit", amount=1000,
                           day=datetime(2025, 6, 2))
        j = Journal(self.accounts, [morning, evening], [dated])
        self.assertEqual(j.computed["m"].balance_at_entry, 11000)

    def test_a_fee_is_in_the_result_of_its_day(self):
        """The daily loss limit counts a fee charged that day the way the
        prop firm does; a deposit is not a result."""
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 2, 9, 0), pnl=-200, result="Lose",
                  closed=(2025, 6, 2, 12, 0)),
        ], [Adjustment(id="f", account="broker", kind="fee", amount=-30,
                       day=datetime(2025, 6, 2)),
            Adjustment(id="d", account="broker", kind="deposit", amount=500,
                       day=datetime(2025, 6, 2))])
        self.assertEqual(j.closed_on("broker", datetime(2025, 6, 2, 18, 0)), -230)
        self.assertEqual(j.closed_on("broker", datetime(2025, 6, 3)), 0)

    def test_risk_follows_the_current_balance(self):
        """Risk in dollars is measured against the computed balance, not the start."""
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25), pnl=1000, result="Win", closed=(2025, 6, 26)),
            trade("t2", (2025, 7, 1), pnl=110, result="Win", closed=(2025, 7, 2)),
        ], [])
        self.assertEqual(j.computed["t1"].risk_money, 100)      # 1% of 10 000
        self.assertEqual(j.computed["t2"].risk_money, 110)      # 1% of 11 000
        self.assertAlmostEqual(j.r("t2"), 1.0)
        self.assertAlmostEqual(j.r("t1"), 10.0)

    def test_adjustments_move_the_balance(self):
        j = Journal(self.accounts, [], [
            Adjustment(id="c1", account="broker", kind="deposit", amount=5000,
                       day=datetime(2025, 6, 1)),
            Adjustment(id="c2", account="broker", kind="withdrawal", amount=-2000,
                       day=datetime(2025, 7, 1)),
        ])
        self.assertEqual(j.balance("broker"), 13000)

    def test_an_adjustment_counts_from_its_own_day(self):
        j = Journal(self.accounts, [trade("t1", (2025, 6, 1))], [
            Adjustment(id="c1", account="broker", kind="deposit", amount=10000,
                       day=datetime(2025, 6, 1)),
        ])
        self.assertEqual(j.computed["t1"].balance_at_entry, 20000)

    def test_pnl_does_not_touch_an_entry_on_the_closing_day(self):
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25), pnl=1000, result="Win", closed=(2025, 6, 26)),
            trade("t2", (2025, 6, 26)),
            trade("t3", (2025, 6, 27)),
        ], [])
        self.assertEqual(j.computed["t2"].balance_at_entry, 10000)
        self.assertEqual(j.computed["t3"].balance_at_entry, 11000)

    def test_an_exit_with_an_hour_counts_from_that_hour(self):
        """A trade closed at noon is money on the account by three o'clock: an
        entry later that day is measured against the balance it left behind,
        and an entry earlier that day is not."""
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25), pnl=-1000, result="Lose",
                  closed=(2025, 6, 26, 12, 0)),
            trade("morning", (2025, 6, 26, 9, 0)),
            trade("evening", (2025, 6, 26, 15, 8)),
        ], [])
        self.assertEqual(j.computed["morning"].balance_at_entry, 10000)
        self.assertEqual(j.computed["evening"].balance_at_entry, 9000)

    def test_an_exit_without_an_hour_still_waits_for_the_next_day(self):
        """Nothing says which of the two came first, so the old rule holds."""
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25), pnl=-1000, result="Lose",
                  closed=(2025, 6, 26)),
            trade("evening", (2025, 6, 26, 15, 8)),
            trade("next", (2025, 6, 27, 9, 0)),
        ], [])
        self.assertEqual(j.computed["evening"].balance_at_entry, 10000)
        self.assertEqual(j.computed["next"].balance_at_entry, 9000)

    def test_be_gives_zero_r(self):
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25), pnl=0, result="BE", closed=(2025, 6, 26)),
        ], [])
        self.assertEqual(j.r("t1"), 0.0)

    def test_an_open_trade_has_no_r(self):
        j = Journal(self.accounts, [trade("t1", (2025, 6, 25))], [])
        self.assertIsNone(j.r("t1"))
        self.assertEqual([t.id for t in j.open_trades()], ["t1"])

    def test_accounts_do_not_mix(self):
        accounts = dict(self.accounts, **{"prop-100k": Account(id="prop-100k",
                                                               start_balance=100000)})
        j = Journal(accounts, [
            trade("t1", (2025, 6, 25), pnl=-940, result="Lose", closed=(2025, 6, 26),
                  account="prop-100k"),
            trade("t2", (2025, 7, 1), account="broker"),
        ], [])
        self.assertEqual(j.balance("prop-100k"), 99060)
        self.assertEqual(j.balance("broker"), 10000)
        self.assertEqual(j.computed["t2"].balance_at_entry, 10000)

    def test_equity_curve(self):
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25), pnl=500, result="Win", closed=(2025, 6, 26)),
            trade("t2", (2025, 7, 1), pnl=-200, result="Lose", closed=(2025, 7, 3)),
        ], [])
        self.assertEqual([b for _, b in j.equity("broker")], [10500, 10300])

    def test_reconciliation_brings_the_balance_to_the_real_one(self):
        """A gap is written down as an adjustment, never silently."""
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25), pnl=900, result="Win", closed=(2025, 6, 26)),
        ], [
            Adjustment(id="reconciliation", account="broker", kind="reconciliation",
                       amount=100, day=datetime(2026, 8, 29),
                       comment="reconciled while importing"),
        ])
        self.assertEqual(j.balance("broker"), 11000)

    def test_money_moved_is_kept_apart_from_what_was_earned(self):
        """A payout is not a loss: the result of the account is the balance
        with the money moved in and out taken back out of it."""
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25), pnl=1000, result="Win", closed=(2025, 6, 26)),
        ], [
            Adjustment(id="a1", account="broker", kind="withdrawal", amount=-3000,
                       day=datetime(2025, 7, 1), comment="payout"),
            Adjustment(id="a2", account="broker", kind="deposit", amount=500,
                       day=datetime(2025, 7, 2)),
        ])
        self.assertEqual(j.balance("broker"), 8500)      # 10000 + 1000 - 3000 + 500
        self.assertEqual(j.cashed_out("broker"), 3000)
        self.assertEqual(j.deposited("broker"), 500)
        self.assertEqual(j.result("broker"), 1000)       # the trade, and only it
        # the line on the tile adds up
        self.assertEqual(10000 + j.result("broker") + j.deposited("broker")
                         - j.cashed_out("broker"), j.balance("broker"))

    def test_a_withdrawal_lowers_the_balance_a_later_entry_risks_against(self):
        """Money taken off is gone from the risk of every trade opened after."""
        j = Journal(self.accounts, [
            trade("t1", (2025, 7, 5), risk=1.0),
        ], [
            Adjustment(id="a1", account="broker", kind="withdrawal", amount=-2000,
                       day=datetime(2025, 7, 1)),
        ])
        self.assertEqual(j.computed["t1"].balance_at_entry, 8000)
        self.assertEqual(j.computed["t1"].risk_money, 80)


if __name__ == "__main__":
    unittest.main()


class StreaksAndPeriods(unittest.TestCase):
    def setUp(self):
        self.accounts = {"broker": Account(id="broker", start_balance=10000)}

    def test_streaks_follow_the_order_of_closing(self):
        from plainbook import stats
        j = Journal(self.accounts, [
            trade("t1", (2026, 8, 1), pnl=100, result="Win", closed=(2026, 8, 2)),
            trade("t2", (2026, 8, 2), pnl=100, result="Win", closed=(2026, 8, 3)),
            trade("t3", (2026, 8, 3), pnl=0, result="BE", closed=(2026, 8, 4)),
            trade("t4", (2026, 8, 4), pnl=100, result="Win", closed=(2026, 8, 5)),
            trade("t5", (2026, 8, 5), pnl=-100, result="Lose", closed=(2026, 8, 6)),
            trade("t6", (2026, 8, 6), pnl=-100, result="Lose", closed=(2026, 8, 7)),
            trade("t7", (2026, 8, 7)),                       # open: not a run
        ], [])
        # the break-even in the middle neither breaks the run nor extends it
        self.assertEqual(stats.streaks(j, j.trades), (3, 2, ("Lose", 2)))
        self.assertEqual(stats.streaks(j, []), (0, 0, (None, 0)))

    def test_the_curve_of_a_period_starts_at_its_own_balance(self):
        from plainbook import stats
        j = Journal(self.accounts, [
            trade("t1", (2026, 7, 1), pnl=500, result="Win", closed=(2026, 7, 2)),
            trade("t2", (2026, 8, 1), pnl=-200, result="Lose", closed=(2026, 8, 2)),
            trade("t3", (2026, 8, 3), pnl=300, result="Win", closed=(2026, 8, 4)),
        ], [Adjustment(id="a", account="broker", kind="deposit", amount=1000,
                       day=datetime(2026, 7, 15))])
        since = datetime(2026, 8, 1)
        august = [t for t in j.trades if t.opened >= since]
        points = stats.equity(j, "broker", august, since)
        # July's trade and the deposit are in the first point, not on the line
        self.assertEqual(points[0], (since, 11500))
        self.assertEqual([b for _, b in points[1:]], [11300, 11600])
        # a filter by trade leaves the others out of the line, still from 11500
        points = stats.equity(j, "broker", [j.trades[2]], since)
        self.assertEqual([b for _, b in points], [11500, 11800])

    def test_equity_events_say_what_moved_each_point(self):
        from plainbook import stats
        j = Journal(self.accounts, [
            trade("t1", (2026, 7, 1), pnl=500, result="Win", closed=(2026, 7, 2)),
            trade("t2", (2026, 8, 1), pnl=-200, result="Lose", closed=(2026, 8, 2)),
        ], [Adjustment(id="a", account="broker", kind="deposit", amount=1000,
                       day=datetime(2026, 7, 15))])
        points = stats.equity_events(j, "broker")
        # the opening balance stands before the first event, on its day
        self.assertEqual(points[0], (datetime(2026, 7, 2), 10000, "start"))
        self.assertEqual([b for _, b, _ in points], [10000, 10500, 11500, 11300])
        self.assertEqual([w for _, _, w in points][1:],
                         [None, j.adjustments[0], None])
        # the balances are the ones of equity, whatever the tags say
        self.assertEqual(stats.equity(j, "broker"), j.equity("broker"))
        since = datetime(2026, 8, 1)
        self.assertEqual(stats.equity_events(j, "broker", None, since)[0],
                         (since, 11500, "since"))

    def test_the_currency_is_the_accounts_own_or_the_shared_one(self):
        accounts = {"a": Account(id="a", currency="USD"),
                    "b": Account(id="b", currency="EUR"),
                    "c": Account(id="c", currency="EUR", archived=True)}
        j = Journal(accounts, [], [])
        self.assertEqual(j.currency("b"), "EUR")
        self.assertEqual(j.currency("nobody"), "USD")
        self.assertEqual(j.currency(), "")             # USD and EUR: no shared one
        accounts["a"].currency = "EUR"
        self.assertEqual(Journal(accounts, [], []).currency(), "EUR")

    def test_a_stop_at_breakeven_frees_the_open_risk(self):
        """Three trades moved to the entry and two fresh ones put 2% at
        risk, not 5%: the limit counting the open risk sees only the two.
        The risk a trade was sized with still stands for its R."""
        old = [trade(f"o{i}", (2026, 9, 7, 10, i)) for i in range(3)]
        for t in old:
            t.breakeven = datetime(2026, 9, 8, 9, 0)
        fresh = [trade(f"f{i}", (2026, 9, 9, 10, i)) for i in range(2)]
        j = Journal(self.accounts, old + fresh, [])
        self.assertAlmostEqual(j.open_risk("broker"), 200.0)
        self.assertEqual([t.id for t in j.at_breakeven("broker")],
                         ["o0", "o1", "o2"])
        self.assertAlmostEqual(j.computed["o0"].risk_money, 100.0)
        old[0].breakeven = None
        j = Journal(self.accounts, old + fresh, [])
        self.assertAlmostEqual(j.open_risk("broker"), 300.0)

    def test_the_exit_is_not_before_the_entry(self):
        from plainbook.model import RecordError
        with self.assertRaises(RecordError):
            trade("t", (2026, 8, 5, 14, 0), pnl=1, result="Win",
                  closed=(2026, 8, 5, 13, 0)).check()
        # an exit with no hour on the day of the entry is that day, not earlier
        trade("t", (2026, 8, 5, 14, 0), pnl=1, result="Win",
              closed=(2026, 8, 5)).check()
        with self.assertRaises(RecordError):
            trade("t", (2026, 8, 5), pnl=1, result="Win", closed=(2026, 8, 4)).check()


class Copies(unittest.TestCase):
    """One position on two accounts is two trades for the money and one
    decision for the system."""

    def test_the_copies_of_a_position_fold_into_one_idea(self):
        from plainbook import stats
        accounts = {"broker": Account(id="broker", start_balance=10000),
                    "prop": Account(id="prop", start_balance=100000)}
        trades = [
            trade("a", (2025, 6, 2, 9, 0), pnl=-100, result="Lose",
                  closed=(2025, 6, 2, 12, 0)),
            trade("b", (2025, 6, 2, 9, 0), pnl=-1000, result="Lose",
                  closed=(2025, 6, 2, 12, 0), account="prop"),
            trade("c", (2025, 6, 3, 9, 0), pnl=200, result="Win",
                  closed=(2025, 6, 3, 12, 0)),
        ]
        j = Journal(accounts, trades, [])
        self.assertEqual(stats.copies(j.trades), 1)
        self.assertEqual(stats.summary(j, j.trades).trades, 3)
        self.assertAlmostEqual(stats.drawdown_r(j, j.trades), -2.0)
        view, ideas = stats.ideas(j, j.trades)
        s = stats.summary(view, ideas)
        self.assertEqual((s.trades, s.wins, s.losses), (2, 1, 1))
        self.assertAlmostEqual(s.sum_pnl, -900)               # every copy's money
        self.assertAlmostEqual(stats.drawdown_r(view, ideas), -1.0)
        self.assertEqual(stats.copies(ideas), 0)
        # the journal underneath is untouched
        self.assertEqual(len(j.trades), 3)
        self.assertAlmostEqual(j.r("b"), -1.0)


class PropRules(unittest.TestCase):
    """A prop account against the rules of its firm, worked out from the
    journal and never stored."""

    def prop(self, **rules):
        return Account(id="prop", kind="prop", start_balance=100000, **rules)

    def closed(self, tid, pnl, opened, closed):
        return Trade(id=tid, account="prop", pair="EURUSD", direction="long",
                     style="swing", risk=1.0, opened=opened, opened_time=True,
                     result="Win" if pnl > 0 else "Lose", pnl=pnl,
                     closed=closed, closed_time=True)

    def test_the_firm_counts_its_day_on_its_own_clock(self):
        """Midnight in Prague is 01:00 in Moscow in September: a loss closed at
        00:30 Moscow time belongs to the firm's day before."""
        a = self.prop(daily_loss_limit=5000, zone="Europe/Prague")
        j = Journal({"prop": a}, [
            self.closed("late", -700, datetime(2026, 9, 21, 20, 0), datetime(2026, 9, 22, 0, 30)),
            self.closed("today", -300, datetime(2026, 9, 22, 9, 0), datetime(2026, 9, 22, 11, 0)),
        ], [], clock="Europe/Moscow")
        start, end, found = j.firm_day(a, datetime(2026, 9, 22, 15, 0))
        self.assertTrue(found)
        self.assertEqual((start, end), (datetime(2026, 9, 22, 1, 0), datetime(2026, 9, 23, 1, 0)))
        p = j.prop("prop", datetime(2026, 9, 22, 15, 0))
        self.assertEqual(p.today, -300)
        self.assertEqual(p.daily_left, 4700)

    def test_a_day_that_begins_in_the_evening(self):
        """A firm whose day turns at 17:00 New York time counts a trade closed
        at 18:00 there in the next day."""
        a = self.prop(daily_loss_limit=1000, zone="America/New_York", day_start="17:00")
        j = Journal({"prop": a}, [], [], clock="America/New_York")
        start, end, _ = j.firm_day(a, datetime(2026, 9, 22, 18, 0))
        self.assertEqual(start, datetime(2026, 9, 22, 17, 0))
        start, end, _ = j.firm_day(a, datetime(2026, 9, 22, 16, 0))
        self.assertEqual(start, datetime(2026, 9, 21, 17, 0))

    def test_an_unknown_clock_falls_back_and_says_so(self):
        a = self.prop(daily_loss_limit=1000, zone="Mars/Base")
        j = Journal({"prop": a}, [], [])
        self.assertFalse(j.prop("prop", datetime(2026, 9, 22, 12, 0)).zone_found)

    def test_the_floor_static_trailing_and_trailing_to_start(self):
        trades = [
            self.closed("a", 6000, datetime(2026, 9, 1, 9), datetime(2026, 9, 1, 12)),
            self.closed("b", 8000, datetime(2026, 9, 2, 9), datetime(2026, 9, 2, 12)),
            self.closed("c", -3000, datetime(2026, 9, 3, 9), datetime(2026, 9, 3, 12)),
        ]
        now = datetime(2026, 9, 4, 12)
        floors = {}
        for mode in ("static", "trailing", "trailing to start"):
            a = self.prop(max_loss=10000, max_loss_mode=mode)
            p = Journal({"prop": a}, trades, []).prop("prop", now)
            floors[mode] = p.floor
            self.assertEqual(p.high, 114000)
        self.assertEqual(floors, {"static": 90000, "trailing": 104000,
                                  "trailing to start": 100000})

    def test_the_target_and_the_days_make_a_pass(self):
        a = self.prop(profit_target=10000, min_days=2, max_loss=10000)
        now = datetime(2026, 9, 4, 12)
        one = [self.closed("a", 11000, datetime(2026, 9, 1, 9), datetime(2026, 9, 1, 12))]
        p = Journal({"prop": a}, one, []).prop("prop", now)
        self.assertEqual((p.target_left, p.days_left, p.passed), (0, 1, False))
        two = one + [self.closed("b", 100, datetime(2026, 9, 2, 9), datetime(2026, 9, 2, 12))]
        self.assertTrue(Journal({"prop": a}, two, []).prop("prop", now).passed)

