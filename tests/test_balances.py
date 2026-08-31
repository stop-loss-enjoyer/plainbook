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


def trade(id, day, pnl=None, result=None, risk=1.0, account="bybit", closed=None):
    return Trade(id=id, account=account, pair="EURUSD", direction="long",
                 style="swing", entry_tf="H4", execution=["M15"], risk=risk,
                 opened=datetime(*day), result=result, pnl=pnl,
                 closed=datetime(*closed) if closed else None)


class Balances(unittest.TestCase):
    def setUp(self):
        self.accounts = {"bybit": Account(id="bybit", start_balance=10000)}

    def test_balance_grows_by_closed_pnl(self):
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25), pnl=1000, result="Win", closed=(2025, 6, 26)),
            trade("t2", (2025, 7, 1)),                     # open, not in the balance
        ], [])
        self.assertEqual(j.balance("bybit"), 11000)

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
            Adjustment(id="c1", account="bybit", kind="deposit", amount=5000,
                       day=datetime(2025, 6, 1)),
            Adjustment(id="c2", account="bybit", kind="withdrawal", amount=-2000,
                       day=datetime(2025, 7, 1)),
        ])
        self.assertEqual(j.balance("bybit"), 13000)

    def test_an_adjustment_counts_from_its_own_day(self):
        j = Journal(self.accounts, [trade("t1", (2025, 6, 1))], [
            Adjustment(id="c1", account="bybit", kind="deposit", amount=10000,
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
            trade("t2", (2025, 7, 1), account="bybit"),
        ], [])
        self.assertEqual(j.balance("prop-100k"), 99060)
        self.assertEqual(j.balance("bybit"), 10000)
        self.assertEqual(j.computed["t2"].balance_at_entry, 10000)

    def test_equity_curve(self):
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25), pnl=500, result="Win", closed=(2025, 6, 26)),
            trade("t2", (2025, 7, 1), pnl=-200, result="Lose", closed=(2025, 7, 3)),
        ], [])
        self.assertEqual([b for _, b in j.equity("bybit")], [10500, 10300])

    def test_reconciliation_brings_the_balance_to_the_real_one(self):
        """A gap is written down as an adjustment, never silently."""
        j = Journal(self.accounts, [
            trade("t1", (2025, 6, 25), pnl=900, result="Win", closed=(2025, 6, 26)),
        ], [
            Adjustment(id="reconciliation", account="bybit", kind="reconciliation",
                       amount=100, day=datetime(2026, 8, 29),
                       comment="reconciled while importing"),
        ])
        self.assertEqual(j.balance("bybit"), 11000)


if __name__ == "__main__":
    unittest.main()
