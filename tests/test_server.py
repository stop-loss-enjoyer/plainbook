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

from plainbook import store
from plainbook.model import Account

# a one-pixel PNG — enough to exercise the whole screenshot path
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "05572bd6a20000000049454e44ae426082")


class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.save_account(cls.root, Account(id="bybit", name="Bybit",
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
        cls.tmp.cleanup()
        os.environ.pop("PLAINBOOK_ROOT", None)

    # --- helpers ---
    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path, as_text=True):
        with urllib.request.urlopen(self.url(path)) as r:
            data = r.read()
            return r.status, data.decode("utf-8") if as_text else data

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
        self.assertIn("Bybit", html)
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
        self.assertIn("bybit", field)
        self.assertNotIn("legacy", field)

    def test_03_open_a_trade_with_a_screenshot(self):
        _, html = self.get("/new")
        token = self.form_token(html)
        shot = self.paste_shot(token, "idea-1")
        code, where = self.post("/new", {
            "token": token, "blocks": "1", "account": "bybit", "pair": "EURUSD",
            "direction": "long", "style": "swing", "entry_tf": "H4",
            "execution": ["Market Entry", "SNR"], "risk": "1",
            "entry": "2026-08-29T14:30", "idea_tf_1": "H4",
            "idea_text_1": "breakout, waiting for a retest",
            "file_idea-1": shot["file"]})
        self.assertEqual(code, 200)
        ServerCase.trade_id = urllib.parse.unquote(where.rsplit("/", 1)[1])
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
            "token": token, "blocks": "1", "account": "bybit", "pair": "GBPUSD",
            "direction": "short", "style": "EMT", "entry_tf": "H1",
            "risk": "0.5", "entry": "2026-08-29T14:30", "idea_tf_1": "H1",
            "idea_text_1": "idea rewritten",
            "have_idea-1": "shots/idea-01-01.png",
            "remove": "shots/idea-01-01.png",       # this screenshot goes away
            "have_exit": "shots/exit-01.png"})
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
            "token": "0" * 16, "blocks": "1", "account": "bybit", "pair": "EURUSD",
            "direction": "sideways", "style": "swing", "risk": "1",
            "entry": "2026-08-29T10:00"}).encode()
        req = urllib.request.Request(self.url("/new"), data=data)
        try:
            urllib.request.urlopen(req)
            self.fail("the server swallowed junk")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
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

    def test_14_accounts_are_created_archived_and_deleted(self):
        code, where = self.post("/account/new", {
            "id": "проба", "name": "Test", "start": "5000", "currency": "USD"})
        self.assertIn("latin", urllib.parse.unquote(where))   # cyrillic id is refused
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
        _, where = self.post("/account/delete", {"id": "bybit"})
        self.assertIn("archive it instead", urllib.parse.unquote(where))
        self.assertIn("bybit", store.all_accounts(self.root))

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
            "token": token, "closed": "1", "blocks": "1", "account": "bybit",
            "pair": "GBPUSD", "direction": "short", "style": "EMT",
            "entry_tf": "H1", "risk": "0.5", "entry": "2026-08-29T14:30",
            "idea_text_1": "idea rewritten",
            "have_exit": "shots/exit-01.png", "conclusions": "held to target"})
        t = store.load_trade(self.root, ServerCase.trade_id)
        self.assertEqual(t.exit_images, ["shots/exit-01.png"])
        self.assertIn("held to target", t.conclusions)

    def test_18_a_screenshot_leaves_with_its_own_field(self):
        """The cross in the form only drops a hidden field — the server knows
        nothing about a delete, it rebuilds the folder from what arrived."""
        q = urllib.parse.quote(ServerCase.trade_id)
        _, html = self.get(f"/edit/{q}")
        token = self.form_token(html)
        self.post(f"/edit/{q}", {
            "token": token, "closed": "1", "blocks": "1", "account": "bybit",
            "pair": "GBPUSD", "direction": "short", "style": "EMT",
            "entry_tf": "H1", "risk": "0.5", "entry": "2026-08-29T14:30",
            "idea_text_1": "idea rewritten", "conclusions": "held to target"})
        t = store.load_trade(self.root, ServerCase.trade_id)
        self.assertEqual(t.exit_images, [])
        self.assertEqual(os.listdir(store.shots_dir(self.root, t.id)), [])

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
        # the record has not vanished — it sits in the trash under its own id
        self.assertTrue(any(name.startswith(ServerCase.trade_id)
                            for name in os.listdir(trash)))
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.get(f"/trade/{q}")
        self.assertEqual(e.exception.code, 404)

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


if __name__ == "__main__":
    unittest.main()
