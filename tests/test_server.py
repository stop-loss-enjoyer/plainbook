#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End to end: open a trade, paste a screenshot, close it, edit it."""
import importlib
import json
import os
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import stats, store
from plainbook.model import Account

# a one-pixel PNG, enough to exercise the whole screenshot path
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "05572bd6a20000000049454e44ae426082")


class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.save_account(cls.root, Account(id="broker", name="Broker",
                                             start_balance=10000))
        store.save_account(cls.root, Account(id="legacy", name="Legacy",
                                             start_balance=5000, archived=True))
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

    # --- helpers ---
    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path, as_text=True):
        with urllib.request.urlopen(self.url(path)) as r:
            data = r.read()
            return r.status, data.decode("utf-8") if as_text else data

    def landed(self, where):
        """The record a form landed on: the last part of the path, the word the
        journal said left out of it."""
        return urllib.parse.unquote(
            urllib.parse.urlparse(where).path.rsplit("/", 1)[1])

    def post(self, path, fields):
        data = urllib.parse.urlencode(fields, doseq=True).encode("utf-8")
        req = urllib.request.Request(self.url(path), data=data)
        with urllib.request.urlopen(req) as r:
            return r.status, r.geturl()

    def paste_shot(self, token, zone):
        req = urllib.request.Request(
            self.url(f"/draft/upload?token={token}&zone={zone}"),
            data=PNG, headers={"Content-Type": "image/png"})
        with urllib.request.urlopen(req) as r:
            return json.load(r)

    def form_token(self, html):
        return re.search(r'name="token" value="([0-9a-f]{16})"', html).group(1)

    # --- checks ---
    def test_01_home_page_opens(self):
        code, html = self.get("/")
        self.assertEqual(code, 200)
        self.assertIn("Broker", html)
        self.assertIn("10 000 $", html)         # account tile: name and balance
        self.assertNotIn("1% =", html)          # no risk conversion here

    def test_01a_header_links_work(self):
        _, html = self.get("/")
        header = re.findall(r'<header.*?</header>', html, re.S)[0]
        for href in re.findall(r'<a href="([^"]+)"', header):
            if href.startswith("/") and "new" not in href:
                self.assertEqual(self.get(href)[0], 200, href)

    def test_01b_form_has_no_risk_hint_but_has_a_calendar(self):
        _, html = self.get("/new")
        self.assertNotIn("Risk in money", html)  # percents are worked out in the head
        self.assertIn("showPicker", html)        # clicking the date opens the calendar

    def test_02_archived_account_is_not_offered(self):
        _, html = self.get("/new")
        field = re.search(r'<select name="account">(.*?)</select>', html, re.S).group(1)
        self.assertIn("broker", field)
        self.assertNotIn("legacy", field)

    def test_03_open_a_trade_with_a_screenshot(self):
        _, html = self.get("/new")
        token = self.form_token(html)
        shot = self.paste_shot(token, "idea-1")
        code, where = self.post("/new", {
            "token": token, "blocks": "1", "account": "broker", "pair": "EURUSD",
            "direction": "long", "style": "swing", "entry_tf": "H4",
            "execution": ["Market Entry", "SNR"], "risk": "1",
            "entry": "2026-08-29T14:30", "idea_tf_1": "H4",
            "idea_text_1": "breakout, waiting for a retest",
            "file_idea-1": shot["file"]})
        self.assertEqual(code, 200)
        ServerCase.trade_id = self.landed(where)
        t = store.load_trade(self.root, ServerCase.trade_id)
        self.assertEqual(t.pair, "EURUSD")
        self.assertEqual(t.execution, ["Market Entry", "SNR"])
        self.assertTrue(t.is_open)
        self.assertEqual(t.idea[0].images, ["shots/idea-01-01.png"])
        self.assertTrue(os.path.exists(os.path.join(
            store.shots_dir(self.root, t.id), "idea-01-01.png")))

    def test_04_an_open_trade_shows_on_the_home_page(self):
        _, html = self.get("/")
        self.assertIn("Open positions", html)
        self.assertIn(ServerCase.trade_id, html)

    def test_05_trade_page_and_its_screenshot(self):
        code, html = self.get(f"/trade/{urllib.parse.quote(ServerCase.trade_id)}")
        self.assertEqual(code, 200)
        self.assertIn("breakout, waiting for a retest", html)
        path = re.search(r'src="(/shot/[^"]+)"', html).group(1)
        code, data = self.get(path, as_text=False)
        self.assertEqual(code, 200)
        self.assertTrue(data.startswith(b"\x89PNG"))

    def test_06_close_the_trade(self):
        q = urllib.parse.quote(ServerCase.trade_id)
        _, html = self.get(f"/close/{q}")
        token = self.form_token(html)
        shot = self.paste_shot(token, "exit")
        self.post(f"/close/{q}", {
            "token": token, "result": "Win", "pnl": "250",
            "exit": "2026-08-31", "conclusions": "held to target",
            "file_exit": shot["file"]})
        t = store.load_trade(self.root, ServerCase.trade_id)
        self.assertEqual(t.result, "Win")
        self.assertEqual(t.pnl, 250.0)
        self.assertEqual(t.exit_images, ["shots/exit-01.png"])
        self.assertIn("held to target", t.conclusions)
        self.assertFalse(t.is_open)

    def test_07_r_is_measured_against_the_balance_at_entry(self):
        _, html = self.get(f"/trade/{urllib.parse.quote(ServerCase.trade_id)}")
        self.assertIn("+2.50", html)               # 250 $ against 100 $ of risk

    def test_08_editing_changes_fields_and_cleans_shots(self):
        q = urllib.parse.quote(ServerCase.trade_id)
        _, html = self.get(f"/edit/{q}")
        token = self.form_token(html)
        self.post(f"/edit/{q}", {
            "token": token, "blocks": "1", "account": "broker", "pair": "GBPUSD",
            "direction": "short", "style": "EMT", "entry_tf": "H1",
            "risk": "0.5", "entry": "2026-08-29T14:30", "idea_tf_1": "H1",
            "idea_text_1": "idea rewritten",
            "have_idea-1": "shots/idea-01-01.png",
            "remove": "shots/idea-01-01.png",       # this screenshot goes away
            "have_exit": "shots/exit-01.png"})
        # the pair changed, so the folder follows it and keeps its number
        self.assertFalse(os.path.isdir(store.trade_dir(self.root, ServerCase.trade_id)))
        ServerCase.trade_id = "2026-08-29-01-gbpusd"
        t = store.load_trade(self.root, ServerCase.trade_id)
        self.assertEqual(t.pair, "GBPUSD")
        self.assertEqual(t.style, "EMT")
        self.assertEqual(t.risk, 0.5)
        self.assertEqual(t.idea[0].images, [])      # the removed shot is gone
        self.assertEqual(t.exit_images, ["shots/exit-01.png"])
        files = os.listdir(store.shots_dir(self.root, t.id))
        self.assertNotIn("idea-01-01.png", files)   # and off the disk too

    def test_09_a_bad_form_does_not_break_the_journal(self):
        before = len(store.all_trades(self.root))
        data = urllib.parse.urlencode({
            "token": "0" * 16, "blocks": "1", "account": "broker", "pair": "EURUSD",
            "direction": "sideways", "style": "swing", "risk": "1",
            "entry": "2026-08-29T10:00"}).encode()
        req = urllib.request.Request(self.url("/new"), data=data)
        try:
            urllib.request.urlopen(req)
            self.fail("the server swallowed junk")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            e.close()
        self.assertEqual(len(store.all_trades(self.root)), before)

    def test_10_a_report_builds_and_keeps_its_conclusions(self):
        self.post("/report/build", {"what": "month", "period_month": "2026-08"})
        code, html = self.get("/report/2026-08")
        self.assertEqual(code, 200)
        self.assertIn("August 2026", html)
        self.post("/report/2026-08", {"conclusions": "what the month taught me"})
        _, html = self.get("/report/2026-08")
        self.assertIn("what the month taught me", html)
        self.post("/report/build", {"what": "month", "period_month": "2026-08"})
        _, html = self.get("/report/2026-08")
        self.assertIn("what the month taught me", html)   # a rebuild kept them

    def test_11_statistics_renders(self):
        code, html = self.get("/stats")
        self.assertEqual(code, 200)
        self.assertIn("<svg", html)
        self.assertIn("R distribution", html)

    def test_12_open_trade_counter(self):
        code, body = self.get("/open-count")
        self.assertEqual(code, 200)
        self.assertEqual(body.strip(), "0")

    def test_13_a_foreign_origin_is_refused(self):
        req = urllib.request.Request(self.url("/new"), data=b"x=1",
                                     headers={"Origin": "http://evil.example"})
        try:
            urllib.request.urlopen(req)
            self.fail("a foreign origin was accepted")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 403)
            e.close()

    def test_14_accounts_are_created_archived_and_deleted(self):
        code, where = self.post("/account/new", {
            "id": "ünïcode", "name": "Test", "start": "5000", "currency": "USD"})
        self.assertIn("latin", urllib.parse.unquote(where))   # a non-latin id is refused
        self.post("/account/new", {"id": "test-acc", "name": "Test",
                                   "start": "5000", "currency": "USD"})
        self.assertIn("test-acc", store.all_accounts(self.root))
        _, html = self.get("/new")
        self.assertIn("test-acc", html)                      # offered at once

        self.post("/account/archive", {"id": "test-acc"})
        self.assertTrue(store.all_accounts(self.root)["test-acc"].archived)
        _, html = self.get("/new")
        field = re.search(r'<select name="account">(.*?)</select>', html, re.S).group(1)
        self.assertNotIn("test-acc", field)                  # archived is not offered

        self.post("/account/delete", {"id": "test-acc"})
        self.assertNotIn("test-acc", store.all_accounts(self.root))

    def test_15_an_account_with_trades_is_not_deleted(self):
        _, where = self.post("/account/delete", {"id": "broker"})
        self.assertIn("archive it instead", urllib.parse.unquote(where))
        self.assertIn("broker", store.all_accounts(self.root))

    def test_16_pairs_are_added_and_removed(self):
        self.post("/pair/new", {"pair": "eurjpy"})
        self.assertIn("EURJPY", store.all_pairs(self.root))
        _, html = self.get("/new")
        self.assertIn("EURJPY", html)                        # in the suggestions
        self.post("/pair/delete", {"pair": "EURJPY"})
        self.assertNotIn("EURJPY", store.all_pairs(self.root))

    def test_17_the_edit_form_keeps_the_exit_and_the_conclusions(self):
        """Editing a closed trade must not wipe its exit screenshots: the form
        did not show them, and saving rewrote the shots folder from the form."""
        q = urllib.parse.quote(ServerCase.trade_id)
        _, html = self.get(f"/edit/{q}")
        self.assertIn('name="have_exit"', html)
        self.assertIn('name="closed"', html)
        self.assertIn('class="remove"', html)      # the cross on a thumbnail
        token = self.form_token(html)
        self.post(f"/edit/{q}", {
            "token": token, "closed": "1", "blocks": "1", "account": "broker",
            "pair": "GBPUSD", "direction": "short", "style": "EMT",
            "entry_tf": "H1", "risk": "0.5", "entry": "2026-08-29T14:30",
            "idea_text_1": "idea rewritten", "result": "Win", "pnl": "250",
            "exit": "2026-08-31",
            "have_exit": "shots/exit-01.png", "conclusions": "held to target"})
        t = store.load_trade(self.root, ServerCase.trade_id)
        self.assertEqual(t.exit_images, ["shots/exit-01.png"])
        self.assertIn("held to target", t.conclusions)

    def test_18_a_screenshot_leaves_with_its_own_field(self):
        """The cross in the form only drops a hidden field, and the server knows
        nothing about a delete, it rebuilds the folder from what arrived."""
        q = urllib.parse.quote(ServerCase.trade_id)
        _, html = self.get(f"/edit/{q}")
        token = self.form_token(html)
        self.post(f"/edit/{q}", {
            "token": token, "closed": "1", "blocks": "1", "account": "broker",
            "pair": "GBPUSD", "direction": "short", "style": "EMT",
            "entry_tf": "H1", "risk": "0.5", "entry": "2026-08-29T14:30",
            "idea_text_1": "idea rewritten", "result": "Win", "pnl": "250",
            "exit": "2026-08-31", "conclusions": "held to target"})
        t = store.load_trade(self.root, ServerCase.trade_id)
        self.assertEqual(t.exit_images, [])
        self.assertEqual(os.listdir(store.shots_dir(self.root, t.id)), [])

    def test_18a_the_result_is_picked_and_not_defaulted(self):
        """A menu with no empty option arrives with its first value picked, so a
        trade closed without a glance at the field came out a Win."""
        q = urllib.parse.quote(ServerCase.trade_id)
        _, html = self.get(f"/close/{q}")
        self.assertIn("pick one", html)
        self.assertIn("required", html.split('name="result"')[1][:40])
        token = self.form_token(html)
        data = urllib.parse.urlencode({
            "token": token, "result": "", "pnl": "-250",
            "exit": "2026-08-31"}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(self.url(f"/close/{q}"),
                                                          data=data))
            self.fail("the server closed a trade with no result")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            e.close()

    def test_18b_a_wrong_result_is_fixed_by_editing(self):
        """The result was Win on a losing trade and there was no way back."""
        q = urllib.parse.quote(ServerCase.trade_id)
        _, html = self.get(f"/edit/{q}")
        self.assertIn('name="result"', html)
        token = self.form_token(html)
        self.post(f"/edit/{q}", {
            "token": token, "closed": "1", "blocks": "1", "account": "broker",
            "pair": "GBPUSD", "direction": "short", "style": "EMT",
            "entry_tf": "H1", "risk": "0.5", "entry": "2026-08-29T14:30",
            "idea_text_1": "idea rewritten", "result": "Lose", "pnl": "-250",
            "exit": "2026-09-01T14:30", "conclusions": "held to target"})
        t = store.load_trade(self.root, ServerCase.trade_id)
        self.assertEqual(t.result, "Lose")
        self.assertEqual(t.pnl, -250.0)
        self.assertEqual(f"{t.closed:%Y-%m-%d %H:%M}", "2026-09-01 14:30")
        self.assertTrue(t.closed_time)          # the hour orders the day
        # and back, so the trades the tests below count stay what they were
        self.post(f"/edit/{q}", {
            "token": self.form_token(self.get(f"/edit/{q}")[1]),
            "closed": "1", "blocks": "1", "account": "broker",
            "pair": "GBPUSD", "direction": "short", "style": "EMT",
            "entry_tf": "H1", "risk": "0.5", "entry": "2026-08-29T14:30",
            "idea_text_1": "idea rewritten", "result": "Win", "pnl": "250",
            "exit": "2026-08-31", "conclusions": "held to target"})
        self.assertEqual(store.load_trade(self.root, ServerCase.trade_id).result,
                         "Win")

    def test_19_the_list_groups_by_weeks_months_and_quarters(self):
        _, html = self.get("/")
        self.assertIn('class="group"', html)
        self.assertIn("this week", html)
        self.assertRegex(html, r'class="label">W\d\d<')      # weeks by default
        _, html = self.get("/?" + urllib.parse.urlencode({"group": "month"}))
        self.assertIn("August 2026", html)
        _, html = self.get("/?" + urllib.parse.urlencode({"group": "quarter"}))
        self.assertIn("Q3 2026", html)

    def test_20_a_trade_is_deleted_into_the_trash(self):
        q = urllib.parse.quote(ServerCase.trade_id)
        _, html = self.get(f"/trade/{q}")
        self.assertIn(f"/trade/{q}/delete", html)
        before = len(store.all_trades(self.root))
        self.post(f"/trade/{q}/delete", {})
        self.assertEqual(len(store.all_trades(self.root)), before - 1)
        self.assertFalse(os.path.isdir(store.trade_dir(self.root, ServerCase.trade_id)))
        trash = os.path.join(self.root, store.TRASH)
        # the record has not vanished: it sits in the trash under its own id
        self.assertTrue(any(name.startswith(ServerCase.trade_id)
                            for name in os.listdir(trash)))
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.get(f"/trade/{q}")
        self.assertEqual(e.exception.code, 404)
        e.exception.close()

    def test_21_a_card_is_written_and_read_back(self):
        _, html = self.get("/card/2026-08-29")
        self.assertIn("Daily report card", html)
        self.assertIn("current focus (goal)", html)
        self.post("/card/save", {
            "date": "2026-08-29", "previous": "2026-08-29", "grade": "B",
            "pnl": "250", "quality": "A", "focus": "no counter-trend trades",
            "process": "followed the plan", "learned": "waited for the retest",
            "errors": "moved the stop too early", "best": "EURUSD short",
            "overview": "an even day"})
        k = store.load_card(self.root, datetime(2026, 8, 29))
        self.assertEqual(k.grade, "B")
        self.assertEqual(k.pnl, 250.0)
        self.assertEqual(k.quality, "A")
        self.assertEqual(k.focus, "no counter-trend trades")
        self.assertEqual(k.overview, "an even day")
        _, html = self.get("/card/2026-08-29")
        self.assertIn("waited for the retest", html)   # the form came back filled
        _, html = self.get("/cards")
        self.assertIn("29.08.2026", html)
        self.assertIn("an even day", html)

    def test_21a_a_daily_card_carries_a_trades_assessment(self):
        """The paper's numbered lines, same as the weekly card's."""
        _, html = self.get("/card/2026-08-30")
        self.assertIn("trades assessment", html)
        self.post("/card/save", {
            "date": "2026-08-30", "previous": "2026-08-30", "grade": "A",
            "focus": "one setup a day",
            "assess_trade": ["EURUSD long", "", "XAU short", "", ""],
            "assess_grade": ["A", "", "C", "", ""]})
        k = store.load_card(self.root, datetime(2026, 8, 30))
        # the empty rows of the paper table are not records
        self.assertEqual([(r.trade, r.grade) for r in k.assessment],
                         [("EURUSD long", "A"), ("XAU short", "C")])
        _, html = self.get("/card/2026-08-30")
        self.assertIn('value="XAU short"', html)

    def test_22_changing_the_date_moves_the_card(self):
        self.post("/card/save", {
            "date": "2026-08-27", "previous": "2026-08-29", "grade": "B",
            "pnl": "250", "quality": "A", "focus": "no counter-trend trades",
            "overview": "an even day"})
        self.assertIsNone(store.load_card(self.root, datetime(2026, 8, 29)))
        self.assertIsNotNone(store.load_card(self.root, datetime(2026, 8, 27)))

    def test_23_a_card_is_deleted_into_the_trash(self):
        self.post("/card/2026-08-27/delete", {})
        self.assertIsNone(store.load_card(self.root, datetime(2026, 8, 27)))
        trash = os.path.join(self.root, store.TRASH)
        self.assertTrue(any(name.startswith("card-2026-08-27")
                            for name in os.listdir(trash)))

    def test_23a_a_card_with_empty_fields_saves_and_opens(self):
        """A card with no P&L and no quality used to crash the page: an empty
        key in the header reads back as a list, and float('[]') killed it."""
        self.post("/card/save", {
            "date": "2026-08-26", "previous": "2026-08-26", "grade": "A",
            "pnl": "", "quality": "", "focus": "pennies"})
        code, html = self.get("/card/2026-08-26")
        self.assertEqual(code, 200)
        self.assertIn("pennies", html)
        # empty fields have to stay empty, not become "[]"
        self.assertRegex(html, r'name="quality"[^>]*value=""')
        self.assertRegex(html, r'name="pnl"[^>]*value=""')
        code, html = self.get("/cards")
        self.assertEqual(code, 200)
        self.assertIn("26.08.2026", html)

    def test_24_a_broken_card_date_does_not_break_the_server(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.get("/card/2026-13-99")
        self.assertEqual(e.exception.code, 404)
        e.exception.close()

    def test_25_money_goes_in_and_out_and_cashouts_are_counted(self):
        self.post("/account/new", {"id": "money-acc", "name": "Money",
                                   "start": "10000", "currency": "USD"})
        self.post("/money/new", {"account": "money-acc", "kind": "deposit",
                                 "amount": "2000", "day": "2026-08-20",
                                 "comment": "top up"})
        self.post("/money/new", {"account": "money-acc", "kind": "withdrawal",
                                 "amount": "500", "day": "2026-08-25",
                                 "comment": "payout"})
        kept = {c.id: c for c in store.all_adjustments(self.root)}
        deposit = kept["2026-08-20-deposit-money-acc"]
        payout = kept["2026-08-25-withdrawal-money-acc"]
        self.assertEqual(deposit.amount, 2000)
        self.assertEqual(payout.amount, -500)           # the sign is the kind's
        code, html = self.get("/accounts")
        self.assertEqual(code, 200)
        self.assertIn("11 500", html)                   # balance after both
        self.assertIn("500", html)                      # cashed out
        # a payout is not a loss: the tile shows what was earned, and says
        # separately what was moved
        _, home = self.get("/")
        self.assertIn("cashed out", home)
        self.assertIn("added", home)

    def test_26_correcting_a_balance_writes_down_the_difference(self):
        self.post("/money/correct", {"account": "money-acc", "balance": "11450",
                                     "day": "2026-08-26", "comment": "swap"})
        gap = {c.id: c for c in store.all_adjustments(self.root)}[
            "2026-08-26-reconciliation-money-acc"]
        self.assertEqual(gap.kind, "reconciliation")
        self.assertEqual(gap.amount, -50)
        _, where = self.post("/money/correct", {"account": "money-acc",
                                                "balance": "11450"})
        self.assertIn("nothing to correct", urllib.parse.unquote(where))

    def test_27_a_money_record_is_deleted_into_the_trash(self):
        self.post("/money/delete", {"id": "2026-08-26-reconciliation-money-acc"})
        left = {c.id for c in store.all_adjustments(self.root)}
        self.assertNotIn("2026-08-26-reconciliation-money-acc", left)
        self.assertTrue(any("2026-08-26-reconciliation-money-acc" in name
                            for name in os.listdir(os.path.join(self.root, ".trash"))))
        _, where = self.post("/money/delete", {"id": "no-such-record"})
        self.assertIn("no such record", urllib.parse.unquote(where))

    def test_28_a_bad_money_form_is_refused(self):
        _, where = self.post("/money/new", {"account": "nowhere", "kind": "deposit",
                                            "amount": "10"})
        self.assertIn("no such account", urllib.parse.unquote(where))
        _, where = self.post("/money/new", {"account": "money-acc",
                                            "kind": "reconciliation", "amount": "10"})
        self.assertIn("bad kind", urllib.parse.unquote(where))
        _, where = self.post("/money/new", {"account": "money-acc", "kind": "fee",
                                            "amount": "0"})
        self.assertIn("amount is zero", urllib.parse.unquote(where))

    def test_29_statistics_leaves_archived_accounts_off_the_charts(self):
        """An archived account is done with: nothing to watch on its curve.
        Its trades still count in the figures underneath."""
        code, html = self.get("/stats")
        self.assertEqual(code, 200)
        tabs = re.search(r'Equity by account.*?</p>', html, re.S).group(0)
        self.assertIn("Broker", tabs)
        self.assertNotIn("Legacy", tabs)                 # archived
        self.assertIn("Archived accounts are not drawn", html)
        # picked by hand through the filter, it is shown again
        _, html = self.get("/stats?account=legacy")
        self.assertIn("Legacy", html)

    def test_30_the_r_rings_split_wins_from_losses(self):
        """A win and a loss land in their own ring, with their R in the middle."""
        for result, pnl in (("Win", "300"), ("Lose", "-100")):
            _, html = self.get("/new")
            token = self.form_token(html)
            _, where = self.post("/new", {
                "token": token, "blocks": "1", "account": "broker", "pair": "EURUSD",
                "direction": "long", "style": "swing", "entry_tf": "H4",
                "risk": "1", "entry": "2026-08-20T10:00"})
            tid = self.landed(where)
            _, html = self.get(f"/close/{urllib.parse.quote(tid)}")
            self.post(f"/close/{urllib.parse.quote(tid)}", {
                "token": self.form_token(html), "result": result, "pnl": pnl,
                "exit": "2026-08-21", "conclusions": ""})
        code, html = self.get("/stats")
        self.assertEqual(code, 200)
        rings = re.search(r'R distribution.*?</div></div>\s*<p class="caption">',
                          html, re.S).group(0)
        self.assertIn("Losses", rings)
        self.assertIn("Wins", rings)
        self.assertIn("closed", rings)
        # the loss is the stop itself, the win about three R: each in its bucket
        self.assertIn("-1…-1.2", rings)
        self.assertIn("+3R and more", rings)

    def test_31_the_pair_field_offers_pairs_with_their_flags(self):
        """The browser's own list cannot carry the flags, so the form has its
        own. Typing a pair that is not in it still has to work."""
        self.post("/pair/new", {"pair": "EURUSD"})
        _, html = self.get("/new")
        self.assertIn('class="picker"', html)
        self.assertIn('data-value="EURUSD"', html)
        self.assertIn('<use href="#fl-eu"', html)       # the flag itself
        self.assertNotIn('<datalist', html)
        # a pair nobody has heard of goes in by hand, as before
        _, html = self.get("/new")
        token = self.form_token(html)
        _, where = self.post("/new", {
            "token": token, "blocks": "1", "account": "broker", "pair": "WHATEVER",
            "direction": "long", "style": "swing", "entry_tf": "H4",
            "risk": "1", "entry": "2026-08-19T10:00"})
        tid = self.landed(where)
        self.assertEqual(store.load_trade(self.root, tid).pair, "WHATEVER")

    def test_32_money_and_corrections_are_folded_and_kept_apart(self):
        self.post("/money/new", {"account": "broker", "kind": "withdrawal",
                                 "amount": "100", "day": "2026-08-18"})
        self.post("/money/correct", {"account": "broker", "balance": "12345",
                                     "day": "2026-08-19", "comment": "broker"})
        _, html = self.get("/accounts")
        self.assertIn('<details class="fold"><summary>Money in and out', html)
        self.assertIn('<details class="fold"><summary>Correct a balance', html)
        money = html[html.index("Money in and out"):html.index("Correct a balance")]
        corrections = html[html.index("Correct a balance"):]
        # a correction belongs under corrections, not among the deposits
        self.assertIn("withdrawal", money)
        self.assertNotIn("reconciliation", money)
        self.assertIn("reconciliation", corrections)
        self.assertNotIn("withdrawal", corrections)

    def test_33_a_report_row_leads_to_the_trades_behind_it(self):
        """A pair or an account in a report opens the journal filtered to it,
        over the months of that report."""
        self.post("/report/build", {"what": "month", "period_month": "2026-08"})
        _, html = self.get("/report/2026-08")
        self.assertIn("/?pair=EURUSD&from=2026-08&to=2026-08", html)
        self.assertIn("/?account=broker&from=2026-08&to=2026-08", html)
        self.assertIn("/?style=swing&from=2026-08&to=2026-08", html)
        # the head of a table is not a link: "account" is not an account
        self.assertNotIn("/?account=account", html)
        # and the address really does narrow the journal
        _, page = self.get("/?pair=EURUSD&from=2026-08&to=2026-08")
        self.assertIn("EURUSD", page)
        _, page = self.get("/?pair=EURUSD&from=2026-01&to=2026-01")
        self.assertIn("Nothing matches the filter", page)

    def test_34_the_conclusions_field_starts_empty(self):
        """It used to open with a hint inside it that had to be deleted first."""
        # a period nobody has written conclusions for yet
        self.post("/report/build", {"what": "month", "period_month": "2026-07"})
        _, html = self.get("/report/2026-07")
        field = re.search(r'<textarea name="conclusions".*?>(.*?)</textarea>',
                          html, re.S).group(1)
        self.assertEqual(field, "")
        self.assertIn("What you learned this period", html)   # the placeholder
        # a report built with the old hint inside opens empty as well
        file = os.path.join(self.root, "journal", "reports", "2026-07.md")
        with open(file, encoding="utf-8") as f:
            text = f.read()
        with open(file, "w", encoding="utf-8") as f:
            f.write(text.rstrip() + "\n\n_(empty, write it in the browser)_\n")
        _, html = self.get("/report/2026-07")
        self.assertNotIn("write it in the browser", html)

    def test_35_a_trade_is_duplicated_on_the_ticked_accounts(self):
        """One form, three trades: the same idea, an account and a risk each."""
        self.post("/account/new", {"id": "prop-100k", "name": "prop 100k",
                                   "start": "100000", "currency": "USD"})
        self.post("/account/new", {"id": "prop-50k", "name": "prop 50k",
                                   "start": "50000", "currency": "USD"})
        _, html = self.get("/new")
        self.assertIn("Duplicate on other accounts", html)
        # every live account has a row, the trade's own is taken away on screen
        self.assertIn('data-account="prop-100k"', html)
        self.assertIn('data-account="prop-50k"', html)
        self.assertIn('data-account="broker"', html)
        token = self.form_token(html)
        shot = self.paste_shot(token, "idea-1")
        before = {t.id for t in store.all_trades(self.root)}
        code, where = self.post("/new", {
            "token": token, "blocks": "1", "account": "broker", "pair": "GBPUSD",
            "direction": "short", "style": "swing", "entry_tf": "H4",
            "risk": "2", "entry": "2026-08-30T09:00", "idea_tf_1": "H4",
            "idea_text_1": "range high, selling the sweep",
            "file_idea-1": shot["file"],
            "dup": ["prop-100k", "prop-50k"],
            "dup_risk_prop-100k": "0.5", "dup_risk_prop-50k": "0.25",
            "dup_risk_broker": "9"})
        self.assertEqual(code, 200)
        fresh = [t for t in store.all_trades(self.root) if t.id not in before]
        self.assertEqual(len(fresh), 3)
        origin = next(t for t in fresh if t.account == "broker")
        copies = {t.account: t for t in fresh if t.account != "broker"}
        self.assertEqual(self.landed(where), origin.id)  # opens the one entered
        self.assertEqual(origin.risk, 2)
        self.assertEqual(copies["prop-100k"].risk, 0.5)
        self.assertEqual(copies["prop-50k"].risk, 0.25)
        for t in fresh:
            self.assertEqual(t.pair, "GBPUSD")
            self.assertEqual(t.direction, "short")
            self.assertEqual(t.idea[0].text, "range high, selling the sweep")
            # each has its own copy of the screenshot on the disk
            self.assertTrue(os.path.exists(os.path.join(
                store.shots_dir(self.root, t.id), "idea-01-01.png")))

    def test_36_a_tick_on_the_trades_own_account_writes_nothing_twice(self):
        _, html = self.get("/new")
        token = self.form_token(html)
        before = len(store.all_trades(self.root))
        code, _ = self.post("/new", {
            "token": token, "blocks": "1", "account": "broker", "pair": "EURUSD",
            "direction": "long", "style": "swing", "risk": "1",
            "entry": "2026-08-30T11:00", "idea_text_1": "no",
            "dup": "broker", "dup_risk_broker": "1"})
        self.assertEqual(code, 200)
        self.assertEqual(len(store.all_trades(self.root)), before + 1)

    def test_37_the_trade_form_lists_are_edited_on_the_accounts_tab(self):
        """Styles, timeframes and execution formats belong to the owner."""
        _, html = self.get("/new")
        self.assertIn(">swing<", html)                      # the defaults are there
        self.assertIn("Market Entry", html)

        self.post("/list/new", {"kind": "styles", "word": "scalp"})
        self.post("/list/new", {"kind": "timeframes", "word": "M5"})
        self.post("/list/new", {"kind": "execution", "word": "OB retest"})
        _, html = self.get("/new")
        field = re.search(r'<select name="style">(.*?)</select>', html, re.S).group(1)
        self.assertIn("scalp", field)
        tf = re.search(r'<select name="entry_tf">(.*?)</select>', html, re.S).group(1)
        self.assertEqual(tf.index("M5") > tf.index("D1"), True)   # added at the end
        self.assertIn("OB retest", html)
        self.assertEqual(store.all_words(self.root, "styles")[-1], "scalp")

        # the same word twice is refused, and the list is left as it was
        _, where = self.post("/list/new", {"kind": "styles", "word": "SCALP"})
        self.assertIn("already in the list", urllib.parse.unquote(where))
        self.assertEqual(store.all_words(self.root, "styles").count("scalp"), 1)

        self.post("/list/delete", {"kind": "timeframes", "word": "M15"})
        tf = re.search(r'<select name="entry_tf">(.*?)</select>',
                       self.get("/new")[1], re.S).group(1)
        self.assertNotIn("M15", tf)
        self.assertIn("H4", tf)                              # the rest is untouched

    def test_38_a_word_taken_out_stays_in_the_trades_that_carry_it(self):
        _, html = self.get("/new")
        token = self.form_token(html)
        code, where = self.post("/new", {
            "token": token, "blocks": "1", "account": "broker", "pair": "EURUSD",
            "direction": "long", "style": "scalp", "entry_tf": "M5",
            "execution": ["OB retest"], "risk": "1",
            "entry": "2026-08-31T08:00", "idea_text_1": "quick one"})
        self.assertEqual(code, 200)
        trade_id = self.landed(where)

        self.post("/list/delete", {"kind": "styles", "word": "scalp"})
        self.post("/list/delete", {"kind": "timeframes", "word": "M5"})
        self.post("/list/delete", {"kind": "execution", "word": "OB retest"})
        # the trade still reads back whole, and its own words are in its form
        t = store.load_trade(self.root, trade_id)
        self.assertEqual((t.style, t.entry_tf, t.execution),
                         ("scalp", "M5", ["OB retest"]))
        _, form = self.get(f"/edit/{urllib.parse.quote(trade_id)}")
        self.assertIn('value="scalp" selected', form)
        self.assertIn("OB retest", form)
        self.assertIn("M5", form)
        # saving the form back does not drop them
        edit_token = self.form_token(form)
        self.post(f"/edit/{urllib.parse.quote(trade_id)}", {
            "token": edit_token, "blocks": "1", "account": "broker",
            "pair": "EURUSD", "direction": "long", "style": "scalp",
            "entry_tf": "M5", "execution": ["OB retest"], "risk": "1",
            "entry": "2026-08-31T08:00", "idea_text_1": "quick one"})
        t = store.load_trade(self.root, trade_id)
        self.assertEqual((t.style, t.entry_tf, t.execution),
                         ("scalp", "M5", ["OB retest"]))
        # and the accounts page offers it back, saying how many trades hold it
        _, page = self.get("/accounts")
        self.assertIn("not offered", page)
        store.delete_trade(self.root, trade_id)

    def test_39_the_last_style_is_not_removed(self):
        for word in store.all_words(self.root, "styles")[1:]:
            self.post("/list/delete", {"kind": "styles", "word": word})
        left = store.all_words(self.root, "styles")
        self.assertEqual(len(left), 1)
        _, where = self.post("/list/delete", {"kind": "styles", "word": left[0]})
        self.assertIn("at least one", urllib.parse.unquote(where))
        self.assertEqual(store.all_words(self.root, "styles"), left)
        # a style of the list has a winrate tile of its own once it has trades
        _, home = self.get("/")
        traded = {t.style for t in store.all_trades(self.root)}
        self.assertEqual(f"winrate {left[0]}" in home, left[0] in traded)
        for style in traded & set(left):
            self.assertIn(f"winrate {style}", home)

    def test_40_a_report_carries_the_slices_the_charts_and_the_period_before(self):
        self.post("/report/build", {"what": "month", "period_month": "2026-08"})
        code, html = self.get("/report/2026-08")
        self.assertEqual(code, 200)
        for heading in ("By direction", "By entry TF", "By execution",
                        "Best and worst trade", "Process", "R distribution",
                        "deepest fall from a high"):
            self.assertIn(heading, html, heading)
        self.assertIn("July 2026", html)                 # the period compared with
        self.assertIn("<svg", html)                      # the rings are drawn
        # the named trade is a link to the trade itself
        best = re.search(r'<a href="/trade/([^"]+)">', html)
        self.assertTrue(best)
        self.assertEqual(self.get("/trade/" + best.group(1))[0], 200)

    def test_41_a_report_of_an_empty_period_still_opens(self):
        self.post("/report/build", {"what": "month", "period_month": "2026-05"})
        code, html = self.get("/report/2026-05")
        self.assertEqual(code, 200)
        self.assertIn("April 2026", html)                # nothing to compare with
        self.assertIn("Nothing to plot yet", html)

    def test_42_a_plan_is_written_and_a_trade_is_tied_to_it(self):
        _, html = self.get("/plans")
        self.assertIn("No plans yet", html)
        _, form = self.get("/plan/new")
        token = self.form_token(form)
        shot = self.paste_shot(token, "idea-1")
        code, where = self.post("/plan/new", {
            "token": token, "blocks": "1", "title": "weekly", "pair": "EURUSD",
            "narrative": "bullish", "from": "2026-08-31", "until": "2026-09-06",
            "idea_tf_1": "D1", "idea_text_1": "range formed",
            "file_idea-1": shot["file"],
            "plan_text": "long from the nearest SNR, no shorts"})
        self.assertEqual(code, 200)
        plan_id = self.landed(where)
        k = store.load_plan(self.root, plan_id)
        self.assertEqual((k.title, k.pair, k.narrative), ("weekly", "EURUSD", "bullish"))
        self.assertEqual(k.analysis[0].images, ["shots/idea-01-01.png"])
        self.assertEqual(
            self.get(f"/plan-shot/{plan_id}/idea-01-01.png", as_text=False)[0], 200)

        # the plan is offered in the form of a trade, and the trade keeps it
        _, form = self.get("/new")
        self.assertIn(plan_id, form)
        token = self.form_token(form)
        _, where = self.post("/new", {
            "token": token, "blocks": "1", "account": "broker", "pair": "EURUSD",
            "direction": "long", "style": "swing", "risk": "1",
            "entry": "2026-09-01T10:00", "idea_text_1": "per the plan",
            "plan": plan_id})
        trade_id = self.landed(where)
        self.assertEqual(store.load_trade(self.root, trade_id).plan, plan_id)
        # the plan page counts what came of it, and the trade page names it
        _, page = self.get(f"/plan/{urllib.parse.quote(plan_id)}")
        self.assertIn("Trades of this plan", page)
        self.assertIn(trade_id, page)
        _, trade = self.get(f"/trade/{urllib.parse.quote(trade_id)}")
        self.assertIn(f'href="/plan/{plan_id}"', trade)
        ServerCase.plan_id = plan_id

    def test_43_an_update_is_added_and_the_plan_is_edited(self):
        plan_id = ServerCase.plan_id
        self.post(f"/plan/{urllib.parse.quote(plan_id)}/update",
                  {"update": "gap up on Monday, plan holds"})
        k = store.load_plan(self.root, plan_id)
        self.assertIn("gap up on Monday", k.updates)
        self.assertIn(datetime.now().strftime("%d.%m.%Y"), k.updates)

        _, form = self.get(f"/plan/{urllib.parse.quote(plan_id)}/edit")
        token = self.form_token(form)
        self.assertIn("range formed", form)          # the analysis is in the form
        self.post(f"/plan/{urllib.parse.quote(plan_id)}/edit", {
            "token": token, "blocks": "1", "title": "weekly", "pair": "EURUSD",
            "narrative": "bearish", "from": "2026-08-31", "until": "2026-09-06",
            "idea_tf_1": "D1", "idea_text_1": "range formed",
            "have_idea-1": "shots/idea-01-01.png",
            "plan_text": "long from the nearest SNR, no shorts",
            "updates": k.updates, "review": "the plan held"})
        k = store.load_plan(self.root, plan_id)
        self.assertEqual(k.narrative, "bearish")
        self.assertEqual(k.review, "the plan held")
        self.assertIn("gap up on Monday", k.updates)
        # editing an unrelated field keeps the analysis screenshot on the disk
        self.assertEqual(k.analysis[0].images, ["shots/idea-01-01.png"])
        self.assertTrue(os.path.exists(os.path.join(
            store.plan_dir(self.root, plan_id), "shots", "idea-01-01.png")))

    def test_44_the_header_offers_a_plan_and_not_a_report(self):
        _, html = self.get("/")
        header = re.findall(r'<header.*?</header>', html, re.S)[0]
        self.assertIn('href="/plan/new"', header)
        self.assertNotIn("Build report", header)
        self.assertIn('href="/reports"', header)      # the tab is still there
        # and the form that builds a report lives on the Reports tab
        self.assertIn('action="/report/build"', self.get("/reports")[1])

    def test_45_a_plan_is_deleted_into_the_trash(self):
        plan_id = ServerCase.plan_id
        self.post(f"/plan/{urllib.parse.quote(plan_id)}/delete", {})
        self.assertFalse(os.path.exists(store.plan_dir(self.root, plan_id)))
        self.assertTrue(any(name.startswith("plan-" + plan_id)
                            for name in os.listdir(os.path.join(self.root, ".trash"))))
        # the trade keeps the id of a plan that is gone, and still opens
        code, html = self.get("/trade/" + urllib.parse.quote(
            [t.id for t in store.all_trades(self.root) if t.plan == plan_id][0]))
        self.assertEqual(code, 200)
        self.assertIn(plan_id, html)

    # --- v1.4.3 ---
    def open_trade(self, **over):
        _, html = self.get("/new")
        fields = {"token": self.form_token(html), "blocks": "1", "account": "broker",
                  "pair": "EURUSD", "direction": "long", "style": "swing",
                  "entry_tf": "H4", "risk": "1", "entry": "2026-08-29T14:30",
                  "idea_tf_1": "H4", "idea_text_1": "a plain idea"}
        fields.update(over)
        _, where = self.post("/new", fields)
        return self.landed(where)

    def refused(self, path, fields, code=400):
        data = urllib.parse.urlencode(fields, doseq=True).encode("utf-8")
        try:
            urllib.request.urlopen(urllib.request.Request(self.url(path), data=data))
            self.fail(f"{path} went through")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, code)
            e.close()

    def test_50_a_broken_record_is_named_and_the_rest_still_load(self):
        folder = store.trade_dir(self.root, "2026-01-05-01-eurusd")
        os.makedirs(folder)
        with open(os.path.join(folder, "trade.md"), "w") as f:
            f.write("---\nid: 2026-01-05-01-eurusd\naccount: broker\npair: EURUSD\n"
                    "direction: long\nstyle: swing\nrisk %: 1\nentry: 05.01.2026\n---\n")
        self.S.drop_cache()
        try:
            for path in ("/", "/stats", "/accounts", "/cards", "/plans"):
                code, html = self.get(path)
                self.assertEqual(code, 200, path)
                self.assertIn('<div class="notice">', html, path)
                self.assertIn("2026-01-05-01-eurusd/trade.md", html, path)
            self.assertIn("does not match format", self.get("/")[1])
        finally:
            import shutil
            shutil.rmtree(folder)
            self.S.drop_cache()
        self.assertNotIn('<div class="notice">', self.get("/")[1])

    def test_51_a_pair_is_one_pair_whatever_the_case(self):
        trade_id = self.open_trade(pair="eurusd")
        self.assertEqual(store.load_trade(self.root, trade_id).pair, "EURUSD")
        self.assertTrue(trade_id.endswith("-eurusd"))

    def test_52_the_exit_is_not_before_the_entry(self):
        trade_id = self.open_trade(entry="2026-08-29T14:30")
        q = urllib.parse.quote(trade_id)
        token = self.form_token(self.get(f"/close/{q}")[1])
        self.refused(f"/close/{q}", {"token": token, "result": "Win", "pnl": "10",
                                     "exit": "2026-08-28T10:00"})
        self.assertTrue(store.load_trade(self.root, trade_id).is_open)
        # the same day without an hour is not "before", whatever hour the entry has
        self.post(f"/close/{q}", {"token": token, "result": "Win", "pnl": "10",
                                  "exit": "2026-08-29T00:00"})
        self.assertFalse(store.load_trade(self.root, trade_id).is_open)

    def test_53_a_card_is_not_moved_onto_another(self):
        self.post("/card/save", {"date": "2026-07-01", "previous": "2026-07-01",
                                 "focus": "the first"})
        self.post("/card/save", {"date": "2026-07-02", "previous": "2026-07-02",
                                 "focus": "the second"})
        self.refused("/card/save", {"date": "2026-07-01", "previous": "2026-07-02",
                                    "focus": "the second, moved"})
        self.assertEqual(store.load_card(self.root, datetime(2026, 7, 1)).focus,
                         "the first")
        self.assertIsNotNone(store.load_card(self.root, datetime(2026, 7, 2)))

    def test_54_search_finds_a_word_in_an_idea(self):
        trade_id = self.open_trade(idea_text_1="liquidity swept above the range")
        code, html = self.get("/search?q=SWEPT+above")
        self.assertEqual(code, 200)
        self.assertIn(f'href="/trade/{urllib.parse.quote(trade_id, safe="")}"', html)
        self.assertIn("<mark>swept above</mark>", html)
        self.assertIn("Nothing carries that word", self.get("/search?q=zzzz")[1])

    def test_55_the_selection_is_exported_as_csv(self):
        trade_id = self.open_trade(pair="USDJPY", style="EMT")
        with urllib.request.urlopen(self.url("/export.csv?pair=USDJPY")) as r:
            self.assertIn("text/csv", r.headers["Content-Type"])
            self.assertIn("attachment", r.headers["Content-Disposition"])
            text = r.read().decode("utf-8")
        lines = text.strip().split("\n")
        self.assertTrue(lines[0].startswith("id,account,pair"))
        self.assertIn("balance at entry", lines[0])
        self.assertTrue(any(line.startswith(trade_id) for line in lines[1:]))
        self.assertTrue(all("USDJPY" in line for line in lines[1:]))

    def test_56_the_daily_limit_warns_on_the_front_page(self):
        self.post("/account/limit", {"id": "broker", "limit": "50"})
        self.assertEqual(store.all_accounts(self.root)["broker"].daily_loss_limit, 50)
        now = datetime.now().strftime("%Y-%m-%dT%H:%M")
        trade_id = self.open_trade(entry=now, risk="1")     # 1% of ~10 000 at risk
        _, html = self.get("/")
        tile = re.search(r'<div class="tile([^"]*)"><div class="name">Broker', html)
        self.assertIn("over", tile.group(1))
        self.assertIn("daily loss limit reached", html)
        self.assertIn("limit 50 $", html)
        self.post("/account/limit", {"id": "broker", "limit": ""})
        self.assertIsNone(store.all_accounts(self.root)["broker"].daily_loss_limit)
        self.assertNotIn("daily loss limit reached", self.get("/")[1])
        self.post(f"/trade/{urllib.parse.quote(trade_id)}/delete", {})

    def test_57_a_deleted_trade_is_restored_from_the_trash(self):
        trade_id = self.open_trade(idea_text_1="to be deleted and brought back")
        q = urllib.parse.quote(trade_id)
        self.post(f"/trade/{q}/delete", {})
        self.assertFalse(os.path.isdir(store.trade_dir(self.root, trade_id)))
        _, html = self.get("/accounts")
        name = re.search(r'name="name" value="(' + re.escape(trade_id) + r'-[0-9-]+)"',
                         html).group(1)
        self.post("/trash/restore", {"name": name})
        self.assertTrue(os.path.isdir(store.trade_dir(self.root, trade_id)))
        self.assertEqual(self.get(f"/trade/{q}")[0], 200)
        self.assertNotIn(name, self.get("/accounts")[1])

    def test_58_a_deleted_account_goes_to_the_trash_and_comes_back(self):
        self.post("/account/new", {"id": "spare", "name": "Spare", "start": "1",
                                   "currency": "eur"})
        self.assertIn("1 €", self.get("/accounts")[1])
        self.post("/account/delete", {"id": "spare"})
        self.assertNotIn("spare", store.all_accounts(self.root))
        # by id, not first of its kind: the trash of these tests is shared, and
        # a record deleted within the same second by an earlier test ties with it
        name = next(x[0] for x in store.trash_list(self.root)
                    if x[1] == "account" and x[2] == "spare")
        self.post("/trash/restore", {"name": name})
        self.assertEqual(store.all_accounts(self.root)["spare"].currency, "EUR")
        self.post("/account/delete", {"id": "spare"})

    def test_59_the_plan_page_says_whether_the_trades_followed_it(self):
        token = self.form_token(self.get("/plan/new")[1])
        _, where = self.post("/plan/new", {
            "token": token, "blocks": "1", "title": "bull week", "pair": "EURUSD",
            "narrative": "bullish", "from": "2026-08-24", "until": "2026-08-28",
            "plan_text": "buy the dips"})
        plan_id = self.landed(where)
        self.open_trade(plan=plan_id, direction="long", entry="2026-08-25T10:00")
        self.open_trade(plan=plan_id, direction="short", entry="2026-08-26T10:00")
        _, html = self.get(f"/plan/{urllib.parse.quote(plan_id)}")
        self.assertIn("with the narrative: 1 trade", html)
        self.assertIn("against it: 1 trade", html)

    def test_60_the_folder_follows_the_day_of_the_trade(self):
        trade_id = self.open_trade(entry="2026-06-10T09:00", pair="AUDUSD")
        self.assertTrue(trade_id.startswith("2026-06-10-"))
        q = urllib.parse.quote(trade_id)
        token = self.form_token(self.get(f"/edit/{q}")[1])
        _, where = self.post(f"/edit/{q}", {
            "token": token, "blocks": "1", "account": "broker", "pair": "AUDUSD",
            "direction": "long", "style": "swing", "entry_tf": "H4", "risk": "1",
            "entry": "2026-06-11T09:00", "idea_tf_1": "H4", "idea_text_1": "moved"})
        moved = self.landed(where)
        self.assertEqual(moved, "2026-06-11-01-audusd")
        self.assertFalse(os.path.isdir(store.trade_dir(self.root, trade_id)))
        self.assertEqual(store.load_trade(self.root, moved).id, moved)
        # a link with the old id in it says the trade is gone, not that it broke
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.get(f"/trade/{q}")
        self.assertEqual(e.exception.code, 404)
        e.exception.close()

    def test_61_the_streak_is_on_the_statistics_and_not_the_front_page(self):
        # the first rows of the list already show the run; the tile said it twice
        _, html = self.get("/")
        self.assertNotIn('<div class="name">streak</div>', html)
        _, html = self.get("/stats")
        self.assertIn("longest run of wins", html)

    # --- the weekly card ---
    def test_62_a_weekly_card_is_written_and_read_back(self):
        _, html = self.get("/week/2026-W35")
        self.assertIn("Weekly report card", html)
        self.assertIn("missed / underexploited opportunities", html)
        self.post("/week/save", {
            "week": "2026-W35", "previous": "2026-W35", "grade": "B", "pnl": "480",
            "trades": "4", "quality": "A", "progress": "3",
            "focus": "one setup a day", "process": "levels marked on Sunday",
            "learned": "waited for the retest", "errors": "sized up after a loss",
            "best": "GBPUSD long", "missed": "US100 on Thursday",
            "lesson": "the plan is written before the open",
            "assess_trade": ["EURUSD long", "", "XAU short", "", ""],
            "assess_grade": ["A", "", "C", "", ""]})
        k = store.load_week(self.root, "2026-W35")
        self.assertEqual((k.grade, k.pnl, k.trades, k.quality, k.progress),
                         ("B", 480.0, 4, "A", 3))
        self.assertEqual(k.lesson, "the plan is written before the open")
        # the empty rows of the paper table are not records
        self.assertEqual([(r.trade, r.grade) for r in k.assessment],
                         [("EURUSD long", "A"), ("XAU short", "C")])
        _, html = self.get("/week/2026-W35")
        self.assertIn("waited for the retest", html)   # the form came back filled
        self.assertIn('value="XAU short"', html)
        _, html = self.get("/cards")
        self.assertIn("24.08 - 30.08.2026", html)
        self.assertIn("the plan is written before the open", html)

    # --- the word the journal says after a form ---
    def test_72_a_saved_form_is_answered_in_the_middle_of_the_page(self):
        trade_id = self.open_trade(idea_text_1="a trade that says so")
        q = urllib.parse.quote(trade_id)
        _, where = self.post(f"/close/{q}", {
            "token": self.form_token(self.get(f"/close/{q}")[1]),
            "result": "Win", "pnl": "10", "exit": "2026-08-30T10:00"})
        self.assertIn("said=Trade%20closed", where)
        _, html = self.get(urllib.parse.urlparse(where).path + "?said=Trade+closed")
        self.assertIn('<div class="toast" role="status">Trade closed</div>', html)
        # and the address is left without it, so a reload says nothing
        self.assertIn('history.replaceState', html)
        self.assertNotIn("said", urllib.parse.urlparse(
            re.search(r'replaceState\(\{\}, "", "([^"]+)"', html).group(1)).query)
        self.assertNotIn('class="toast"', self.get(f"/trade/{q}")[1])

    def test_73_the_word_is_not_taken_for_a_filter(self):
        _, html = self.get("/?pair=EURUSD&said=Trade+opened")
        self.assertIn('class="toast"', html)
        # the filters and the links they build know nothing about it
        self.assertNotIn("said", re.search(r'<header.*?</header>', html, re.S).group(0))
        self.assertNotIn("said=", html.split('class="toast"')[1])

    def test_74_the_logo_leads_home(self):
        _, html = self.get("/stats")
        self.assertIn('<a href="/" class="logo"', html)

    # --- screenshots in the plan and in its updates ---
    def new_plan(self, **over):
        _, form = self.get("/plan/new")
        fields = {"token": self.form_token(form), "blocks": "1", "title": "shots",
                  "pair": "EURUSD", "narrative": "bullish", "from": "2026-08-31",
                  "until": "2026-09-06", "idea_tf_1": "D1",
                  "idea_text_1": "range formed", "plan_text": "long from the SNR"}
        fields.update(over)
        _, where = self.post("/plan/new", fields)
        return self.landed(where)

    def test_69_the_plan_text_carries_screenshots(self):
        _, form = self.get("/plan/new")
        token = self.form_token(form)
        shot = self.paste_shot(token, "plan")
        plan_id = self.new_plan(token=token, file_plan=shot["file"])
        k = store.load_plan(self.root, plan_id)
        self.assertIn("![](shots/plan-01.png)", k.plan)
        self.assertEqual(
            self.get(f"/plan-shot/{plan_id}/plan-01.png", as_text=False)[0], 200)
        q = urllib.parse.quote(plan_id)
        _, html = self.get(f"/plan/{q}")
        self.assertIn(f'<img src="/plan-shot/{plan_id}/plan-01.png"', html)
        # the picture is not typed into the text field, it hangs in its own zone
        _, form = self.get(f"/plan/{q}/edit")
        self.assertNotIn("![](shots/plan-01.png)", form)
        self.assertIn('name="have_plan" value="shots/plan-01.png"', form)

    def test_70_an_update_carries_a_screenshot_and_keeps_it(self):
        _, form = self.get("/plan/new")
        token = self.form_token(form)
        idea_shot = self.paste_shot(token, "idea-1")
        plan_id = self.new_plan(title="updates", token=token,
                                **{"file_idea-1": idea_shot["file"]})
        q = urllib.parse.quote(plan_id)
        _, html = self.get(f"/plan/{q}")
        token = self.form_token(html)
        shot = self.paste_shot(token, "update")
        self.post(f"/plan/{q}/update", {"token": token, "update": "level held",
                                        "file_update": shot["file"]})
        k = store.load_plan(self.root, plan_id)
        self.assertIn("level held", k.updates)
        self.assertIn("![](shots/update-01.png)", k.updates)
        _, html = self.get(f"/plan/{q}")
        self.assertIn(f'<img src="/plan-shot/{plan_id}/update-01.png"', html)
        # an update is added from a form that shows one zone, so the pictures
        # of the analysis have to be exactly where they were
        self.assertEqual(k.analysis[0].images, ["shots/idea-01-01.png"])
        self.assertEqual(
            self.get(f"/plan-shot/{plan_id}/idea-01-01.png", as_text=False)[0], 200)

        # a second update must not take the picture of the first one with it
        token = self.form_token(self.get(f"/plan/{q}")[1])
        shot = self.paste_shot(token, "update")
        self.post(f"/plan/{q}/update", {"token": token, "update": "stop moved",
                                        "file_update": shot["file"]})
        k = store.load_plan(self.root, plan_id)
        self.assertIn("![](shots/update-01.png)", k.updates)
        self.assertIn("![](shots/update-02.png)", k.updates)
        for name in ("update-01.png", "update-02.png", "idea-01-01.png"):
            self.assertEqual(
                self.get(f"/plan-shot/{plan_id}/{name}", as_text=False)[0], 200)

        # and editing the plan afterwards keeps both, in their own lines
        _, form = self.get(f"/plan/{q}/edit")
        self.assertIn('name="have_update" value="shots/update-01.png"', form)
        token = self.form_token(form)
        self.post(f"/plan/{q}/edit", {
            "token": token, "blocks": "1", "title": "updates", "pair": "EURUSD",
            "narrative": "bullish", "from": "2026-08-31", "until": "2026-09-06",
            "idea_tf_1": "D1", "idea_text_1": "range formed",
            "plan_text": "long from the SNR",
            "updates": store.load_plan(self.root, plan_id).updates,
            "have_update": ["shots/update-01.png", "shots/update-02.png"],
            "have_idea-1": ["shots/idea-01-01.png"]})
        k = store.load_plan(self.root, plan_id)
        self.assertEqual(k.updates.count("!["), 2)
        first = k.updates.index("![](shots/update-01.png)")
        self.assertLess(k.updates.index("stop moved"), first + 200)
        self.assertLess(k.updates.index("level held"), k.updates.index("stop moved"))
        for name in ("update-01.png", "update-02.png", "idea-01-01.png"):
            self.assertEqual(
                self.get(f"/plan-shot/{plan_id}/{name}", as_text=False)[0], 200)

    def test_71_a_removed_update_screenshot_leaves_the_plan(self):
        plan_id = self.new_plan(title="removing")
        q = urllib.parse.quote(plan_id)
        token = self.form_token(self.get(f"/plan/{q}")[1])
        shot = self.paste_shot(token, "update")
        self.post(f"/plan/{q}/update", {"token": token, "update": "one",
                                        "file_update": shot["file"]})
        form = self.get(f"/plan/{q}/edit")[1]
        # the cross takes the thumbnail out of the form, so nothing comes back
        self.post(f"/plan/{q}/edit", {
            "token": self.form_token(form), "blocks": "1", "title": "removing",
            "pair": "EURUSD", "narrative": "bullish", "from": "2026-08-31",
            "until": "2026-09-06", "idea_tf_1": "D1", "idea_text_1": "range formed",
            "plan_text": "long from the SNR",
            "updates": store.load_plan(self.root, plan_id).updates})
        k = store.load_plan(self.root, plan_id)
        self.assertNotIn("![", k.updates)
        self.assertIn("one", k.updates)

    def test_62a_both_cards_are_listed_on_the_cards_tab(self):
        """One tab, one folder, two tables: the days and the weeks apart."""
        _, html = self.get("/cards")
        self.assertIn("Daily report cards", html)
        self.assertIn("Weekly report cards", html)
        self.assertIn('href="/card/', html)
        self.assertIn('href="/week/2026-W35"', html)
        # a row is opened by clicking anywhere on it
        self.assertIn('<td class="cell"><a href="/week/2026-W35"', html)
        # and the header of the journal offers both cards by their names
        _, home = self.get("/")
        self.assertIn("+ DRC", home)
        self.assertIn("+ WRC", home)
        self.assertNotIn("+ Card", home)

    def test_62b_the_two_cards_share_the_cards_folder(self):
        names = sorted(os.listdir(os.path.join(self.root, "journal", "cards")))
        self.assertIn("2026-W35.md", names)
        self.assertTrue(any(re.match(r"\d{4}-\d{2}-\d{2}\.md$", n) for n in names))
        self.assertFalse(os.path.isdir(os.path.join(self.root, "journal", "weeks")))

    def test_63_a_weekly_card_with_empty_fields_saves_and_opens(self):
        self.post("/week/save", {"week": "2026-W34", "previous": "2026-W34",
                                 "grade": "A", "pnl": "", "trades": "",
                                 "quality": "", "progress": "", "focus": "pennies"})
        code, html = self.get("/week/2026-W34")
        self.assertEqual(code, 200)
        self.assertIn("pennies", html)
        self.assertRegex(html, r'name="quality"[^>]*value=""')
        self.assertRegex(html, r'name="trades"[^>]*value=""')

    def test_64_changing_the_week_moves_the_card(self):
        self.post("/week/save", {"week": "2026-W33", "previous": "2026-W34",
                                 "grade": "A", "focus": "pennies"})
        self.assertIsNone(store.load_week(self.root, "2026-W34"))
        self.assertIsNotNone(store.load_week(self.root, "2026-W33"))

    def test_65_a_weekly_card_is_not_moved_onto_another(self):
        self.post("/week/save", {"week": "2026-W31", "previous": "2026-W31",
                                 "focus": "the first"})
        self.post("/week/save", {"week": "2026-W32", "previous": "2026-W32",
                                 "focus": "the second"})
        self.refused("/week/save", {"week": "2026-W31", "previous": "2026-W32",
                                    "focus": "the second, moved"})
        self.assertEqual(store.load_week(self.root, "2026-W31").focus, "the first")
        self.assertIsNotNone(store.load_week(self.root, "2026-W32"))

    def test_66_a_weekly_card_is_deleted_into_the_trash_and_comes_back(self):
        self.post("/week/2026-W32/delete", {})
        self.assertIsNone(store.load_week(self.root, "2026-W32"))
        name = next(x[0] for x in store.trash_list(self.root)
                    if x[1] == "week" and x[2] == "2026-W32")
        self.post("/trash/restore", {"name": name})
        self.assertEqual(store.load_week(self.root, "2026-W32").focus, "the second")

    def test_67_a_week_that_does_not_exist_is_a_404(self):
        for bad in ("2026-W99", "2025-W53", "week"):
            with self.assertRaises(urllib.error.HTTPError) as e:
                self.get(f"/week/{bad}")
            self.assertEqual(e.exception.code, 404, bad)
            e.exception.close()

    def test_68_search_finds_a_word_in_a_weekly_card(self):
        code, html = self.get("/search?q=US100+on+Thursday")
        self.assertEqual(code, 200)
        self.assertIn('href="/week/2026-W35"', html)
        self.assertIn("<mark>US100 on Thursday</mark>", html)

    def test_68a_search_finds_a_trade_in_a_daily_assessment(self):
        code, html = self.get("/search?q=XAU+short")
        self.assertEqual(code, 200)
        self.assertIn('href="/card/2026-08-30"', html)

    def test_69_the_ev_stands_next_to_every_winrate_on_the_front_page(self):
        from plainbook import stats
        code, html = self.get("/")
        self.assertEqual(code, 200)
        j = self.S.journal()
        s = stats.summary(j, j.trades)
        self.assertTrue(s.decided)
        # the overall tile: the winrate, then the EV of the same trades
        self.assertIn(f'{s.wr:.1f}% <span class="ev', html)
        self.assertIn(f'<span class="muted">EV</span> {s.average_r:+.2f} R</span>',
                      html)
        # the total row of a period carries it after its WR
        self.assertRegex(html, r'WR \d+%<span class="dates">EV [+-]\d+\.\d\d</span>')

    def test_70_the_ev_is_in_the_statistics_and_the_reports_for_every_pair(self):
        from plainbook import stats
        # a pair never traded before: its row and its EV come with its first
        # closed trade, nothing has to be added anywhere for it
        _, html = self.get("/new")
        _, where = self.post("/new", {
            "token": self.form_token(html), "blocks": "1", "account": "broker",
            "pair": "NZDCAD", "direction": "short", "style": "swing",
            "entry_tf": "H4", "risk": "1", "entry": "2026-08-20T10:00",
            "idea_tf_1": "H4", "idea_text_1": "a pair traded once"})
        q = urllib.parse.quote(self.landed(where))
        _, html = self.get(f"/close/{q}")
        self.post(f"/close/{q}", {"token": self.form_token(html), "result": "BE",
                                  "pnl": "-3", "exit": "2026-08-21",
                                  "conclusions": "flat, minus the commission"})
        j = self.S.journal()
        rows = dict(stats.by_field(j, j.trades, lambda t: t.pair))
        self.assertIn("NZDCAD", rows)
        code, html = self.get("/stats")
        self.assertEqual(code, 200)
        self.assertIn('<th class="num">EV</th>', html)
        self.assertNotIn("average R", html)
        for pair, s in rows.items():
            row = re.search(rf'<tr><td>{re.escape(self.S.H.pair(pair))}</td>(.*?)</tr>',
                            html)
            self.assertTrue(row, pair)
            self.assertIn(f'<td class="num">{s.average_r:+.2f}</td>', row.group(1), pair)
        # the same column in a report, in the summary and in every slice
        self.post("/report/build", {"what": "month", "period_month": "2026-08"})
        code, html = self.get("/report/2026-08")
        self.assertEqual(code, 200)
        self.assertIn("EV (average R, BE counted)", html)
        self.assertEqual(html.count('<th class="num">EV</th>'), 6)
        self.assertIn(f'<td class="num">{rows["NZDCAD"].average_r:+.2f}</td>', html)

    def test_71_the_assessment_has_the_result_column_of_the_paper(self):
        j = self.S.journal()
        t = next(x for x in j.trades if not x.is_open and x.closed)
        day = t.closed.strftime("%Y-%m-%d")
        closed = self.S.day_trades(j, t.closed)
        labels = self.S.trade_labels(closed)
        # the same pair, direction and day on two accounts: told apart by the
        # account, or the result would be filled in from the wrong trade
        self.assertEqual(len(set(labels.values())), len(closed))
        label = labels[t.id]
        expected = self.S.outcomes(j, closed)[label]
        self.assertTrue(expected.startswith(t.result))
        _, html = self.get(f"/card/{day}")
        self.assertIn(f'<option value="{label}">', html)
        self.assertIn('name="assess_result"', html)
        # graded without a result, as a card written before the column was
        self.post("/card/save", {"date": day, "previous": day, "grade": "B",
                                 "assess_trade": [label, "XAU short"],
                                 "assess_grade": ["A", "C"],
                                 "assess_result": ["", "by hand"]})
        k = store.load_card(self.root, datetime.strptime(day, "%Y-%m-%d"))
        self.assertEqual([(r.trade, r.result) for r in k.assessment],
                         [(label, ""), ("XAU short", "by hand")])
        # the form offers the journal's result for the trade it knows, and
        # leaves the one typed by hand alone
        _, html = self.get(f"/card/{day}")
        self.assertIn(f'name="assess_result" autocomplete="off" '
                      f'style="width:100%" value="{expected}"', html)
        self.assertIn('value="by hand"', html)
        # a result without a trade is not a row
        self.post("/card/save", {"date": day, "previous": day, "grade": "B",
                                 "assess_trade": [label, ""],
                                 "assess_grade": ["A", ""],
                                 "assess_result": [expected, "orphan"]})
        k = store.load_card(self.root, datetime.strptime(day, "%Y-%m-%d"))
        self.assertEqual([(r.trade, r.grade, r.result) for r in k.assessment],
                         [(label, "A", expected)])

    def test_72_a_refused_edit_leaves_the_folder_where_it_was(self):
        """The record is checked before its folder is renamed: an entry moved
        past the exit is refused, and the trade still opens under its id."""
        t = next(x for x in self.S.journal(True).trades if not x.is_open)
        tid = t.id
        q = urllib.parse.quote(tid)
        _, html = self.get(f"/edit/{q}")
        # any risk figure is a risk figure: 0.81% is a trade, not a typo
        self.assertIn('name="risk" step="any"', html)
        fields = {"token": self.form_token(html), "blocks": "1",
                  "account": t.account, "pair": "AUDNZD", "direction": t.direction,
                  "style": t.style, "entry_tf": t.entry_tf, "risk": f"{t.risk:g}",
                  "entry": "2027-01-05T10:00", "closed": "1", "result": t.result,
                  "pnl": f"{t.pnl:g}", "exit": t.closed.strftime("%Y-%m-%dT%H:%M"),
                  "conclusions": "kept", "idea_tf_1": "H4", "idea_text_1": "kept"}
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.post(f"/edit/{q}", fields)
        self.assertEqual(e.exception.code, 400)
        e.exception.close()
        self.assertTrue(os.path.isdir(store.trade_dir(self.root, tid)))
        self.assertEqual(store.load_trade(self.root, tid).pair, t.pair)
        self.assertEqual(self.get(f"/trade/{q}")[0], 200)
        # a risk left empty is refused with a word, not a traceback
        fields.update(entry=t.opened.strftime("%Y-%m-%dT%H:%M"), risk="")
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.post(f"/edit/{q}", fields)
        self.assertIn("risk is missing", e.exception.read().decode())
        e.exception.close()
        self.assertEqual(store.load_trade(self.root, tid).risk, t.risk)

    def test_73_the_risk_follows_the_account_and_the_period_tile_the_exit(self):
        j = self.S.journal(True)
        first = next(a for a in sorted(j.accounts) if not j.accounts[a].archived)
        last = {t.account: t.risk for t in j.trades}
        _, html = self.get("/new")
        self.assertIn(f'value="{last[first]:g}" required>', html)
        self.assertIn('data-last-risk="', html)
        self.assertIn("follow_account('account', 'risk')", html)
        # a trade opened and closed now, said to be a Win that lost money
        now = datetime.now()
        _, where = self.post("/new", {
            "token": self.form_token(html), "blocks": "1", "account": first,
            "pair": "EURUSD", "direction": "long", "style": "swing",
            "entry_tf": "H4", "risk": "0.7", "entry": now.strftime("%Y-%m-%dT%H:%M"),
            "idea_tf_1": "H4", "idea_text_1": "closed within the hour"})
        tid = self.landed(where)
        q = urllib.parse.quote(tid)
        _, html = self.get(f"/close/{q}")
        self.post(f"/close/{q}", {"token": self.form_token(html), "result": "Win",
                                  "pnl": "-40", "exit": now.strftime("%Y-%m-%dT%H:%M"),
                                  "conclusions": "a slip of the hand"})
        # the next new trade on that account starts at the risk this one had
        _, html = self.get("/new")
        self.assertIn('value="0.7" required>', html)
        # the disagreement is said on the trade page, the record is kept
        _, html = self.get(f"/trade/{q}")
        self.assertIn('<div class="notice"><b>Win with a PnL of', html)
        self.assertEqual(store.load_trade(self.root, tid).result, "Win")
        # the period tile counts what closed this week, this trade among it
        j = self.S.journal(True)
        n = sum(1 for t in j.trades if not t.is_open and t.closed
                and stats.week(t.closed) == stats.week(now))
        _, home = self.get("/")
        self.assertIn(f"{n} closed", home)


if __name__ == "__main__":
    unittest.main()
