#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End to end: open a trade, paste a screenshot, close it, edit it."""
import importlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import stats, store
from plainbook.model import Account, Playbook, Setup, Rule, Trade

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
        self.assertIn("<h2>R distribution</h2>", html)

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
        # the tab shows its pictures once something has closed, so give it one
        _, html = self.get("/new")
        _, where = self.post("/new", {
            "token": self.form_token(html), "blocks": "1", "account": "broker",
            "pair": "EURUSD", "direction": "long", "style": "swing",
            "entry_tf": "H4", "risk": "1", "entry": "2026-08-18T10:00"})
        tid = self.landed(where)
        _, html = self.get(f"/close/{urllib.parse.quote(tid)}")
        self.post(f"/close/{urllib.parse.quote(tid)}", {
            "token": self.form_token(html), "result": "BE", "pnl": "0",
            "exit": "2026-08-19", "conclusions": ""})
        code, html = self.get("/stats")
        self.assertEqual(code, 200)
        card = re.search(r'<h2>Equity</h2>.*?</p>', html, re.S).group(0)
        self.assertIn("<h3>Broker</h3>", card)
        self.assertNotIn("Legacy", card)                 # archived: no curve, no switch
        self.assertIn("Archived accounts are not drawn", card)
        # picked by hand through the filter, it is shown again, with its curve
        store.save_trade(self.root, Trade(
            id="2026-08-02-01-audusd", account="legacy", pair="AUDUSD",
            direction="long", style="swing", risk=1.0,
            opened=datetime(2026, 8, 2), closed=datetime(2026, 8, 3),
            result="Win", pnl=50))
        self.S.drop_cache()
        try:
            _, html = self.get("/stats?account=legacy")
            card = re.search(r'<h2>Equity</h2>.*?</p>', html, re.S).group(0)
            self.assertIn('class="current" href="/stats?account=legacy">Legacy</a>', card)
            self.assertIn("<h3>Legacy</h3>", card)
            self.assertIn("<svg", card)
        finally:
            shutil.rmtree(store.trade_dir(self.root, "2026-08-02-01-audusd"))
            self.S.drop_cache()

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
        rings = re.search(r'<h2>R distribution</h2>.*?</div></div>\s*'
                          r'<p class="caption">', html, re.S).group(0)
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

    def test_36a_an_open_trade_is_copied_from_its_own_form(self):
        """The copy forgotten at the entry: the block stands in the edit form
        of an open trade, an account that holds the position already is
        named and not offered, and a closed trade has no block."""
        origin = self.open_trade(entry="2026-08-30T12:00", pair="AUDUSD",
                                 idea_text_1="the copy will carry this")
        q = urllib.parse.quote(origin)
        _, form = self.get(f"/edit/{q}")
        self.assertIn("Duplicate on other accounts", form)
        self.assertIn('name="dup" value="prop-100k"', form)
        token = self.form_token(form)
        shot = self.paste_shot(token, "idea-1")
        before = {t.id for t in store.all_trades(self.root)}
        _, where = self.post(f"/edit/{q}", {
            "token": token, "blocks": "1", "account": "broker", "pair": "AUDUSD",
            "direction": "long", "style": "swing", "entry_tf": "H4", "risk": "1",
            "entry": "2026-08-30T12:00", "idea_tf_1": "H4",
            "idea_text_1": "the copy will carry this", "file_idea-1": shot["file"],
            "dup": ["prop-100k", "broker"], "dup_risk_prop-100k": "0.5"})
        self.assertIn("a%20copy%20on%20prop-100k", where)
        fresh = [t for t in store.all_trades(self.root) if t.id not in before]
        self.assertEqual([t.account for t in fresh], ["prop-100k"])
        twin = fresh[0]
        self.assertEqual((twin.pair, twin.risk, twin.opened),
                         ("AUDUSD", 0.5, datetime(2026, 8, 30, 12, 0)))
        self.assertEqual(twin.idea[0].text, "the copy will carry this")
        self.assertEqual(twin.idea[0].images, ["shots/idea-01-01.png"])
        self.assertTrue(os.path.exists(os.path.join(
            store.shots_dir(self.root, twin.id), "idea-01-01.png")))
        # the account that holds it now is named, not offered
        _, form = self.get(f"/edit/{q}")
        self.assertIn("already holds this position", form)
        self.assertNotIn('name="dup" value="prop-100k"', form)
        self.assertIn('name="dup" value="prop-50k"', form)
        # ticking it again writes nothing
        before = len(store.all_trades(self.root))
        self.post(f"/edit/{q}", {
            "token": self.form_token(form), "blocks": "1", "account": "broker",
            "pair": "AUDUSD", "direction": "long", "style": "swing",
            "entry_tf": "H4", "risk": "1", "entry": "2026-08-30T12:00",
            "idea_tf_1": "H4", "idea_text_1": "the copy will carry this",
            "have_idea-1": "shots/idea-01-01.png", "dup": "prop-100k"})
        self.assertEqual(len(store.all_trades(self.root)), before)
        # a closed trade offers no copy and writes none when asked
        _, form = self.get(f"/close/{q}")
        self.post(f"/close/{q}", {"token": self.form_token(form), "result": "Win",
                                  "pnl": "40", "exit": "2026-08-31T10:00",
                                  "conclusions": ""})
        _, form = self.get(f"/edit/{q}")
        self.assertNotIn("Duplicate on other accounts", form)
        self.post(f"/edit/{q}", {
            "token": self.form_token(form), "blocks": "1", "account": "broker",
            "pair": "AUDUSD", "direction": "long", "style": "swing",
            "entry_tf": "H4", "risk": "1", "entry": "2026-08-30T12:00",
            "idea_tf_1": "H4", "idea_text_1": "the copy will carry this",
            "have_idea-1": "shots/idea-01-01.png", "closed": "1",
            "result": "Win", "pnl": "40", "exit": "2026-08-31T10:00",
            "conclusions": "", "dup": "prop-50k"})
        self.assertEqual(len(store.all_trades(self.root)), before)

    def test_36b_the_front_page_says_which_version_this_is(self):
        from plainbook import __version__
        _, html = self.get("/")
        self.assertIn(f'<span class="ver">{__version__}</span>', html)

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
                        "best / worst trade", "Process", "R distribution",
                        "deepest fall from a high", "Trade by trade", "mistakes"):
            self.assertIn(heading, html, heading)
        self.assertIn("July 2026", html)                 # the period compared with
        self.assertIn("<svg", html)                      # the rings are drawn
        self.assertIn('class="tape"', html)              # and the tape of the trades
        # the figures lead: the strip of tiles stands before the first table
        self.assertLess(html.index('class="tiles report"'), html.index("<table"))
        # the tables of the appendix are dealt into two columns, the way the
        # Statistics tab deals its own
        appendix = html[html.rindex('<div class="twin"><div>'):]
        for heading in ("<h2>Accounts</h2>", "<h2>By pair</h2>", "<h2>By style</h2>"):
            self.assertIn(heading, appendix, heading)
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

    def test_44a_the_playbooks_tab_asks_until_a_playbook_is_written(self):
        _, html = self.get("/playbooks")
        header = re.findall(r'<header.*?</header>', html, re.S)[0]
        self.assertIn('class="current attention"', header)
        self.assertIn("No playbooks yet", html)
        store.save_playbook(self.root, Playbook(
            id="pull", name="Pullback", styles=["swing"], version="1.0",
            block=40, intro="Trend only.",
            setups=[Setup(name="A: reaction", text="The first reaction is in.",
                          rules=[Rule(1, "Level on D1"), Rule(2, "Target 1R away")])],
            filters=[Rule(3, "An hour to the news")],
            limits=[("risk", "1 %")]))
        try:
            _, html = self.get("/playbooks")
            header = re.findall(r'<header.*?</header>', html, re.S)[0]
            self.assertNotIn("attention", header)
            self.assertIn('href="/playbook/pull"', html)
            self.assertIn("0 / 40", html)
            self.assertEqual(self.S.block_bar(Playbook(id="x", block=40), 45).count("block 2: <b>5 / 40</b>"), 1)
            self.assertIn("next review at <b>80</b>", self.S.block_bar(Playbook(id="x", block=40), 45))
            self.assertIn("block 1: <b>40 / 40</b>", self.S.block_bar(Playbook(id="x", block=40), 40))
            self.assertNotIn("in all", self.S.block_bar(Playbook(id="x", block=40), 40))
            status, html = self.get("/playbook/pull")
            self.assertEqual(status, 200)
            for piece in ('class="pb-name">Pullback', "A: reaction",
                          "Target 1R away", "An hour to the news",
                          '<span class="n">3</span>', 'class="limits"'):
                self.assertIn(piece, html)
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.get("/playbook/nope")
            self.assertEqual(caught.exception.code, 404)
        finally:
            shutil.rmtree(store.playbook_dir(self.root, "pull"))

    def test_44b_a_playbook_is_written_revised_by_version_and_deleted(self):
        _, html = self.get("/playbook/new")
        self.assertIn('name="setup_rule_1"', html)
        fields = {"name": "Pullback", "status": "experiment", "version": "1.0",
                  "since": "2026-08-15", "block": "40", "styles": "swing",
                  "intro": "Trend only.", "setups": "2",
                  "setup_name_1": "A: reaction", "setup_about_1": "The first reaction.",
                  "setup_rule_1": ["Level on D1", "- [ ] Target 2R away", "", ""],
                  "setup_rule_1_detail": ["The level is a fractal on D1", "", "",
                                          "Words left empty: the rule is the words"],
                  "setup_name_2": "", "setup_about_2": "", "setup_rule_2": [""],
                  "filter": ["An hour to the news", "No other\nposition open"],
                  "limit_kind": ["risk", "max per week", "other", "max hold", "other"],
                  "limit_name": ["", "", "trades per move", "", "no name"],
                  "limit_value": ["1", "3", "5", "", ""],
                  "notes": "## Math\n\nBreak-even at 33%."}
        _, where = self.post("/playbook/new", fields)
        self.assertEqual(self.landed(where), "pullback")
        p = store.load_playbook(self.root, "pullback")
        self.assertEqual([r.text for r in p.rules],
                         ["Level on D1", "Target 2R away",
                          "Words left empty: the rule is the words",
                          "An hour to the news", "No other position open"])
        self.assertEqual(p.rules[0].detail, "The level is a fractal on D1")
        self.assertEqual(len(p.setups), 1)          # the empty block is dropped
        self.assertEqual(p.limits, [("risk", "1"), ("max per week", "3"),
                                    ("trades per move", "5")])
        self.assertEqual(p.sections, [("Math", "Break-even at 33%.")])
        self.assertEqual(p.block, 40)
        _, html = self.get("/playbook/pullback")
        self.assertIn("Target 2R away", html)
        self.assertIn('href="/playbook/pullback/edit"', html)
        # the same name again gets its own folder
        self.post("/playbook/new", dict(fields, name="Pullback"))
        self.assertTrue(os.path.isdir(store.playbook_dir(self.root, "pullback-2")))
        shutil.rmtree(store.playbook_dir(self.root, "pullback-2"))

        # with no trade under the rules yet they are a draft: edited freely
        _, html = self.get("/playbook/pullback/edit")
        self.assertIn('value="Pullback"', html)
        self.assertIn("Target 2R away", html)
        self.assertIn('<option value="risk" selected>', html)
        self.assertIn('name="limit_name" value="trades per move"', html)
        _, html = self.get("/playbook/pullback")
        self.assertIn("risk per trade<b>1 %</b>", html)
        self.assertIn("trades per move<b>5</b>", html)
        draft = dict(fields, setups="1", setup_rule_1=["Level on D1", "Target 2R away, or none"])
        self.post("/playbook/pullback/edit", draft)
        self.assertEqual(store.load_playbook(self.root, "pullback").rules[1].text,
                         "Target 2R away, or none")
        self.assertEqual(store.playbook_versions(self.root, "pullback"), [])
        self.post("/playbook/pullback/edit", fields)

        # a trade tied to the playbook without a checklist holds nothing
        loose = Trade(id="2031-01-05-01-eurusd", account="broker", pair="EURUSD",
                      direction="long", style="swing", opened=datetime(2031, 1, 5),
                      playbook="pullback", playbook_version="1.0")
        store.save_trade(self.root, loose)
        self.S.drop_cache()
        self.post("/playbook/pullback/edit", draft)
        self.assertEqual(store.playbook_versions(self.root, "pullback"), [])
        self.post("/playbook/pullback/edit", fields)
        _, html = self.get(f"/trade/{loose.id}")
        self.assertIn("rules not ticked", html)
        shutil.rmtree(store.trade_dir(self.root, loose.id))

        # once a trade was ticked against the number, rules rewritten under
        # the same number are refused with the form back
        held = Trade(id="2031-01-06-01-eurusd", account="broker", pair="EURUSD",
                     direction="long", style="swing", opened=datetime(2031, 1, 6),
                     playbook="pullback", playbook_version="1.0", setup="A: reaction",
                     deviations=[2])
        store.save_trade(self.root, held)
        self.S.drop_cache()
        _, html = self.get("/playbook/pullback")
        self.assertIn("1 / 40", html)                 # the trade counts in the block
        self.assertIn(f'href="/trade/{held.id}"', html)
        _, html = self.get(f"/trade/{held.id}")
        self.assertIn('href="/playbook/pullback"', html)
        self.assertIn("rules not met: 2", html)
        changed = dict(fields, setups="1", setup_rule_1=["Level on D1", "Target 3R away"])
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/playbook/pullback/edit", changed)
        self.assertEqual(caught.exception.code, 400)
        html = caught.exception.read().decode("utf-8")
        self.assertIn('class="notice"', html)
        self.assertIn("Target 3R away", html)         # what was typed is kept
        self.assertEqual([r.text for r in store.load_playbook(self.root, "pullback").rules][1],
                         "Target 2R away")
        self.assertIn("The level is a fractal on D1", html)
        # with a new number the old rules are kept under versions/
        self.post("/playbook/pullback/edit", dict(changed, version="1.1"))
        p = store.load_playbook(self.root, "pullback")
        self.assertEqual(p.version, "1.1")
        self.assertEqual(p.rules[1].text, "Target 3R away")
        self.assertEqual(store.playbook_versions(self.root, "pullback"), ["1.0"])
        old = store.load_playbook_version(self.root, "pullback", "1.0")
        self.assertEqual(old.rules[1].text, "Target 2R away")
        _, html = self.get("/playbook/pullback")
        self.assertIn('href="/playbook/pullback/version/1.0"', html)
        _, html = self.get("/playbook/pullback/version/1.0")
        self.assertIn("Target 2R away", html)
        # the search looks into the playbook too
        _, html = self.get("/search?q=Target+3R")
        self.assertIn('href="/playbook/pullback"', html)
        # the intro edited under the same number is fine: the rules did not move
        self.post("/playbook/pullback/edit", dict(changed, version="1.1", intro="Trend, only."))
        self.assertEqual(store.load_playbook(self.root, "pullback").intro, "Trend, only.")
        self.assertEqual(store.playbook_versions(self.root, "pullback"), ["1.0"])

        shutil.rmtree(store.trade_dir(self.root, held.id))
        self.S.drop_cache()

        # a review is added from the page, dated, with a screenshot, and an
        # edit of the playbook afterwards keeps it
        _, html = self.get("/playbook/pullback")
        self.assertIn('action="/playbook/pullback/review"', html)
        token = self.form_token(html)
        shot = self.paste_shot(token, "review")
        self.post("/playbook/pullback/review",
                  {"token": token, "review": "Block one: the target rule leaked.",
                   "file_review": shot["file"]})
        p = store.load_playbook(self.root, "pullback")
        self.assertIn("**", p.review)
        self.assertIn("Block one", p.review)
        self.assertIn("![](shots/review-01.png)", p.review)
        _, html = self.get("/playbook/pullback")
        self.assertIn("Block one", html)
        self.assertIn('src="/playbook-shot/pullback/review-01.png"', html)
        self.assertEqual(self.get("/playbook-shot/pullback/review-01.png", as_text=False)[1], PNG)
        self.post("/playbook/pullback/edit", dict(changed, version="1.1", intro="Kept."))
        self.assertIn("Block one", store.load_playbook(self.root, "pullback").review)

        self.post("/playbook/pullback/delete", {})
        self.assertFalse(os.path.exists(store.playbook_dir(self.root, "pullback")))
        trashed = [name for name in os.listdir(os.path.join(self.root, ".trash"))
                   if name.startswith("playbook-pullback")]
        self.assertEqual(len(trashed), 1)
        # the trash knows what it holds, and restores it to the playbooks
        self.assertIn(("playbook", "pullback"),
                      [(kind, rid) for _, kind, rid, _ in store.trash_list(self.root)])
        self.assertEqual(store.restore(self.root, trashed[0]), ("playbook", "pullback"))
        self.assertTrue(os.path.isfile(os.path.join(store.playbook_dir(self.root, "pullback"),
                                                    "playbook.md")))
        self.post("/playbook/pullback/delete", {})

    def test_44c_a_trade_is_ticked_against_a_playbook(self):
        store.save_playbook(self.root, Playbook(
            id="pull", name="Pullback", styles=["swing"], version="1.0",
            setups=[Setup(name="A", rules=[Rule(1, "Level on D1", "A fractal level"),
                                           Rule(2, "Target 2R away")]),
                    Setup(name="B", rules=[Rule(3, "Trend on D1")])],
            filters=[Rule(4, "An hour to the news")],
            management=[Rule(5, "Stop never moved against"), Rule(6, "Closed by Friday")]))
        try:
            _, html = self.get("/new")
            self.assertIn('name="playbook"', html)
            self.assertIn('data-playbook="pull"', html)
            self.assertIn('id="met-pull-4"', html)
            self.assertNotIn('class="frame"', html)          # no limits, no frame
            book = store.load_playbook(self.root, "pull")
            book.limits = [("risk", "1"), ("open at once", "1")]
            book.block = 2
            store.save_playbook(self.root, book)
            _, html = self.get("/new")
            self.assertIn('open now <b>0</b> of 1', html)
            self.assertIn('data-risk="1"', html)
            # ticked: rules 1 and 4, so 2 is the deviation; setup B is not held to
            trade_id = self.open_trade(playbook="pull", setup_pull="A",
                                       met_pull=["1", "4"], ticked="1",
                                       why_pull_2="target 1.6R, took it anyway",
                                       why_pull_1="ignored: the box is ticked")
            t = store.load_trade(self.root, trade_id)
            self.assertEqual((t.playbook, t.playbook_version, t.setup, t.deviations),
                             ("pull", "1.0", "A", [2]))
            self.assertEqual(t.reasons, {2: "target 1.6R, took it anyway"})
            # the CSV carries the playbook columns in line with its header
            import csv as _csv
            rows = list(_csv.reader(io.StringIO(self.get("/export.csv")[1])))
            head, mine = rows[0], next(r for r in rows[1:] if r[0] == trade_id)
            self.assertEqual(len(head), len(mine))
            self.assertEqual(mine[head.index("playbook")], "pull")
            self.assertEqual(mine[head.index("deviations")], "2")
            self.assertEqual(mine[head.index("reasons")], "2: target 1.6R, took it anyway")
            self.assertEqual(mine[head.index("R")], "")           # still open
            _, html = self.get(f"/trade/{trade_id}")
            self.assertIn('class="rules ticked"', html)
            self.assertIn('<li class="no"><span class="n">2</span>', html)
            self.assertIn('<li class="ok"><span class="n">4</span>', html)
            self.assertIn('<span class="reason">target 1.6R, took it anyway</span>', html)
            self.assertNotIn("Trend on D1", html)
            _, html = self.get(f"/edit/{trade_id}")
            self.assertIn('name="why_pull_2" value="target 1.6R, took it anyway"', html)
            self.assertIn('name="why_pull_1" value="" placeholder="why not: the fact, not the verdict" hidden', html)
            # the management rules stand as a plain list while it is open
            _, html = self.get(f"/trade/{trade_id}")
            self.assertIn("Ticked when the trade is closed", html)
            self.assertNotIn('id="met-pull-5"', html)
            self.assertNotIn('name="held_pull"', html)
            # the edit form draws the boxes as they were ticked
            _, html = self.get(f"/edit/{trade_id}")
            self.assertIn('id="met-pull-1" name="met_pull" value="1" checked', html)
            self.assertIn('id="met-pull-2" name="met_pull" value="2">', html)
            # a setup the playbook does not have is refused, a nameless playbook too
            self.refused("/new", {"token": self.form_token(self.get("/new")[1]), "blocks": "1",
                                  "account": "broker", "pair": "EURUSD", "direction": "long",
                                  "style": "swing", "risk": "1", "entry": "2026-08-29T15:00",
                                  "playbook": "pull", "setup_pull": "Z"})
            self.refused("/playbook/new", {"token": "", "name": "  ", "version": "1.0",
                                           "status": "active"})
            self.refused("/playbook/new", {"token": "", "name": "Two", "version": "1.0",
                                           "status": "active", "setups": "2",
                                           "setup_name_1": "A", "setup_rule_1": ["one"],
                                           "setup_name_2": "", "setup_rule_2": ["two"]})
            # a trade with no box ticked at all records every rule as not met
            bare = self.open_trade(playbook="pull", setup_pull="B", entry="2026-08-29T15:00")
            self.assertEqual(store.load_trade(self.root, bare).deviations, [3, 4])
            # a trade tied later, never ticked, stays so when edited elsewhere
            loose = store.load_trade(self.root, bare)
            loose.deviations = None
            store.save_trade(self.root, loose)
            self.S.drop_cache()
            _, html = self.get(f"/trade/{bare}")
            self.assertIn("not ticked", html)
            _, html = self.get(f"/edit/{bare}")
            token = self.form_token(html)
            fields = {"token": token, "blocks": "1", "account": "broker", "pair": "EURUSD",
                      "direction": "long", "style": "swing", "entry_tf": "H4", "risk": "1",
                      "entry": "2026-08-29T15:00", "idea_tf_1": "H4", "idea_text_1": "edited",
                      "playbook": "pull", "setup_pull": "B", "ticked": "0"}
            self.post(f"/edit/{bare}", fields)
            self.assertIsNone(store.load_trade(self.root, bare).deviations)
            self.post(f"/edit/{bare}", dict(fields, ticked="1", met_pull=["3"]))
            self.assertEqual(store.load_trade(self.root, bare).deviations, [4])
            # and the playbook now holds its version: the rules ask for a number
            self.S.drop_cache()
            _, html = self.get("/playbook/pull")
            self.assertIn(f'href="/trade/{trade_id}"', html)
            # two open trades are past the limit, and the frame says so in red
            _, html = self.get("/new")
            self.assertIn('<span class="over">open now <b>2</b> of 1</span>', html)
            # two trades make a full block: the tab asks, the page says so, and
            # a review written on the page settles it
            _, html = self.get("/")
            self.assertIn('href="/playbooks" class="attention"', html)
            _, html = self.get("/playbook/pull")
            self.assertIn("block 1 is complete", html)
            self.assertIn("review due", self.get("/playbooks")[1])
            token = self.form_token(html)
            self.post("/playbook/pull/review", {"token": token, "review": "Block one: fine."})
            self.S.drop_cache()
            _, html = self.get("/")
            self.assertNotIn("attention", re.findall(r'<header.*?</header>', html, re.S)[0])
            # the statistics put the playbooks first, with the setups beneath
            # the close form ticks the management rules; 5 held, 6 not
            _, html = self.get(f"/close/{trade_id}")
            self.assertIn('id="held-pull-5"', html)
            self.assertIn('id="exit-checklist"', html)
            self.post(f"/close/{trade_id}", {"token": self.form_token(html),
                                             "result": "Win", "pnl": "200",
                                             "exit": "2026-08-30T10:00",
                                             "held_pull": ["5"],
                                             "why_pull_6": "held over the weekend"})
            t = store.load_trade(self.root, trade_id)
            self.assertEqual((t.deviations, t.exit_deviations), ([2], [6]))
            # the reason of the entry stays, the reason of the close is added
            self.assertEqual(t.reasons, {2: "target 1.6R, took it anyway",
                                         6: "held over the weekend"})
            self.S.drop_cache()
            _, html = self.get("/playbook/pull")
            self.assertIn("Reasons given", html)
            self.assertIn("held over the weekend", html)
            _, html = self.get(f"/trade/{trade_id}")
            self.assertIn('<li class="no"><span class="n">6</span>', html)
            self.assertIn('<li class="ok"><span class="n">5</span>', html)
            self.assertIn("1 rule not held", html)
            # editing the closed trade without touching the list keeps it;
            # touching it records it
            _, html = self.get(f"/edit/{trade_id}")
            self.assertIn('id="held-pull-5" name="held_pull" value="5" checked', html)
            token = self.form_token(html)
            fields = {"token": token, "blocks": "1", "account": "broker", "pair": "EURUSD",
                      "direction": "long", "style": "swing", "entry_tf": "H4", "risk": "1",
                      "entry": "2026-08-29T14:30", "idea_tf_1": "H4", "idea_text_1": "edited",
                      "playbook": "pull", "setup_pull": "A", "met_pull": ["1", "4"],
                      "why_pull_2": "target 1.6R, took it anyway",     # the form sends it back
                      "closed": "1", "result": "Win", "pnl": "200", "exit": "2026-08-30T10:00",
                      "ticked_exit": "1", "held_pull": ["5", "6"]}
            self.post(f"/edit/{trade_id}", fields)
            t = store.load_trade(self.root, trade_id)
            self.assertEqual(t.exit_deviations, [])
            self.assertEqual(t.reasons, {2: "target 1.6R, took it anyway"})   # 6 is held now
            self.S.drop_cache()
            _, html = self.get("/playbook/pull")
            self.assertIn("held to the end <b>1</b>", html)
            self.assertIn('<th class="num">held</th>', html)
            self.S.drop_cache()
            _, html = self.get("/stats")
            # the playbooks head the zone of cards, the plain slices being
            # the appendix under and beside them
            self.assertIn('<div class="twin"><div><div class="card">'
                          '<h2>By playbook</h2>', html)
            self.assertLess(html.index('class="tiles strip"'),
                            html.index("<h2>By playbook</h2>"))
            self.assertIn('href="/playbook/pull"', html)
            self.assertIn('<tr class="sub"><td>A</td>', html)
            self.assertIn(f'>{stats.NO_PLAYBOOK}</td>', html)
            _, html = self.get("/playbook/pull")
            self.assertIn("What a rule costs", html)
            self.assertIn("kept every rule", html)
            self.post("/report/build", {"what": "month", "period_month": "2026-08"})
            _, html = self.get("/report/2026-08")
            self.assertIn("By playbook", html)
            self.assertIn('href="/playbook/pull"', html)
            # the one ticked trade broke rule 2 at the entry: the report counts
            # it as a mistake, names the rule and what the trade brought
            self.assertIn("1 broke a rule", html)
            self.assertIn("kept every rule", html)
            self.assertIn('<span class="n muted">2</span>', html)
            for tid in (trade_id, bare):
                shutil.rmtree(store.trade_dir(self.root, tid))
        finally:
            shutil.rmtree(store.playbook_dir(self.root, "pull"))
            self.S.drop_cache()

    def test_44d_the_checklist_survives_the_playbook_and_the_version_moving(self):
        store.save_playbook(self.root, Playbook(
            id="pull", name="Pullback", styles=["swing"], version="1.0",
            setups=[Setup(name="A", rules=[Rule(1, "Level on D1"), Rule(2, "Target 2R away")])],
            filters=[Rule(3, "An hour to the news")],
            management=[Rule(4, "Stop never moved")]))
        store.save_playbook(self.root, Playbook(
            id="other", name="Other", styles=["swing"], version="2.0",
            setups=[Setup(rules=[Rule(1, "One")])], management=[Rule(2, "Held"), Rule(3, "Closed")]))
        try:
            trade_id = self.open_trade(playbook="pull", setup_pull="A", met_pull=["1", "3"],
                                       ticked="1", why_pull_2="early")
            _, html = self.get(f"/close/{trade_id}")
            self.post(f"/close/{trade_id}", {"token": self.form_token(html), "result": "Win",
                                             "pnl": "100", "exit": "2026-08-30T10:00",
                                             "held_pull": ["4"]})
            self.S.drop_cache()
            base = {"blocks": "1", "account": "broker", "pair": "EURUSD", "direction": "long",
                    "style": "swing", "entry_tf": "H4", "risk": "1", "entry": "2026-08-29T14:30",
                    "idea_tf_1": "H4", "idea_text_1": "edited", "closed": "1",
                    "result": "Win", "pnl": "100", "exit": "2026-08-30T10:00"}

            # 4: moved to another playbook, the old ticks at the close go with it
            _, html = self.get(f"/edit/{trade_id}")
            self.post(f"/edit/{trade_id}", dict(base, token=self.form_token(html),
                                                 playbook="other", ticked="1", met_other=["1"]))
            t = store.load_trade(self.root, trade_id)
            self.assertEqual((t.playbook, t.playbook_version, t.deviations), ("other", "2.0", []))
            self.assertIsNone(t.exit_deviations)
            self.assertEqual(t.reasons, {})
            # and back, ticked afresh
            _, html = self.get(f"/edit/{trade_id}")
            self.post(f"/edit/{trade_id}", dict(base, token=self.form_token(html),
                                                 playbook="pull", setup_pull="A", ticked="1",
                                                 met_pull=["1", "3"], why_pull_2="early",
                                                 ticked_exit="1", held_pull=["4"]))
            t = store.load_trade(self.root, trade_id)
            self.assertEqual((t.deviations, t.exit_deviations, t.reasons), ([2], [], {2: "early"}))

            # 2: a new number with the rules untouched freezes the old rules
            self.S.drop_cache()
            _, html = self.get("/playbook/pull/edit")
            fields = {"name": "Pullback", "status": "experiment", "version": "1.1", "styles": "swing",
                      "setups": "1", "setup_name_1": "A", "setup_rule_1": ["Level on D1", "Target 2R away"],
                      "filter": ["An hour to the news"], "management": ["Stop never moved"]}
            self.post("/playbook/pull/edit", fields)
            self.assertEqual(store.playbook_versions(self.root, "pull"), ["1.0"])
            # the rules change under 1.1 freely, nobody ticked 1.1; 1.0 keeps its text
            self.post("/playbook/pull/edit", dict(fields, setup_rule_1=["Level on W", "Target 2R away"]))
            _, html = self.get(f"/trade/{trade_id}")
            self.assertIn("Level on D1", html)
            self.assertNotIn("Level on W", html)

            # 3: an attached trade ticked after the move takes the version it was held to
            loose = Trade(id="2031-02-02-01-eurusd", account="broker", pair="EURUSD",
                          direction="long", style="swing", opened=datetime(2031, 2, 2),
                          playbook="pull", playbook_version="1.0")
            store.save_trade(self.root, loose)
            self.S.drop_cache()
            _, html = self.get(f"/edit/{loose.id}")
            self.assertIn("Level on D1", html)                # drawn from the frozen 1.0
            self.post(f"/edit/{loose.id}", {"token": self.form_token(html), "blocks": "1",
                                            "account": "broker", "pair": "EURUSD",
                                            "direction": "long", "style": "swing", "risk": "1",
                                            "entry": "2031-02-02T10:00", "playbook": "pull",
                                            "setup_pull": "A", "ticked": "1", "met_pull": ["1", "2", "3"]})
            t = store.load_trade(self.root, loose.id)
            self.assertEqual((t.playbook_version, t.deviations), ("1.0", []))
            shutil.rmtree(store.trade_dir(self.root, loose.id))

            # 1: the playbook deleted, an edit of the trade keeps its checklist
            self.post("/playbook/pull/delete", {})
            self.S.drop_cache()
            _, html = self.get(f"/edit/{trade_id}")
            self.assertIn('<option value="pull" selected>', html)
            self.post(f"/edit/{trade_id}", dict(base, token=self.form_token(html),
                                                 playbook="pull", idea_text_1="a fix"))
            t = store.load_trade(self.root, trade_id)
            self.assertEqual((t.playbook, t.deviations, t.exit_deviations, t.reasons),
                             ("pull", [2], [], {2: "early"}))
            _, html = self.get(f"/trade/{trade_id}")
            self.assertEqual(self.get(f"/trade/{trade_id}")[0], 200)

            # 5: a reserved heading in the notes or a review is refused
            self.refused("/playbook/other/edit", {"name": "Other", "status": "active", "version": "2.0",
                                                  "setups": "1", "setup_rule_1": ["One"],
                                                  "notes": "## Filters\n\n- [ ] typed in the notes"})
            self.refused("/playbook/other/edit", {"name": "Other", "status": "active", "version": "2.0",
                                                  "setups": "1", "setup_rule_1": ["One"],
                                                  "intro": "## Markets\n\nall"})
            _, html = self.get("/playbook/other")
            self.refused("/playbook/other/review", {"token": self.form_token(html),
                                                    "review": "## Management\n\n- [ ] x"})
            self.assertEqual([r.text for r in store.load_playbook(self.root, "other").filters], [])
            # 6: bold marks typed into the few words do not tear the rule apart
            self.post("/playbook/other/edit", {"name": "Other", "status": "active", "version": "2.0",
                                               "setups": "1", "setup_rule_1": ["**One** thing"],
                                               "setup_rule_1_detail": ["the whole rule"]})
            r = store.load_playbook(self.root, "other").rules[0]
            self.assertEqual((r.text, r.detail), ("One thing", "the whole rule"))
            shutil.rmtree(store.trade_dir(self.root, trade_id))
        finally:
            for pid in ("pull", "other"):
                if os.path.isdir(store.playbook_dir(self.root, pid)):
                    shutil.rmtree(store.playbook_dir(self.root, pid))
            self.S.drop_cache()

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
        tile = re.search(r'<div class="tile([^"]*)"><div class="name">'
                         r'<a href="/stats\?account=broker"[^>]*>Broker', html)
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
        self.assertIn("longest run of losses", html)

    # --- the weekly card ---
    def test_62_a_weekly_card_is_written_and_read_back(self):
        _, html = self.get("/week/2026-W35")
        self.assertIn("Weekly report card", html)
        self.assertIn("missed / underexploited opportunities", html)
        # the progress of the focus: ten numbers, each with what it means
        self.assertIn('<option value="10">10 · done, take a new focus</option>', html)
        self.assertIn('<option value="1">1 · not moved</option>', html)
        self.assertIn('<option value="5">5 · halfway</option>', html)
        self.assertNotIn('<option value="11"', html)
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
        rows = dict(stats.by_values(j, j.trades, lambda t: [t.pair]))
        self.assertIn("NZDCAD", rows)
        code, html = self.get("/stats")
        self.assertEqual(code, 200)
        self.assertIn('<th class="num">EV</th>', html)
        self.assertNotIn("average R", html)
        for pair, s in rows.items():
            # the label of a row is a link on the statistics, plain in a report
            row = re.search(rf'<tr><td>(?:<a [^>]*>)?'
                            rf'{re.escape(self.S.H.pair(pair))}(?:</a>)?</td>(.*?)</tr>',
                            html)
            self.assertTrue(row, pair)
            self.assertIn(f'<td class="num">{s.average_r:+.2f}</td>', row.group(1), pair)
        # the same column in a report, in the summary and in every slice
        self.post("/report/build", {"what": "month", "period_month": "2026-08"})
        code, html = self.get("/report/2026-08")
        self.assertEqual(code, 200)
        # the EV stands beside the winrate in the strip, as on the front page
        self.assertIn('<span class="muted">EV</span>', html)
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
        # the same list is offered to the best trade, which is written by hand
        self.assertIn('class="pick" data-into="best"', html)
        # and is not offered on a day the journal held no trade at all: the
        # list behind it would be empty
        self.assertNotIn('class="pick"', self.get("/card/2000-01-01")[1])
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

    def test_74_a_swing_still_open_is_graded_on_the_week_it_was_run(self):
        """The card of week 29 is written while the position is in the market:
        the row keeps the trade, says "open", and says what the trade made when
        it closes, in week 30, with the day it closed on."""
        tid = self.open_trade(pair="USDJPY", style="swing", risk="1",
                              entry="2026-07-14T09:00")
        q = urllib.parse.quote(tid)
        label = "USDJPY long, open since 14.07"
        _, html = self.get("/week/2026-W29")
        self.assertIn(f'<option value="{label}">', html)      # offered, though open
        self.assertIn(f'"{label}": "{tid}"', html.replace("&quot;", '"'))
        self.assertIn('name="assess_id"', html)
        # graded in the week it was run, with the result the journal offered
        self.post("/week/save", {
            "week": "2026-W29", "previous": "2026-W29", "grade": "B",
            "focus": "hold the swing", "assess_trade": [label],
            "assess_grade": ["A"], "assess_result": ["open"], "assess_id": [tid]})
        k = store.load_week(self.root, "2026-W29")
        # the answer of the journal is not written into the card: the trade is
        self.assertEqual([(r.trade, r.grade, r.result, r.id) for r in k.assessment],
                         [(label, "A", "", tid)])
        _, html = self.get("/week/2026-W29")
        self.assertIn('style="width:100%" value="open"', html)
        # it closes a week later, in week 30
        _, form = self.get(f"/close/{q}")
        self.post(f"/close/{q}", {"token": self.form_token(form), "result": "Win",
                                  "pnl": "200", "exit": "2026-07-22T12:00"})
        r = self.S.journal(True).r(tid)
        # the card of week 29 now says what the swing made, and when
        _, html = self.get("/week/2026-W29")
        self.assertIn(f'style="width:100%" value="Win {r:+.2f} R, 22.07"', html)
        # and in week 30, where the money is, it is offered as a closed trade
        _, html = self.get("/week/2026-W30")
        self.assertIn('<option value="USDJPY long, 22.07">', html)
        # the cards tab counts the trades of a week by colour and no words:
        # week 29 held it and did not close it, so it is the blue one there,
        # and week 30, where it closed in the money, has it green
        def row(week, html):
            return re.search(rf'href="/week/{week}".*?</tr>', html, re.S).group(0)
        self.post("/week/save", {"week": "2026-W30", "previous": "2026-W30",
                                 "grade": "A", "focus": "let it run"})
        _, html = self.get("/cards")
        self.assertIn('<span class="live">', row("2026-W29", html))
        self.assertNotIn('<span class="win">', row("2026-W29", html))
        self.assertIn('<span class="win">1</span>', row("2026-W30", html))
        self.post(f"/week/2026-W30/delete", {})
        self.post(f"/week/2026-W29/delete", {})
        self.post(f"/trade/{q}/delete", {})

    def test_75_a_card_with_no_trades_behind_it_keeps_its_own_count(self):
        """A week brought in from before the journal held those trades has
        nothing to break down, and the number written on it stands."""
        self.post("/week/save", {"week": "2026-W20", "previous": "2026-W20",
                                 "grade": "C", "trades": "6", "focus": "imported"})
        _, html = self.get("/cards")
        row = re.search(r'href="/week/2026-W20".*?</tr>', html, re.S).group(0)
        self.assertNotIn("breakdown", row)
        self.assertIn(">6</a>", row)
        self.post("/week/2026-W20/delete", {})

    def test_76_the_reports_tab_is_a_shelf_of_every_period(self):
        """Every month and quarter since the first closed trade, its figures
        live from the journal, a link where a report stands and the form that
        builds one where none does."""
        from plainbook import stats
        _, html = self.get("/reports")
        self.assertIn('href="/report/2026-08"', html)          # built by an earlier test
        self.assertIn('action="/report/build"', html)
        self.assertIn('name="period_month"', html)
        self.assertIn('name="period_quarter"', html)
        # the quarter stands over its months
        self.assertLess(html.index("Q3 2026"), html.index("August 2026"))
        # the figures come from the journal, the file only keeps the text
        j = self.S.journal()
        s = stats.summary(j, self.S.reports.trades_of_period(j, "2026-08"))
        self.assertIn(f'>{s.sum_r:+.2f}</td>', html)
        # the two select boxes of old are gone: one row, one button
        self.assertNotIn("Build month", html)
        self.assertNotIn("Build quarter", html)

    def test_75b_a_trade_opened_from_a_report_offers_the_way_back(self):
        """A bar of the tape, the best trade, a loss past the stop: each link
        carries its report, and the trade page answers with a button back to
        it. Any other address in the query is ignored."""
        _, html = self.get("/report/2026-08")
        m = re.search(r'href="(/trade/[^"?]+)\?report=2026-08"', html)
        self.assertIsNotNone(m)
        way = m.group(1)
        _, html = self.get(f"{way}?report=2026-08")
        self.assertIn('<a class="btn" href="/report/2026-08">← August 2026</a>', html)
        _, html = self.get(f"{way}?report=/evil")
        self.assertNotIn("← ", html)
        _, html = self.get(way)
        self.assertNotIn('href="/report/', html)

    def test_76b_a_stray_file_in_the_reports_folder_is_passed_over(self):
        """A note or a copy left in journal/reports, and a header edited by
        hand, must not take the shelf or the report down."""
        from plainbook import reports
        folder = os.path.join(self.root, store.JOURNAL, reports.DIR)
        stray = [os.path.join(folder, "notes.md"), os.path.join(folder, "2026-08 copy.md"),
                 os.path.join(folder, "2026-13.md")]
        for f in stray:
            with open(f, "w", encoding="utf-8") as h:
                h.write("just a note\n")
        broken = reports.path(self.root, "2026-06")
        with open(broken, "w", encoding="utf-8") as h:
            h.write("---\nno colon here\n---\n\n## Conclusions\n\nkept by hand\n")
        try:
            code, html = self.get("/reports")
            self.assertEqual(code, 200)
            # the Notes tab carries the word on every page, so the stray file
            # is looked for as the report it would have been read as
            self.assertNotIn('href="/report/notes"', html)
            self.assertNotIn("2026-13", html)
            self.assertIn('href="/report/2026-06"', html)
            code, html = self.get("/report/2026-06")
            self.assertEqual(code, 200)
            self.assertIn("kept by hand", html)
            for gone in ("/report/notes", "/report/2026-13"):
                with self.assertRaises(urllib.error.HTTPError) as e:
                    self.get(gone)
                self.assertEqual(e.exception.code, 404)
        finally:
            for f in stray + [broken]:
                os.remove(f)

    def test_77_a_report_draws_its_trades_and_reads_its_conclusions(self):
        """One bar per closed trade, each a way to the trade; the conclusions
        a field until written, then text behind an Edit fold."""
        from plainbook import stats
        self.post("/report/build", {"what": "month", "period_month": "2026-08"})
        _, html = self.get("/report/2026-08")
        j = self.S.journal()
        closed = self.S.reports.trades_of_period(j, "2026-08")
        tape = re.search(r'<svg class="tape".*?</svg>', html, re.S).group(0)
        bars = re.findall(r'<a href="/trade/([^"]+)"><rect', tape)
        self.assertEqual(len(bars), len(closed))
        self.assertEqual(self.get("/trade/" + bars[0])[0], 200)
        self.assertIn(">stop<", tape)                         # the dashed -1 R line is named
        # the strip says what the journal says, and the period before is there
        s = stats.summary(j, closed)
        self.assertIn(f"{s.sum_r:+.2f} R", html)
        self.assertIn("July 2026", html)
        # no conclusions: the field is open and there is nothing to fold
        self.post("/report/2026-08", {"conclusions": ""})
        _, html = self.get("/report/2026-08")
        self.assertIn('<textarea name="conclusions"', html)
        self.assertNotIn("<summary>Edit</summary>", html)
        self.post("/report/2026-08",
                  {"conclusions": "size flat, stops held\n\nnext: no second entry"})
        _, html = self.get("/report/2026-08")
        self.assertIn("<summary>Edit</summary>", html)
        self.assertIn("<p>size flat, stops held</p>", html)
        self.assertIn("<p>next: no second entry</p>", html)
        field = re.search(r'<textarea name="conclusions".*?>(.*?)</textarea>',
                          html, re.S).group(1)
        self.assertIn("size flat", field)                    # an edit starts from the text
        # the shelf marks the report whose conclusions are written
        _, shelf = self.get("/reports")
        self.assertIn('class="dot"', shelf)

    def test_77b_a_period_of_the_picture_narrows_the_statistics(self):
        """A row of the periods answers on this page and with its own figures:
        it cuts by the exit, the way it was counted, and not by the months of
        the filter, which pick by the entry."""
        _, html = self.get("/stats")
        self.assertIn('href="/stats?closed=', html)
        j = self.S.journal()
        want = self.S.stats.summary(j, self.S.stats.closed_in(j.trades, "2026-08"))
        _, html = self.get("/stats?closed=2026-08")
        head = re.search(r'<div class="page-head">.*?</p>', html, re.S).group(0)
        self.assertIn("August 2026", head)
        self.assertIn(f"{want.trades} closed", head)
        self.assertIn(f'{want.sum_r:+.2f} R</span> over {want.trades} closed', html)
        # and it drops itself again from the title
        self.assertIn('<a href="/stats" title="drop this">', head)

    def test_78_a_loss_past_the_stop_with_no_exit_written_still_draws(self):
        """A trade can carry a result and no exit date: the record loads, the
        trade page prints a hyphen for the date, and the statistics must do
        the same rather than refusing to draw the page."""
        store.save_trade(self.root, Trade(
            id="no-exit-loss", account="broker", pair="US100", direction="long",
            style="swing", risk=1.0, opened=datetime(2026, 8, 11),
            result="Lose", pnl=-500))            # about -5 R, well past the stop
        self.S.drop_cache()
        try:
            code, html = self.get("/stats")
            self.assertEqual(code, 200)
            past = re.search(r"<h2>Past the stop</h2>.*?</table>", html, re.S).group(0)
            self.assertIn("no-exit-loss", past)
            self.assertIn(">-</a>", past)                    # the date it does not have
            # the head says the trade is counted and not drawn, since the
            # picture of the periods cannot place it
            head = re.search(r'<p class="pb-meta">(.*?)</p>', html, re.S).group(1)
            self.assertIn("1 with no exit date", head)
            # the worst trade of the strip names it with a hyphen for the day
            self.assertIn("US100 swing, -</a>", html)
        finally:
            shutil.rmtree(os.path.join(self.root, store.JOURNAL, "trades",
                                       "no-exit-loss"))
            self.S.drop_cache()

    def test_79_a_period_cut_starts_the_curve_where_the_period_began(self):
        """A bar of the picture cuts the page to its period, and the curve
        beside it must then start where the period did, the way a report
        draws it, not at the day the account was opened."""
        _, html = self.get("/stats?closed=2026-08")
        self.assertIn("since the period began", html)
        self.assertNotIn("from start", html)
        _, html = self.get("/stats?from=2026-08&to=2026-08")
        self.assertIn("since the period began", html)
        _, html = self.get("/stats")
        self.assertIn("from start", html)

    def test_79b_the_filter_form_belongs_to_the_tab_it_stands_on(self):
        _, html = self.get("/stats?by=week&axis=trade&closed=2026-08")
        form = re.search(r'<form class="filters"[^>]*>.*?</form>', html, re.S).group(0)
        self.assertIn('action="/stats"', form)
        self.assertIn('<a class="btn" href="/stats">Reset</a>', form)
        self.assertEqual(sorted(re.findall(r'<input type="hidden" name="(\w+)"', form)),
                         ["axis", "by", "closed"])
        # the period is shown in the form, since the badge counts it
        self.assertIn("<label>closed in</label>", form)
        self.assertIn("August 2026", form)
        self.assertIn('<span class="badge">1</span>', html)
        # the front page carries its grouping and nothing of the other tab
        _, html = self.get("/?group=month&closed=2026-08")
        form = re.search(r'<form class="filters"[^>]*>.*?</form>', html, re.S).group(0)
        self.assertIn('action="/"', form)
        self.assertEqual(re.findall(r'<input type="hidden" name="(\w+)"', form), ["group"])

    def test_79c_a_key_that_names_no_period_is_answered_with_the_journal(self):
        """2026-13 and 2025-W53 look like periods and are none; typed into
        the address they must not fell the page, nor be counted as a filter."""
        for key in ("2026-13", "2025-W53", "2026-W00", "junk", "9999-12",
                    "9999-W52", "9999-Q4"):
            code, html = self.get(f"/stats?closed={key}")
            self.assertEqual(code, 200, key)
            self.assertIn("Every closed trade", html)
            self.assertNotIn('class="badge"', html)

    def test_80_a_period_travels_as_itself_and_is_never_turned_into_months(self):
        """The cut carried off this page keeps its period. It used to become
        the months the period covered, so that the front page could take it,
        and those months are the entries of a different set of trades."""
        S = self.S
        self.assertEqual(S.period_name("2026-W01", "week"), "W01 29.12.2025")
        self.assertEqual(S.period_name("2026-08", "month"), "August 2026")
        rows = [(k, None) for k in ("2025-W52", "2026-W01", "2026-W02", "2026-W06")]
        # W01 starts on the 29th of December, so January begins at W02
        self.assertEqual(S.period_marks(rows, "week"),
                         [(0, "Dec"), (2, "Jan 2026"), (3, "Feb")])
        self.assertEqual(S.period_marks([("2025-12", None), ("2026-01", None)], "month"),
                         [(0, "2025"), (1, "2026")])
        q = {"closed": ["2026-W31"], "by": ["week"], "axis": ["trade"], "pair": ["EURUSD"]}
        # how the page happens to be drawn stays behind, the cut travels whole
        self.assertEqual(S.cut_only(q, "/export.csv"),
                         "/export.csv?pair=EURUSD&closed=2026-W31")
        self.assertEqual(S.stats_way(q)(Trade(id="x y", account="broker",
                                              pair="EURUSD", direction="long",
                                              style="swing", risk=1.0,
                                              opened=datetime(2026, 8, 1))),
                         "/trade/x%20y?pair=EURUSD&closed=2026-W31")
        # a key that names no period is not carried at all
        self.assertEqual(S.cut_only({"closed": ["2026-13"], "pair": ["EURUSD"]},
                                    "/export.csv"), "/export.csv?pair=EURUSD")
        q = {"closed": ["2026-08"], "from": ["2026-07"], "to": ["2026-08"]}
        self.assertEqual(S.cut_only(q, "/export.csv"),
                         "/export.csv?from=2026-07&to=2026-08&closed=2026-08")
        self.assertEqual(S.cut_href(q, ("closed",)), "/stats?from=2026-07&to=2026-08")
        self.assertEqual(S.cut_href({"pair": ["EURUSD"]}, ("pair",)), "/stats")
        self.assertIsNone(S.month_start("2026-13"))
        # a week that straddles the edge of the month the page is cut to
        # gets no link: its page would count days the bar never did
        self.assertIsNone(S.period_href("2026-W31", "week", {"closed": ["2026-08"]}))
        self.assertEqual(S.period_href("2026-W32", "week", {"closed": ["2026-08"]}),
                         "/stats?closed=2026-W32")
        self.assertEqual(S.period_href("2026-08", "month", {"closed": ["2026-Q3"]}),
                         "/stats?closed=2026-08")

    def test_80i_a_period_lists_its_trades_on_the_page_that_counted_them(self):
        """The card is the very set the figures were worked out on, by the
        exit, so its rows and the count in the head cannot disagree. Without
        a period cut there is no card, because every other cut is the same
        trades on either page and The trades still opens the journal."""
        S = self.S
        j = S.journal()
        _, html = self.get("/stats?closed=2026-08")
        self.assertIn('<a class="btn" href="#trades"', html)
        card = html[html.index('<div class="card" id="trades">'):]
        want = S.stats.summary(j, S.stats.closed_in(j.trades, "2026-08")).trades
        self.assertEqual(len(re.findall(r'<tr><td class="cell">', card)), want)
        self.assertIn(f">{want} closed in August 2026</span>", card)
        # the exit leads and the entry stands beside it, which is the whole
        # difference between this list and the journal's
        self.assertIn("<th>closed</th><th>entered</th>", card)
        # no cut, no card, and the button still hands the reader to the journal
        for where in ("/stats", "/stats?pair=EURUSD", "/stats?closed=2026-13"):
            _, html = self.get(where)
            self.assertNotIn('id="trades"', html)
            self.assertNotIn('href="#trades"', html)
            self.assertIn("the same selection as a list", html)

    def test_75c_a_report_lists_the_trades_of_its_month(self):
        """A report is a period, so it carries the same card the Statistics
        tab carries under a cut: the trades it closed, counted by the exit,
        each one the way back to this report."""
        S = self.S
        j = S.journal()
        _, html = self.get("/report/2026-08")
        self.assertIn('href="#trades"', html)
        card = html[html.index('<div class="card" id="trades">'):]
        want = len(S.reports.trades_of_period(j, "2026-08"))
        self.assertEqual(len(re.findall(r'<tr><td class="cell">', card)), want)
        self.assertIn(f">{want} closed in August 2026</span>", card)
        self.assertIn("<th>closed</th><th>entered</th>", card)
        # a row carries the report, so the trade answers with the way back
        way = re.search(r'<a href="(/trade/[^"]+)"', card).group(1)
        self.assertIn("?report=2026-08", way)
        _, html = self.get(way.replace("&amp;", "&"))
        self.assertIn('<a class="btn" href="/report/2026-08">← August 2026</a>', html)

    def test_80l_a_cut_carries_a_visible_way_out_of_itself(self):
        """Clicking a month used to be a door that locked: the title drops the
        cut but reads as a heading, and the form's Reset is behind the funnel.
        The head carries one, and only while there is something to drop."""
        # the form inside the funnel has a Reset of its own, so the button is
        # looked for by its own markup and not by the word
        button = ('<a class="btn" href="/stats" title="drop the whole cut and '
                  'read every closed trade">Reset</a>')
        for where in ("/stats?closed=2026-08", "/stats?pair=EURUSD",
                      "/stats?closed=2026-08&pair=EURUSD&by=week"):
            _, html = self.get(where)
            self.assertIn(button, html, where)
        # nothing to drop, no button, and a key that names no period is nothing
        for where in ("/stats", "/stats?closed=2026-13", "/stats?by=month"):
            _, html = self.get(where)
            self.assertNotIn(button, html, where)

    def test_80j_a_trade_opened_from_the_statistics_offers_the_whole_cut_back(self):
        """August and August on one pair are two pages under one title, so a
        way back that carried only the period would land on the wrong one.
        A key that names no period is not carried at all."""
        _, html = self.get("/stats?closed=2026-08&pair=EURUSD")
        card = html[html.index('<div class="card" id="trades">'):]
        way = re.search(r'<a href="(/trade/[^"]+)"', card).group(1).replace("&amp;", "&")
        self.assertIn("pair=EURUSD", way)
        self.assertIn("closed=2026-08", way)
        _, html = self.get(way)
        self.assertIn('<a class="btn" href="/stats?pair=EURUSD&closed=2026-08">'
                      '← Statistics: August 2026</a>', html)
        # a bare trade has nothing to go back to, and a report wins over a cut
        trade = way.split("?")[0]
        _, html = self.get(trade)
        self.assertNotIn("← ", html)
        _, html = self.get(f"{trade}?closed=/evil")
        self.assertNotIn("← ", html)
        _, html = self.get(f"{trade}?report=2026-08&closed=2026-08")
        self.assertIn('href="/report/2026-08">← August 2026</a>', html)
        self.assertNotIn("← Statistics", html)

    def test_80k_a_long_period_folds_the_tail_of_its_list(self):
        """A quarter is a hundred trades and more: the newest thirty stand
        open and the rest go behind one line, the way the table of periods
        folds its own tail."""
        S = self.S
        j = S.journal()
        _, html = self.get("/stats?closed=2026-Q3")
        card = html[html.index('<div class="card" id="trades">'):]
        want = S.stats.summary(j, S.stats.closed_in(j.trades, "2026-Q3")).trades
        self.assertEqual(len(re.findall(r'<tr><td class="cell">', card)), want)
        # the journal these tests share is too short to fold, so the tail is
        # asked of a quarter built for it, the way the periods table asks
        n = S.PERIOD_TRADES_ROWS + 5
        trades = [Trade(id=f"q{i}", account="broker", pair="EURUSD",
                        direction="long", style="swing", risk=1.0,
                        opened=datetime(2026, 7, 1) + timedelta(days=2 * i),
                        closed=datetime(2026, 7, 1) + timedelta(days=2 * i),
                        result="Win", pnl=100) for i in range(n)]
        long = S.Journal(j.accounts, trades, [])
        card = S.period_trades_card(long, trades, "Q3 2026",
                                    lambda t: f"/trade/{t.id}")
        self.assertEqual(len(re.findall(r'<tr><td class="cell">', card)), n)
        self.assertIn("<summary>5 more trades</summary>", card)
        # one fold, and the thirty newest stand before it
        self.assertEqual(card.index("<details"), card.rindex("<details"))
        shown = card[:card.index("<details")]
        self.assertEqual(len(re.findall(r'<tr><td class="cell">', shown)),
                         S.PERIOD_TRADES_ROWS)
        # the newest exit leads, so the last trade written is the first row
        first = re.search(r'<tbody><tr>.*?</tr>', shown, re.S).group(0)
        self.assertIn(f">{trades[-1].closed:%d.%m.%Y}</a>", first)

    def test_80b_the_cards_of_a_zone_are_dealt_into_columns_that_end_together(self):
        S = self.S

        def card(name, rows):
            body = "".join(f"<tr><td>{i}</td></tr>" for i in range(rows))
            return f'<div class="card"><h2>{name}</h2><table>{body}</table></div>'
        self.assertEqual(S.deal([]), "")
        self.assertEqual(S.deal(["", card("only", 3), ""]), card("only", 3))
        cards = [card("a", 12), card("b", 2), card("c", 3), card("d", 4),
                 card("e", 2), card("f", 3)]
        html = S.deal(cards)
        # the columns are told apart by the one seam between them: a card
        # begins with its class, so a bare div opens only the second column
        self.assertTrue(html.startswith('<div class="twin"><div>'))
        left, right = html[len('<div class="twin"><div>'):-len("</div></div>")].split("</div><div>")
        tall = lambda side: sum(S.guess_height(c) for c in cards if c in side)
        self.assertLessEqual(abs(tall(left) - tall(right)), min(map(S.guess_height, cards)))
        # every card once, and inside a column in the order given
        self.assertEqual(sorted(re.findall(r"<h2>(\w)</h2>", left + right)), list("abcdef"))
        self.assertEqual(re.findall(r"<h2>(\w)</h2>", left),
                         [n for n in "abcdef" if f"<h2>{n}</h2>" in left])
        # the pinned pair heads the columns whatever their height
        html = S.deal(cards, pinned=2)
        self.assertTrue(html.startswith('<div class="twin"><div>' + card("a", 12)))
        self.assertIn('</div><div>' + card("b", 2), html)

    def test_80d_the_picture_opens_on_the_grain_the_selection_asks_for(self):
        """One bar per trade while they can be told apart, and a coarser
        grain past that: a history drawn at the wrong grain is either one
        column or three hundred."""
        S = self.S

        def closed(n, months=1):
            out = []
            for i in range(n):
                day = datetime(2026, 1, 1) + timedelta(days=i * 30 * months // max(n, 1))
                out.append(Trade(id=f"t{i}", account="broker", pair="EURUSD",
                                 direction="long", style="swing", risk=1.0,
                                 opened=day, closed=day, result="Win", pnl=100))
            return out
        self.assertEqual(S.period_grain({}, closed(30, 12)), "trade")
        self.assertEqual(S.period_grain({}, closed(31, 2)), "week")
        self.assertEqual(S.period_grain({}, closed(60, 12)), "month")
        self.assertEqual(S.period_grain({}, closed(60, 48)), "quarter")
        # a week holds too few periods to draw: it opens on its trades
        self.assertEqual(S.period_grain({"closed": ["2026-W35"]}, closed(60, 12)),
                         "trade")
        # what the switch says wins over all of it
        self.assertEqual(S.period_grain({"by": ["quarter"]}, closed(3, 1)), "quarter")

    def test_80e_the_periods_table_shows_the_newest_twelve_and_folds_the_rest(self):
        S = self.S
        j = S.journal()
        trades = []
        for i in range(14):
            day = datetime(2025, 1, 1) + timedelta(days=31 * i)
            trades.append(Trade(id=f"m{i}", account="broker", pair="EURUSD",
                                direction="long", style="swing", risk=1.0,
                                opened=day, closed=day, result="Win", pnl=100))
        card = S.periods_table(S.Journal(j.accounts, trades, []), {}, trades, "month")
        rows = re.findall(r'<a href="/stats\?closed=([^"]+)">', card)
        self.assertEqual(len(rows), 14)
        self.assertEqual(rows[0], "2026-02")                 # newest first
        # twelve stand open, the rest under one line
        self.assertEqual(card.index("<details"), card.rindex("<details"))
        self.assertIn("<summary>2 more months</summary>", card)
        shown = card[:card.index("<details")]
        self.assertEqual(len(re.findall(r'<a href="/stats\?closed=', shown)), 12)
        # a single period is not a table
        self.assertEqual(S.periods_table(j, {}, trades[:1], "month"), "")

    def test_80f_an_open_ticked_trade_is_not_a_mistake(self):
        """A position still in the market has no R to put against a rule, and
        every figure of the strip counts what is closed."""
        store.save_trade(self.root, Trade(
            id="open-ticked", account="broker", pair="EURUSD", direction="long",
            style="swing", risk=1.0, opened=datetime(2026, 8, 25),
            playbook="pull", playbook_version="1.0", deviations=[2]))
        self.S.drop_cache()
        try:
            j = self.S.journal()
            live = self.S.reports.discipline(self.root, j, j.trades)
            closed = self.S.reports.discipline(
                self.root, j, [t for t in j.trades if not t.is_open])
            self.assertEqual(len(live.mistakes), len(closed.mistakes))
            self.assertEqual(live.entry_broken, closed.entry_broken)
            self.assertEqual([r[1].number for r in live.rules],
                             [r[1].number for r in closed.rules])
            self.assertFalse(any(t.id == "open-ticked" for t in live.mistakes))
        finally:
            shutil.rmtree(store.trade_dir(self.root, "open-ticked"))
            self.S.drop_cache()

    def test_80g_a_table_the_page_is_already_cut_to_is_not_drawn(self):
        _, html = self.get("/stats")
        self.assertIn("<h2>By pair</h2>", html)
        _, html = self.get("/stats?pair=EURUSD")
        self.assertNotIn("<h2>By pair</h2>", html)           # one row, the strip says it
        self.assertIn('class="tiles strip"', html)           # and the page still stands

    def test_80h_a_tile_says_which_way_its_figure_failed(self):
        """The branches of the strip that no page of the demo reaches: a
        winrate no winrate would save, a win that came back under zero, and
        a fall still open at the end of a period that is not today."""
        S = self.S

        def made(rows):
            trades = [Trade(id=f"t{i}", account="broker", pair="EURUSD",
                            direction="long", style="swing", risk=1.0,
                            opened=datetime(2026, 8, 1) + timedelta(days=i),
                            closed=datetime(2026, 8, 1) + timedelta(days=i),
                            result=result, pnl=float(pnl))
                      for i, (result, pnl) in enumerate(rows)]
            j = S.Journal({"broker": Account(id="broker", start_balance=10000)},
                          trades, [])
            return j, trades, S.stats.summary(j, trades)
        # the break-evens eat more than a win brings
        j, trades, sm = made([("Win", 300)] * 3 + [("Lose", -100)] * 3
                             + [("BE", -90)] * 24)
        self.assertGreater(sm.needed_wr, 100)
        tile = S.wr_tile(j, trades, sm, None)
        self.assertIn("needs over 100%", tile)
        self.assertIn("the break-evens cost more than a win brings", tile)
        # a win that came back under zero after commission: no ratio to give,
        # and the blame is not the break-evens, there are none
        j, trades, sm = made([("Win", -5)] * 5 + [("Lose", -100)] * 5)
        self.assertEqual(sm.be, 0)
        self.assertIsNone(sm.payoff)
        self.assertGreater(sm.needed_wr, 100)
        self.assertIn("a win came back at", S.payoff_tile(sm, None))
        self.assertIn("a win brought less than nothing on average",
                      S.wr_tile(j, trades, sm, None))
        # a hole still open where the selection ends: "now" only when the
        # selection runs to today
        j, trades, sm = made([("Win", 300), ("Lose", -100), ("Lose", -100)])
        fall = S.stats.drawdown(j, trades)
        self.assertIn("under the high now", S.fall_tile(j, trades, sm, fall, True))
        self.assertIn("under the high at the end", S.fall_tile(j, trades, sm, fall, False))

    def test_80c_the_head_names_both_years_when_the_span_crosses_one(self):
        store.save_trade(self.root, Trade(
            id="2025-12-30-01-eurusd", account="broker", pair="EURUSD",
            direction="long", style="swing", risk=1.0,
            opened=datetime(2025, 12, 30), closed=datetime(2025, 12, 31),
            result="Win", pnl=100))
        self.S.drop_cache()
        try:
            _, html = self.get("/stats")
            head = re.search(r'<p class="pb-meta">(.*?)</p>', html, re.S).group(1)
            self.assertIn("31.12.2025 to ", head)
            # the trades of the year before stand in the picture: a month
            # that closed nothing keeps its place between them
            _, html = self.get("/stats?by=month")
            self.assertIn(">Dec<", html)
            self.assertIn(">Jan<", html)
        finally:
            shutil.rmtree(store.trade_dir(self.root, "2025-12-30-01-eurusd"))
            self.S.drop_cache()

    # --- what leaves the journal ---

    def a_trade_with_shots(self):
        """A trade that has pictures: the point of a document is that they
        travel with it."""
        folder = os.path.join(self.root, "journal", "trades")
        for trade in sorted(os.listdir(folder)):
            shots = os.path.join(folder, trade, store.SHOTS)
            if os.path.isdir(shots) and os.listdir(shots):
                return trade
        self.fail("no trade with a screenshot in the test journal")

    def test_90_a_trade_is_shown_as_one_file(self):
        """The preview, then the file: same document, and the file carries its
        own pictures so it opens on a machine with no journal."""
        trade = self.a_trade_with_shots()
        code, html = self.get(f"/share/trade/{trade}")
        self.assertEqual(code, 200)
        self.assertIn('class="bar"', html)          # the strip over a preview
        self.assertIn(f'src="/shot/{trade}/', html)
        code, html = self.get(f"/share/trade/{trade}?file=1")
        self.assertEqual(code, 200)
        self.assertNotIn('class="bar"', html)       # no buttons in what is sent
        self.assertNotIn('src="/shot/', html)
        self.assertIn("data:image/png;base64,", html)

    def test_91_the_file_arrives_named(self):
        trade = self.a_trade_with_shots()
        with urllib.request.urlopen(
                self.url(f"/share/trade/{trade}?file=1")) as r:
            said = r.headers.get("Content-Disposition")
        self.assertIn("attachment", said)
        self.assertIn(f"plainbook-{trade}.html", said)

    def test_92_the_selection_and_the_report_are_shown_too(self):
        code, html = self.get("/share/journal?shots=0")
        self.assertEqual(code, 200)
        self.assertIn("Trades", html)
        built = sorted(os.listdir(os.path.join(self.root, "journal", "reports")))
        period = built[0].removesuffix(".md")
        code, html = self.get(f"/share/report/{period}?shots=0")
        self.assertEqual(code, 200)
        self.assertIn("The trades", html)

    def test_93_a_selection_with_nothing_in_it_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/share/journal?pair=NOTHING")
        self.assertEqual(caught.exception.code, 404)

    def test_94_the_way_to_a_document_is_on_the_page(self):
        """A button on the trade, one over the list, one on the report."""
        trade = self.a_trade_with_shots()
        _, html = self.get(f"/trade/{trade}")
        self.assertIn(f'href="/share/trade/{trade}"', html)
        _, html = self.get("/")
        self.assertIn('href="/share/journal"', html)

    def test_95_breakeven_frees_the_risk_of_an_open_trade(self):
        """Two trades of 1% against a limit of 150 $: over. The first moved
        to breakeven: 100 $ at risk, the tile calms down, the trade says
        since when. Risk back puts it where it was."""
        now = datetime.now().strftime("%Y-%m-%dT%H:%M")
        first = self.open_trade(entry=now, risk="1", pair="EURUSD")
        second = self.open_trade(entry=now, risk="1", pair="USDJPY")
        q = urllib.parse.quote(first)
        # the tests share one journal, so the limit is cut just under what
        # is at stake now: the risk of the first trade, ~100 $, freed takes
        # the account back under it
        j = self.S.journal(True)
        used = max(0.0, -j.closed_on("broker", datetime.now())) + j.open_risk("broker")
        self.post("/account/limit", {"id": "broker", "limit": f"{used - 50:.2f}"})
        _, html = self.get("/")
        self.assertIn("daily loss limit reached", html)
        self.assertIn(f'action="/trade/{q}/breakeven"', html)
        self.assertNotIn('class="chip breakeven"', html)

        _, where = self.post(f"/trade/{q}/breakeven", {"back": "/"})
        self.assertEqual(urllib.parse.urlparse(where).path, "/")
        self.assertIsNotNone(store.load_trade(self.root, first).breakeven)
        _, html = self.get("/")
        self.assertNotIn("daily loss limit reached", html)
        self.assertIn("1 at breakeven", html)
        # other tests leave positions of their own open, so only the tail
        self.assertRegex(html, r"Open positions: \d+, 1 at breakeven")
        self.assertIn('class="chip breakeven"', html)
        _, html = self.get(f"/trade/{q}")
        self.assertIn("at breakeven since", html)
        self.assertIn('name="undo" value="1"', html)

        # an edit of another field keeps the stop where it is
        _, form = self.get(f"/edit/{q}")
        fields = {"token": self.form_token(form), "blocks": "1", "account": "broker",
                  "pair": "EURUSD", "direction": "long", "style": "swing",
                  "entry_tf": "H4", "risk": "1", "entry": now,
                  "idea_tf_1": "H4", "idea_text_1": "edited"}
        self.post(f"/edit/{q}", fields)
        self.assertIsNotNone(store.load_trade(self.root, first).breakeven)

        _, where = self.post(f"/trade/{q}/breakeven", {"undo": "1"})
        self.assertEqual(self.landed(where), first)
        self.assertIsNone(store.load_trade(self.root, first).breakeven)
        self.assertIn("daily loss limit reached", self.get("/")[1])

        # a closed trade has nothing to free
        _, form = self.get(f"/close/{urllib.parse.quote(second)}")
        self.post(f"/close/{urllib.parse.quote(second)}",
                  {"token": self.form_token(form), "result": "Win", "pnl": "50",
                   "exit": now, "conclusions": ""})
        self.refused(f"/trade/{urllib.parse.quote(second)}/breakeven", {})
        self.post("/account/limit", {"id": "broker", "limit": ""})
        self.post(f"/trade/{q}/delete", {})
        self.post(f"/trade/{urllib.parse.quote(second)}/delete", {})

    def test_96_the_moved_stops_have_a_card_and_a_line_in_the_report(self):
        """A trade moved to breakeven and stopped at the entry: the
        Statistics tab gets the card, the report of its month gets the
        sentence in Process."""
        _, html = self.get("/stats?pair=CADJPY")
        self.assertNotIn("<h2>Stop at breakeven</h2>", html)
        tid = self.open_trade(entry="2026-07-06T10:00", pair="CADJPY")
        q = urllib.parse.quote(tid)
        self.post(f"/trade/{q}/breakeven", {})
        _, form = self.get(f"/close/{q}")
        self.post(f"/close/{q}", {"token": self.form_token(form), "result": "BE",
                                  "pnl": "-3", "exit": "2026-07-08T15:00",
                                  "conclusions": ""})
        _, html = self.get("/stats?pair=CADJPY")
        self.assertIn("<h2>Stop at breakeven</h2>", html)
        self.assertIn("moved on 1 of 1", html)
        self.assertIn("1 stopped at the entry", html)
        self.assertNotIn("After the move, not a win", html)
        self.post("/report/build", {"what": "month", "period_month": "2026-07"})
        _, html = self.get("/report/2026-07")
        self.assertIn("Stop moved to breakeven on 1 of", html)
        self.post(f"/trade/{q}/delete", {})


    def test_97_a_note_is_written_with_a_shot_and_a_trade_is_tied_to_it(self):
        _, html = self.get("/notes")
        self.assertIn("No notes yet", html)
        earlier = self.open_trade(entry="2026-09-02T09:00", pair="GBPUSD")
        _, form = self.get("/note/new")
        token = self.form_token(form)
        shot = self.paste_shot(token, "idea-1")
        # two blocks, the second with a heading, and a trade picked in the form
        self.assertIn(f'<option value="{earlier}">', form)
        code, where = self.post("/note/new", {
            "token": token, "title": "London sweep", "date": "2026-09-09",
            "blocks": "2",
            "idea_text_1": "The Asian high goes first.", "file_idea-1": shot["file"],
            "idea_tf_2": "What to wait for", "idea_text_2": "The M15 close.",
            "trade": [earlier, earlier, "no-such-trade"]})
        self.assertEqual(code, 200)
        note_id = self.landed(where)
        self.assertEqual(note_id, "2026-09-09-london-sweep")
        n = store.load_note(self.root, note_id)
        self.assertEqual([(b.tf, b.text, b.images) for b in n.blocks],
                         [("", "The Asian high goes first.", ["shots/idea-01-01.png"]),
                          ("What to wait for", "The M15 close.", [])])
        self.assertEqual(n.trades, [earlier])        # once, and only a known one
        self.assertEqual(
            self.get(f"/note-shot/{note_id}/idea-01-01.png", as_text=False)[0], 200)
        _, page = self.get(f"/note/{note_id}")
        self.assertIn("<h3>What to wait for</h3>", page)
        self.assertIn(f'href="/trade/{earlier}?note={note_id}"', page)
        # the edit form lists the picked trade and offers the rest
        _, form = self.get(f"/note/{note_id}/edit")
        self.assertIn(f'add_example({json.dumps(earlier)}', form)
        self.assertIn('name="idea_tf_2" value="What to wait for"', form)
        # a second example is tied from the note page itself
        tid = self.open_trade(entry="2026-09-09T09:00", pair="GBPUSD")
        _, page = self.get(f"/note/{note_id}")
        self.assertIn(f'<option value="{tid}">', page)
        _, where = self.post(f"/note/{note_id}/attach", {"trade": tid})
        self.assertIn("Example%20added", where)
        self.assertEqual(store.load_note(self.root, note_id).trades, [earlier, tid])
        _, page = self.get(f"/note/{note_id}")
        self.assertIn(f'href="/trade/{tid}?note={note_id}"', page)
        self.assertNotIn(f'<option value="{tid}">', page)
        _, trade = self.get(f"/trade/{tid}?note={note_id}")
        self.assertIn(f'href="/note/{note_id}">← London sweep</a>', trade)
        self.assertIn("an example in", trade)
        # a second press of the same trade changes nothing
        _, where = self.post(f"/note/{note_id}/attach", {"trade": tid})
        self.assertIn("already", where)
        self.assertEqual(store.load_note(self.root, note_id).trades, [earlier, tid])
        self.refused(f"/note/{note_id}/attach", {"trade": "no-such-trade"})
        # the list names the note and counts its examples; search finds it
        _, html = self.get("/notes")
        self.assertIn("London sweep", html)
        self.assertIn('<td class="cell num"><a href="/note/' + note_id + '">2</a>', html)
        _, html = self.get("/search?q=asian+high")
        self.assertIn(f'href="/note/{note_id}"', html)
        ServerCase.note_id, ServerCase.note_trade = note_id, tid

    def test_98_a_note_is_edited_untied_and_deleted_into_the_trash(self):
        note_id, tid = ServerCase.note_id, ServerCase.note_trade
        _, form = self.get(f"/note/{note_id}/edit")
        self.assertIn("The Asian high goes first.", form)
        self.assertIn('name="have_idea-1" value="shots/idea-01-01.png"', form)
        token = self.form_token(form)
        # the form sends back both trades; the first block is edited, the
        # second is dropped by sending it empty
        self.post(f"/note/{note_id}/edit", {
            "token": token, "title": "London sweep", "date": "2026-09-08",
            "blocks": "2",
            "idea_text_1": "The Asian high goes first, then the low.",
            "have_idea-1": "shots/idea-01-01.png",
            "idea_tf_2": "", "idea_text_2": "",
            "trade": store.load_note(self.root, note_id).trades})
        n = store.load_note(self.root, note_id)
        self.assertEqual(n.day, datetime(2026, 9, 8))
        self.assertEqual(len(n.blocks), 1)
        self.assertIn("then the low", n.blocks[0].text)
        # editing the text keeps the screenshot and the examples
        self.assertEqual(n.blocks[0].images, ["shots/idea-01-01.png"])
        self.assertTrue(os.path.exists(os.path.join(
            store.note_dir(self.root, note_id), "shots", "idea-01-01.png")))
        self.assertEqual(len(n.trades), 2)
        # a screenshot and a trade taken out of the form leave the note
        self.post(f"/note/{note_id}/edit", {
            "token": self.form_token(self.get(f"/note/{note_id}/edit")[1]),
            "title": "London sweep", "date": "2026-09-08", "blocks": "1",
            "idea_text_1": "The Asian high goes first, then the low.",
            "trade": tid})
        self.assertFalse(os.path.exists(os.path.join(
            store.note_dir(self.root, note_id), "shots", "idea-01-01.png")))
        self.assertEqual(store.load_note(self.root, note_id).trades, [tid])
        _, where = self.post(f"/note/{note_id}/detach", {"trade": tid})
        self.assertIn("Example%20removed", where)
        self.assertEqual(store.load_note(self.root, note_id).trades, [])
        self.refused(f"/note/{note_id}/detach", {"trade": tid})
        # into the trash and back
        self.post(f"/note/{note_id}/delete", {})
        self.assertFalse(os.path.exists(store.note_dir(self.root, note_id)))
        name = next(x[0] for x in store.trash_list(self.root)
                    if x[1] == "note" and x[2] == note_id)
        self.post("/trash/restore", {"name": name})
        self.assertTrue(os.path.exists(store.note_dir(self.root, note_id)))
        self.assertEqual(self.get(f"/note/{note_id}")[0], 200)

    def test_99_a_trade_opened_from_a_filtered_list_keeps_the_selection(self):
        """The filter of the front page used to be lost the moment a trade
        was opened: the row carries it, the trade page offers the way back,
        the Journal tab leads to the same list, and the forms land on it."""
        tid = self.open_trade(entry="2026-09-03T09:00", pair="NZDUSD")
        q = urllib.parse.quote(tid)
        _, html = self.get("/?account=broker&pair=NZDUSD&group=month")
        keep = "?via=journal&account=broker&pair=NZDUSD&group=month"
        self.assertIn(f'href="/trade/{tid}{keep}"', html)
        _, html = self.get("/")                            # an unfiltered list
        self.assertIn(f'href="/trade/{tid}"', html)
        self.assertNotIn("via=journal", html)
        _, trade = self.get(f"/trade/{q}{keep}")
        back = "/?account=broker&pair=NZDUSD&group=month"
        self.assertIn(f'href="{back}">← Journal: broker, NZDUSD</a>', trade)
        self.assertNotIn("← Statistics", trade)           # the same names, another page
        header = re.findall(r'<header.*?</header>', trade, re.S)[0]
        self.assertIn(f'<a href="{back}" class="current">Journal</a>', header)
        self.assertIn(f'href="/edit/{tid}{keep}"', trade)
        self.assertIn(f'href="/close/{tid}{keep}"', trade)
        self.assertIn(f'action="/trade/{tid}/breakeven{keep}"', trade)
        # the forms carry it in their action and land back with it
        _, form = self.get(f"/edit/{q}{keep}")
        self.assertIn(f'action="/edit/{tid}{keep}"', form)
        self.assertIn(f'href="/trade/{tid}{keep}">Cancel</a>', form)
        _, where = self.post(f"/edit/{q}{keep}", {
            "token": self.form_token(form), "blocks": "1", "account": "broker",
            "pair": "NZDUSD", "direction": "long", "style": "swing",
            "entry_tf": "H4", "risk": "1", "entry": "2026-09-03T09:00",
            "idea_tf_1": "H4", "idea_text_1": "a plain idea"})
        self.assertIn(f"/trade/{tid}{keep}&said=", where)
        _, where = self.post(f"/trade/{q}/breakeven{keep}", {})
        self.assertIn(f"/trade/{tid}{keep}&said=", where)
        _, form = self.get(f"/close/{q}{keep}")
        self.assertIn(f'action="/close/{tid}{keep}"', form)
        _, where = self.post(f"/close/{q}{keep}", {
            "token": self.form_token(form), "result": "Win", "pnl": "50",
            "exit": "2026-09-04T15:00", "conclusions": ""})
        self.assertIn(f"/trade/{tid}{keep}&said=", where)
        _, where = self.post(f"/trade/{q}/delete{keep}", {})
        self.assertIn(f"{back}&said=", where)
        # the cut of the Statistics tab still offers its own way back
        tid = self.open_trade(entry="2026-09-03T09:00", pair="NZDUSD")
        _, trade = self.get(f"/trade/{urllib.parse.quote(tid)}?account=broker")
        self.assertIn("← Statistics", trade)
        self.assertNotIn("← Journal", trade)


if __name__ == "__main__":
    unittest.main()
