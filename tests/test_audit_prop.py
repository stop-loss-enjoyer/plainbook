#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The prop account and the risk after the audit of 09.11.2026: money taken
to the cent before a limit is compared, a closed trade with no exit date
named, the base of an account funded by a deposit, the daily loss limit
under its two switches and as a percent, and a risk typed in money that
comes back to the cent."""
import importlib
import os
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import store
from plainbook.balances import Journal
from plainbook.model import Account, Adjustment, IdeaBlock, RecordError, Trade

NOW = datetime(2026, 8, 20, 15, 0)


def trade(i, account="prop", pnl=None, risk=1.0, opened=None, closed=None,
          result=None):
    opened = opened or NOW - timedelta(hours=i)
    if pnl is not None and closed is None:
        closed = NOW - timedelta(minutes=i)
    return Trade(id=f"2026-08-20-{i:02d}-eurusd", account=account, pair="EURUSD",
                 direction="long", style="swing", entry_tf="H4", risk=risk,
                 opened=opened, opened_time=True,
                 result=result or (None if pnl is None else "Lose"), pnl=pnl,
                 closed=closed, closed_time=closed is not None)


def deposit(i, amount, day, account="prop"):
    return Adjustment(id=f"2026-01-01-{i:02d}-deposit", account=account,
                      kind="deposit", amount=amount, day=day)


class CentsCase(unittest.TestCase):
    """42: three losses that add up to the limit exactly in cents."""

    def test_a_day_that_lost_exactly_the_limit_has_reached_it(self):
        self.assertLess(100.1 + 200.2 + 300.3, 600.6)     # what the floats say
        a = Account(id="prop", kind="prop", start_balance=1000,
                    daily_loss_limit=600.6, max_loss=600.6)
        trades = [trade(1, pnl=-100.1), trade(2, pnl=-200.2), trade(3, pnl=-300.3)]
        p = Journal({"prop": a}, trades, []).prop("prop", NOW)
        self.assertEqual(p.today, -600.6)
        self.assertTrue(p.daily.reached)
        self.assertFalse(p.daily.at_stops)
        self.assertEqual(p.daily_left, 0)
        # the floor of 399.40 is reached by a balance of 399.40, not missed
        self.assertEqual((p.balance, p.floor, p.floor_left), (399.4, 399.4, 0))
        self.assertTrue(p.breached)


class NoExitCase(unittest.TestCase):
    """43: a closed trade with no exit date is named, the figures as they were."""

    def test_it_is_named_with_its_path_and_still_in_the_balance(self):
        a = Account(id="prop", start_balance=1000)
        t = trade(1, pnl=-50)
        t.closed, t.closed_time = None, False
        j = Journal({"prop": a}, [t], [])
        self.assertIn((f"journal/trades/{t.id}/trade.md",
                       "closed with no exit date: add `exit:`"), j.problems)
        self.assertEqual(j.balance("prop"), 950)
        self.assertEqual(j.equity("prop"), [])

    def test_an_open_trade_and_a_dated_close_are_not_named(self):
        j = Journal({"prop": Account(id="prop", start_balance=1000)},
                    [trade(1), trade(2, pnl=10, result="Win")], [])
        self.assertFalse([p for p in j.problems if "no exit date" in p[1]])


class BaseCase(unittest.TestCase):
    """Decision 2: an account opened at 0 and funded by a deposit."""

    def journal(self, mode="static", adjustments=None, trades=None, **rules):
        a = Account(id="prop", kind="prop", start_balance=0, max_loss=10000,
                    max_loss_mode=mode, **rules)
        first = datetime(2026, 8, 3, 10, 0)
        adjustments = adjustments if adjustments is not None else [
            deposit(1, 100000, datetime(2026, 8, 1)),
            deposit(2, 50000, datetime(2026, 8, 10))]      # after the first trade
        trades = trades if trades is not None else [
            trade(1, pnl=-1000, opened=first, closed=first + timedelta(hours=2))]
        return Journal({"prop": a}, trades, adjustments)

    def test_the_static_floor_stands_under_the_deposit_before_the_first_trade(self):
        j = self.journal()
        self.assertEqual(j.base("prop"), 100000)
        p = j.prop("prop", NOW)
        self.assertEqual(p.floor, 90000)
        self.assertEqual(p.balance, 149000)

    def test_trailing_to_start_stops_at_the_same_base(self):
        p = self.journal("trailing to start").prop("prop", NOW)
        self.assertEqual(p.high, 149000)
        self.assertEqual(p.floor, 100000)       # not 139 000, not 0

    def test_without_a_trade_every_deposit_is_the_base(self):
        j = self.journal(trades=[])
        self.assertEqual(j.base("prop"), 150000)

    def test_a_percent_daily_limit_is_of_the_base(self):
        j = self.journal(daily_loss_percent=5)
        self.assertEqual(j.daily_limit("prop"), 5000)
        self.assertEqual(j.prop("prop", NOW).daily.limit, 5000)
        # nothing to take a percent of yet: no limit rather than one of 0
        self.assertIsNone(self.journal(adjustments=[], daily_loss_percent=5)
                          .daily_limit("prop"))


class DailyCase(unittest.TestCase):
    """Decision 4: one function says what the day used, under two switches."""

    def state(self, *trades, closed=True, open_=True, **rules):
        a = Account(id="prop", kind="prop", start_balance=10000,
                    daily_counts_closed=closed, daily_counts_open=open_,
                    **({"daily_loss_limit": 500} | rules))
        return Journal({"prop": a}, list(trades), []).prop("prop", NOW)

    def test_the_four_combinations(self):
        loss, risk = trade(1, pnl=-300), trade(2, risk=1.0)    # 300 lost, 100 at risk
        used = {(c, o): self.state(loss, risk, closed=c, open_=o).daily.used
                for c in (True, False) for o in (True, False)}
        self.assertEqual(used, {(True, True): 400, (True, False): 300,
                                (False, True): 100, (False, False): 0})

    def test_a_profit_closed_today_makes_room_only_when_closed_counts(self):
        win, risk = trade(1, pnl=300, result="Win"), trade(2, risk=2.0)
        self.assertEqual(self.state(win, risk).daily.used, 0)
        self.assertEqual(self.state(win, risk, closed=False).daily.used, 200)

    def test_reached_at_the_stops_is_not_broken_and_not_passed(self):
        p = self.state(trade(1, risk=5.0), profit_target=1)      # 500 at risk
        self.assertEqual((p.daily.reached, p.daily.at_stops), (True, True))
        self.assertFalse(p.breached)
        self.assertFalse(p.passed)

    def test_a_closed_loss_at_the_limit_is_broken(self):
        p = self.state(trade(1, pnl=-500))
        self.assertEqual((p.daily.reached, p.daily.at_stops, p.breached),
                         (True, False, True))

    def test_open_risk_off_never_reaches_by_the_stops(self):
        p = self.state(trade(1, risk=9.0), open_=False)
        self.assertEqual((p.daily.used, p.daily.reached), (0, False))


class WordsCase(unittest.TestCase):
    """The line on Accounts says what `daily` says, and nothing against it."""

    @classmethod
    def setUpClass(cls):
        import plainbook.server
        cls.S = plainbook.server

    def line(self, *trades, **rules):
        a = Account(id="prop", kind="prop", start_balance=10000,
                    **({"daily_loss_limit": 500} | rules))
        return self.S.daily_limit_state(Journal({"prop": a}, list(trades), []), a, NOW)

    def test_reached_at_the_stops_is_said_and_every_rule_met_is_not(self):
        win = trade(3, pnl=1000, result="Win")
        cls, html = self.line(win, profit_target=500)
        self.assertIn("every rule met", html)
        # 1 500 at risk less the 1 000 closed today: the limit, at the stops
        cls, html = self.line(win, trade(1, risk=15.0), profit_target=500)
        self.assertEqual(cls, " over")
        self.assertIn("daily loss limit reached at the stops: ", html)
        self.assertNotIn("every rule met", html)

    def test_a_closed_loss_at_the_limit_says_reached(self):
        _, html = self.line(trade(1, pnl=-500))
        self.assertIn("daily loss limit reached: today -500 $ · limit 500 $", html)

    def test_each_switch_names_only_what_it_counts(self):
        loss, risk = trade(1, pnl=-100), trade(2, risk=1.0)
        _, html = self.line(loss, risk, daily_counts_open=False)
        self.assertIn(">today -100 $ · limit 500 $<", html)
        _, html = self.line(loss, risk, daily_counts_closed=False)
        self.assertIn(">100 $ at risk in open trades · limit 500 $<", html)
        _, html = self.line(loss, daily_counts_closed=False)
        self.assertIn(">nothing at risk in open trades · limit 500 $<", html)


class AccountFileCase(unittest.TestCase):
    """The new keys of an account: optional, never written empty."""

    def test_round_trip_and_defaults(self):
        a = Account(id="p", kind="prop", start_balance=1000, daily_loss_percent=4.5,
                    daily_counts_open=False)
        text = store.account_to_text(a)
        self.assertIn("daily loss limit %: 4.5", text)
        self.assertIn("daily limit counts open risk: no", text)
        self.assertNotIn("daily limit counts closed", text)
        self.assertNotIn("daily loss limit:", text)
        back = store.text_to_account(text)
        self.assertEqual((back.daily_loss_limit, back.daily_loss_percent,
                          back.daily_counts_closed, back.daily_counts_open),
                         (None, 4.5, True, False))
        self.assertEqual(store.account_to_text(back), text)

    def test_an_old_file_reads_as_before(self):
        old = ("---\nid: p\nname: p\nkind: prop\nstart balance: 1000\n"
               "currency: USD\narchived: no\ndaily loss limit: 50\n---\n")
        a = store.text_to_account(old).check()
        self.assertEqual((a.daily_loss_limit, a.daily_loss_percent,
                          a.daily_counts_closed, a.daily_counts_open),
                         (50, None, True, True))
        self.assertEqual(store.account_to_text(a), old)

    def test_money_and_percent_together_do_not_read(self):
        with self.assertRaises(RecordError):
            Account(id="p", daily_loss_limit=50, daily_loss_percent=5).check()
        with self.assertRaises(RecordError):
            Account(id="p", daily_loss_percent=0).check()


class FormCase(unittest.TestCase):
    """The rules form and the pages, on a journal of their own."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.save_account(cls.root, Account(id="big", name="Big", kind="prop",
                                             start_balance=100000))
        store.save_account(cls.root, Account(id="funded", name="Funded",
                                             kind="prop", start_balance=0))
        store.save_adjustment(cls.root, deposit(1, 100000, datetime(2026, 8, 1),
                                                account="funded"))
        os.environ["PLAINBOOK_ROOT"] = cls.root
        import plainbook.server
        cls.S = importlib.reload(plainbook.server)
        cls.server = cls.S.Server(("127.0.0.1", 0), cls.S.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()
        os.environ.pop("PLAINBOOK_ROOT", None)

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path):
        with urllib.request.urlopen(self.url(path)) as r:
            return r.read().decode("utf-8")

    def answer(self, path, fields):
        data = urllib.parse.urlencode(fields, doseq=True).encode("utf-8")
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url(path),
                                                               data=data)) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read().decode("utf-8")

    def account(self, ident):
        return store.all_accounts(self.root)[ident]

    def value(self, html, name):
        return re.search(rf'name="{name}"[^>]*?value="([^"]*)"', html, re.S).group(1)

    def test_a_percent_is_kept_and_shown_back(self):
        self.answer("/account/big/rules", {"kind": "prop", "daily": "4.5%",
                                           "mode": "static", "daily_counts": "1",
                                           "daily_closed": "1", "daily_open": "1"})
        a = self.account("big")
        self.assertEqual((a.daily_loss_limit, a.daily_loss_percent), (None, 4.5))
        html = self.get("/account/big/rules")
        self.assertEqual(self.value(html, "daily"), "4.5%")
        self.assertIn("daily 4.5% = 4 500 $", self.get("/accounts"))
        self.assertIn("limit 4 500 $ (4.5%)", self.get("/accounts"))

    def test_the_boxes_are_read_only_with_their_marker(self):
        self.answer("/account/big/rules", {"kind": "prop", "daily": "500",
                                           "mode": "static", "daily_counts": "1",
                                           "daily_closed": "1"})
        a = self.account("big")
        self.assertEqual((a.daily_counts_closed, a.daily_counts_open), (True, False))
        html = self.get("/account/big/rules")
        self.assertRegex(html, r'name="daily_closed" value="1" checked')
        self.assertRegex(html, r'name="daily_open" value="1">')
        self.assertIn("(closed result only)", self.get("/accounts"))
        # a form that did not draw the boxes leaves them as they are
        self.answer("/account/big/rules", {"kind": "prop", "daily": "500",
                                           "mode": "static"})
        a = self.account("big")
        self.assertEqual((a.daily_counts_closed, a.daily_counts_open), (True, False))
        # a limit that counts nothing is refused, and nothing changes
        code, _ = self.answer("/account/big/rules", {"kind": "prop", "daily": "500",
                                                     "mode": "static",
                                                     "daily_counts": "1"})
        self.assertEqual(code, 400)
        self.assertFalse(self.account("big").daily_counts_open)
        self.answer("/account/big/rules", {"kind": "prop", "daily": "500",
                                           "mode": "static", "daily_counts": "1",
                                           "daily_closed": "1", "daily_open": "1"})
        with open(os.path.join(self.root, "journal", "accounts", "big.md"),
                  encoding="utf-8") as f:
            self.assertNotIn("counts", f.read())

    def test_a_funded_account_takes_its_percents_of_the_deposit(self):
        self.answer("/account/funded/rules", {"kind": "prop", "max": "10%",
                                              "target": "8%", "mode": "static"})
        a = self.account("funded")
        self.assertEqual((a.max_loss, a.profit_target), (10000, 8000))
        self.assertIn("floor 90 000 $ (static)", self.get("/accounts"))
        html = self.get("/account/funded/rules")
        self.assertIn("the start balance and the deposits up to the first trade", html)

    def test_lite_shows_the_boxes_as_it_shows_every_rule(self):
        with open(store.settings_file(self.root), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write("---\nedition: lite\n---\n")
        self.S.drop_cache()
        try:
            html = self.get("/account/big/rules")
            self.assertIn("<title>Plainbook Lite: ", html)
            self.assertIn('name="daily_counts"', html)
            self.assertIn('name="daily_open"', html)
        finally:
            os.remove(store.settings_file(self.root))
            self.S.drop_cache()

    def test_a_percent_of_nothing_is_refused(self):
        store.save_account(self.root, Account(id="bare", kind="prop", start_balance=0))
        self.S.drop_cache()
        code, _ = self.answer("/account/bare/rules", {"kind": "prop", "max": "10%",
                                                      "mode": "static"})
        self.assertEqual(code, 400)


class RiskCase(unittest.TestCase):
    """Decision 1: a risk typed in money comes back to the cent."""

    @classmethod
    def setUpClass(cls):
        import plainbook.server
        cls.S = plainbook.server

    def test_twenty_five_dollars_on_a_hundred_thousand(self):
        percent = self.S.parse_risk("25$", 100000)
        self.assertEqual(percent, 0.025)
        a = Account(id="a", start_balance=100000)
        t = trade(1, account="a", pnl=-25, risk=percent)
        j = Journal({"a": a}, [t], [])
        self.assertAlmostEqual(j.computed[t.id].risk_money, 25)
        self.assertAlmostEqual(j.r(t.id), -1.0)

    def test_every_sum_comes_back_to_the_cent(self):
        for money, balance in [(25.37, 100000), (25.37, 98765.43), (0.01, 100000),
                               (123456.78, 9876543.21), (1, 3)]:
            p = self.S.money_to_percent(money, balance)
            self.assertEqual(round(balance * p / 100, 2), money, (money, balance))

    def test_the_old_half_up_cases_at_the_new_precision(self):
        # two decimals rounded 100.5 of 10 000 up to 1.01; now it is exact,
        # and the half still goes up at the last decimal kept
        self.assertEqual(self.S.money_to_percent(100.5, 10000), 1.005)
        self.assertEqual(self.S.money_to_percent(124.5, 10000), 1.245)
        self.assertEqual(self.S.money_to_percent(1, 3), 33.33)
        self.assertEqual(self.S.money_to_percent(2, 3), 66.67)
        self.assertEqual(self.S.money_to_percent(133, 10000), 1.33)

    def test_an_old_record_keeps_its_two_decimals(self):
        t = trade(1, risk=0.03)
        back = store.text_to_trade(store.trade_to_text(t))
        self.assertEqual(back.risk, 0.03)
        t.risk = 0.02537
        self.assertIn("risk %: 0.02537", store.trade_to_text(t))

    def test_the_page_prints_the_percent_beside_its_money(self):
        self.assertEqual(self.S.risk_text(0.02537), "0.02537%")
        self.assertEqual(self.S.risk_text(0.00001), "0.00001%")
        self.assertIn("function money_percent", self.S.RISK_HINT_SCRIPT)


if __name__ == "__main__":
    unittest.main()
