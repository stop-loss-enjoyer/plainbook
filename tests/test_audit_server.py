#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The server faults of the audit of 09.11.2026, each on a record of its own:
a closed trade with no exit date, a payoff with nothing measured, a copy
refused after the trade was written, a form with no token, a figure with
separators, the addresses of Lite and the downloads another site may not
start."""
import html as htmllib
import http.client
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import reports, stats, store
from plainbook.model import Account, IdeaBlock, Plan, Playbook, Trade, Week


class Base(unittest.TestCase):
    EDITION = ""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.save_account(cls.root, Account(id="broker", name="Broker",
                                             start_balance=10000))
        store.save_account(cls.root, Account(id="second", name="Second",
                                             start_balance=5000))
        store.save_account(cls.root, Account(id="empty", name="Empty",
                                             start_balance=0))
        if cls.EDITION:
            with open(store.settings_file(cls.root), "w", encoding="utf-8",
                      newline="\n") as f:
                f.write(f"---\nedition: {cls.EDITION}\n---\n")
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

    def answer(self, path, fields=None, headers=None):
        """The code and the page, a refusal included."""
        data = (None if fields is None else
                urllib.parse.urlencode(fields, doseq=True).encode("utf-8"))
        req = urllib.request.Request(self.url(path), data=data, headers=headers or {})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read().decode("utf-8")

    def raw(self, method, path, body=None, headers=None):
        """One request, redirects not followed: the code, the headers, the body."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            r = conn.getresponse()
            return r.status, dict(r.getheaders()), r.read().decode("utf-8")
        finally:
            conn.close()

    def trade(self, trade_id, **over):
        fields = dict(id=trade_id, account="broker", pair="EURUSD", direction="long",
                      style="swing", entry_tf="H4", risk=1.0,
                      opened=datetime.strptime(trade_id[:10] + " 10:00", "%Y-%m-%d %H:%M"),
                      opened_time=True, idea=[IdeaBlock(tf="H4", text="an idea")])
        fields.update(over)
        t = Trade(**fields)
        store.save_trade(self.root, t)
        self.S.drop_cache()
        return t

    def trade_form(self, **over):
        form = {"blocks": "1", "account": "broker", "pair": "EURUSD",
                "direction": "long", "style": "swing", "entry_tf": "H4",
                "risk": "1", "entry": "2026-03-10T10:00", "idea_tf_1": "H4",
                "idea_text_1": "an idea"}
        form.update(over)
        return form

    def ids(self):
        return {t.id for t in store.all_trades(self.root, [])}


class JournalPages(Base):
    # --- 9: a closed trade with no exit date still has a page ---
    def test_closed_trade_without_an_exit_date_opens(self):
        t = self.trade("2026-03-02-01-eurusd", result="Win", pnl=120.0)
        self.assertIsNone(store.load_trade(self.root, t.id).closed)
        code, page = self.answer(f"/trade/{t.id}")
        self.assertEqual(code, 200)
        self.assertIn('class="passport"', page)
        # no time to draw, and the exit is not marked
        self.assertNotIn('class="hold"', page)

    # --- 10: the payoff tile with nothing measured, and with a loss above zero ---
    def test_statistics_without_a_measured_win_opens(self):
        self.trade("2026-03-03-01-eurusd", account="empty", result="Win", pnl=50.0,
                   closed=datetime(2026, 3, 4))
        self.trade("2026-03-03-02-eurusd", account="empty", result="Lose", pnl=-20.0,
                   closed=datetime(2026, 3, 4))
        code, page = self.answer("/stats?account=empty")
        self.assertEqual(code, 200)
        self.assertIn('class="tile', page)

    def payoff_caption(self, account, rows):
        for n, (result, pnl) in enumerate(rows, 1):
            self.trade(f"2026-03-05-0{n}-gbpusd", account=account, pair="GBPUSD",
                       result=result, pnl=pnl, closed=datetime(2026, 3, 6))
        j = self.S.journal(True)
        trades = [t for t in j.trades if t.account == account and t.pair == "GBPUSD"]
        s = stats.summary(j, trades)
        return self.S.payoff_tile(j, trades, s, None)

    def test_payoff_names_the_side_that_came_back_wrong(self):
        # no win has an R to average: the sentence about a win must not format None
        tile = self.payoff_caption("empty", [("Win", 50.0), ("Lose", -20.0)])
        self.assertIn("no win and loss to weigh", tile)

    def test_payoff_names_a_loss_that_came_back_above_zero(self):
        # a "Lose" that paid: the win is fine, the loss is the one to name
        tile = self.payoff_caption("second", [("Win", 100.0), ("Lose", 25.0)])
        self.assertIn("a loss came back at", tile)
        self.assertNotIn("a win came back", tile)

    # --- 26: an apostrophe in an id keeps the confirm a script ---
    def test_apostrophe_in_a_trade_id_keeps_delete_and_reopen_working(self):
        t = self.trade("2026-03-06-01-o'brien", result="Win", pnl=10.0,
                       closed=datetime(2026, 3, 7))
        _, page = self.answer("/trade/" + urllib.parse.quote(t.id, safe=""))
        asks = re.findall(r'onsubmit="return confirm\((.*?)\)"', page)
        self.assertEqual(len(asks), 2)
        for ask in asks:
            text = json.loads(htmllib.unescape(ask))
            self.assertIn(t.id, text)

    # --- 28: one mistyped year does not draw a link for every year ---
    def test_a_trade_and_a_week_with_a_mistyped_year_do_not_flood_the_switch(self):
        self.trade("1203-03-02-01-eurusd", opened=datetime(1203, 3, 2, 10, 0))
        store.save_week(self.root, Week(week="1002-W05"))
        self.S.drop_cache()
        code, page = self.answer("/cards")
        self.assertEqual(code, 200)
        years = re.findall(r'<div class="switch years">(.*?)</div>', page, re.S)[0]
        self.assertLess(len(re.findall(r"<a |<span", years)), 80)

    # --- 31: a plan header that is not a safe name is not made a path ---
    def test_plan_title_leaves_an_unsafe_id_alone(self):
        asked = []
        real = store.load_plan
        store.load_plan = lambda *a, **k: asked.append(a) or real(*a, **k)
        try:
            for bad in ("../outside", "a/b", ".hidden"):
                self.assertEqual(self.S.plan_title(bad), bad)
        finally:
            store.load_plan = real
        self.assertEqual(asked, [])

    # --- 41: Remove takes a pair written in lower case by hand ---
    def test_remove_pair_ignores_case(self):
        store.save_pairs(self.root, ["EURUSD", "GBPUSD"])
        path = store.pairs_file(self.root)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text.replace("GBPUSD", "gbpusd"))
        self.assertIn("gbpusd", store.all_pairs(self.root))
        self.answer("/pair/delete", {"pair": "GBPUSD"})
        self.assertEqual(store.all_pairs(self.root), ["EURUSD"])


class ReportsRead(Base):
    # a report file that is not UTF-8 is named on the pages that read it
    def test_a_report_file_that_is_not_utf8_is_named_on_its_pages(self):
        self.trade("2026-02-09-01-eurusd", result="Win", pnl=10.0,
                   closed=datetime(2026, 2, 10))
        file = reports.path(self.root, "2026-02")
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, "wb") as f:
            f.write(b"---\nupdated: 2026-02-28\n---\n\n## Conclusions\n\xcf\xf0\xe8\n")
        self.S.drop_cache()
        for path in ("/report/2026-02", "/reports"):
            code, page = self.answer(path)
            self.assertEqual(code, 200, path)
            self.assertIn("2026-02.md</code>: the file is not UTF-8", page, path)


class Forms(Base):
    # --- 11: a copy refused before anything is written ---
    def test_a_refused_copy_leaves_nothing_written_on_create(self):
        before = self.ids()
        code, page = self.answer("/new", self.trade_form(
            dup=["second"], dup_risk_second="0", pair="USDCHF"))
        self.assertEqual(code, 400)
        self.assertIn('<h2>Not saved</h2>', page)
        self.assertEqual(self.ids(), before)

    def test_a_refused_copy_leaves_the_trade_as_it_was_on_edit(self):
        t = self.trade("2026-03-09-01-audusd", pair="AUDUSD")
        before = self.ids()
        code, _ = self.answer(f"/edit/{t.id}", self.trade_form(
            pair="AUDUSD", risk="2", entry="2026-03-09T10:00",
            dup=["second"], dup_risk_second="0"))
        self.assertEqual(code, 400)
        self.assertEqual(store.load_trade(self.root, t.id).risk, 1.0)
        self.assertEqual(self.ids(), before)

    def test_a_good_copy_is_still_written(self):
        code, _ = self.answer("/new", self.trade_form(
            dup=["second"], dup_risk_second="0.5", pair="NZDJPY"))
        self.assertEqual(code, 200)
        mine = [t for t in store.all_trades(self.root, []) if t.pair == "NZDJPY"]
        self.assertEqual(sorted((t.account, t.risk) for t in mine),
                         [("broker", 1.0), ("second", 0.5)])

    # --- 13: an account file that does not read is not written over ---
    def test_a_new_account_does_not_write_over_an_unreadable_file(self):
        path = store.account_path(self.root, "ghost") if hasattr(
            store, "account_path") else os.path.join(
                self.root, "journal", "accounts", "ghost.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        broken = "---\nid: ghost\nstart balance: lots\n---\nmy own words\n"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(broken)
        self.S.drop_cache()
        self.answer("/account/new", {"id": "ghost", "start": "100"})
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), broken)

    # --- 27: no token, and the record is not answered "Not saved" ---
    def test_a_trade_saved_without_a_token_is_answered_saved(self):
        t = self.trade("2026-03-11-01-usdcad", pair="USDCAD")
        code, page = self.answer(f"/edit/{t.id}", self.trade_form(
            pair="USDCAD", risk="1.5", entry="2026-03-11T10:00"))
        self.assertEqual(code, 200)
        self.assertNotIn('<h2>Not saved</h2>', page)
        self.assertEqual(store.load_trade(self.root, t.id).risk, 1.5)

    def test_a_blank_token_does_not_refuse_a_new_trade(self):
        code, page = self.answer("/new", self.trade_form(token="", pair="EURNZD"))
        self.assertEqual(code, 200)
        self.assertEqual(len([t for t in store.all_trades(self.root, [])
                              if t.pair == "EURNZD"]), 1)

    def test_a_plan_and_a_note_saved_without_a_token_are_answered_saved(self):
        code, page = self.answer("/plan/new", {
            "title": "no token", "pair": "EURUSD", "narrative": "bullish",
            "from": "2026-03-02", "blocks": "0"})
        self.assertEqual(code, 200)
        self.assertNotIn('<h2>Not saved</h2>', page)
        code, page = self.answer("/note/new", {
            "title": "no token note", "date": "2026-03-02", "blocks": "0"})
        self.assertEqual(code, 200)
        self.assertNotIn('<h2>Not saved</h2>', page)

    # --- 29, 30: the rules and limits of a playbook come back as typed ---
    def test_a_rule_ending_in_a_star_keeps_its_words(self):
        pairs = self.S.rule_pairs({"r": ["- [ ] **stop at 2***", "*target 3R*"],
                                   "r_detail": ["only on H4", "why"]}, "r")
        self.assertEqual(pairs, [("stop at 2", "only on H4"), ("target 3R", "why")])
        data = {"name": ["Stars"], "status": ["active"], "setups": ["1"],
                "setup_name_1": ["Main"], "setup_rule_1": ["stop at 2*"],
                "setup_rule_1_detail": ["only on H4"]}
        p = self.S.playbook_from_form(data, Playbook(id="stars"))
        store.save_playbook(self.root, p)
        again = store.load_playbook(self.root, "stars")
        self.assertEqual([(r.text, r.detail) for r in again.setups[0].rules],
                         [("stop at 2", "only on H4")])

    def test_a_limit_name_with_a_colon_is_refused(self):
        data = {"name": ["Limits"], "limit_kind": ["other"],
                "limit_name": ["risk: news days"], "limit_value": ["0.5%"]}
        with self.assertRaises(self.S.RecordError) as e:
            self.S.playbook_from_form(data, Playbook(id="limits"))
        self.assertIn("colon", str(e.exception))
        code, page = self.answer("/playbook/new", {
            "name": "Limits", "status": "active", "setups": "1",
            "limit_kind": "other", "limit_name": "risk: news days",
            "limit_value": "0.5%"})
        self.assertEqual(code, 400)
        self.assertIn('<h2>Not saved</h2>', page)

    # --- 36, Decision 3: what a figure takes ---
    def test_figure_refuses_a_huge_amount_and_a_separator_pair(self):
        figure = self.S.figure
        self.assertEqual(figure("1e15", "PnL"), 1e15)
        for text in ("1e16", "-2e15", "1000000000000001"):
            with self.assertRaises(self.S.RecordError, msg=text):
                figure(text, "PnL")
        for text in ("1,234.56", "1.234,56", "$1,234.50"):
            with self.assertRaises(self.S.RecordError, msg=text) as e:
                figure(text, "PnL")
            self.assertIn("PnL", str(e.exception))
            self.assertIn("without separators", str(e.exception))
        self.assertEqual(figure("12,5"), 12.5)
        self.assertEqual(figure("1 234,5"), 1234.5)
        self.assertEqual(figure("1234.56"), 1234.56)

    def test_a_risk_in_money_with_a_comma_and_a_point_is_refused(self):
        with self.assertRaises(self.S.RecordError) as e:
            self.S.parse_risk("1,250.50$", 10000)
        self.assertIn("without separators", str(e.exception))
        self.assertEqual(self.S.parse_risk("2,5", 10000), 2.5)

    def test_a_pnl_of_two_huge_amounts_is_refused_with_a_page(self):
        t = self.trade("2026-03-12-01-eurgbp", pair="EURGBP")
        code, page = self.answer(f"/close/{t.id}", {
            "result": "Win", "pnl": "1e300", "exit": "2026-03-13T10:00"})
        self.assertEqual(code, 400)
        self.assertIn('<h2>Not saved</h2>', page)
        self.assertTrue(store.load_trade(self.root, t.id).is_open)

    # --- 39: a way back that is not ASCII is not sent as a header ---
    def test_a_non_ascii_way_back_is_replaced(self):
        body = urllib.parse.urlencode({"stop_edge": "1.3", "back": "/été"})
        code, headers, _ = self.raw("POST", "/settings/stop-edge", body, {
            "Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(code, 303)
        self.assertTrue(headers["Location"].startswith("/stats?said="), headers)
        self.assertTrue(headers["Location"].endswith("#past-stop"))
        self.assertTrue(headers["Location"].isascii())

    # --- 40: another site may not start the downloads of the records ---
    def test_other_sites_may_not_download_the_records(self):
        self.trade("2026-03-13-01-eurusd", result="Win", pnl=10.0,
                   closed=datetime(2026, 3, 14))
        foreign = {"Sec-Fetch-Site": "cross-site"}
        for path in ("/export.csv", "/share/journal?file=1", "/share/stats?file=1"):
            self.assertEqual(self.raw("GET", path, headers=foreign)[0], 403, path)
            self.assertEqual(self.raw("GET", path)[0], 200, path)
            self.assertEqual(self.raw("GET", path, headers={
                "Sec-Fetch-Site": "none"})[0], 200, path)
        # the preview of a share is a page to look at, not a download
        self.assertEqual(self.raw("GET", "/share/journal", headers=foreign)[0], 200)


class RiskHint(Base):
    SCRIPT = r"""
const fs = require('fs');
const src = fs.readFileSync(0, 'utf8');
const box = {checked: process.argv[1] === 'unknown', addEventListener(){}};
const entry = {value: process.argv[2], addEventListener(){}};
const form = {dataset: {balances: JSON.stringify({a: {start: 100,
  events: [['2026-03-01T00:00', false, true, 50]]}}), signs: '{}'}};
global.document = {querySelector: s =>
  s === '[name=entry_unknown]' ? box : s === '[name=entry]' ? entry :
  s.startsWith('form[') ? form : {addEventListener(){}, value: 'a'},
  querySelectorAll: () => ({forEach(){}})};
global.Proxy = Proxy;
eval(src.replace(/show_risks\(\);\s*$/, '') + '; console.log(balance_of("a"))');
"""

    def run_hint(self, unknown, entry):
        if not shutil.which("node"):
            self.skipTest("node is not installed")
        out = subprocess.run(["node", "-e", self.SCRIPT, "unknown" if unknown else "",
                              entry], input=self.S.RISK_HINT_SCRIPT, text=True,
                             capture_output=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return float(out.stdout.strip())

    # --- 25: the hint decides "timed" the way the server does ---
    def test_the_hint_follows_the_hour_not_known_box(self):
        # an adjustment-like event at 00:00 of the day itself: counted when the
        # entry has an hour that is known, not when the hour is not known
        known = self.run_hint(False, "2026-03-01T00:00")
        unknown = self.run_hint(True, "2026-03-01T00:00")
        self.assertNotEqual(known, unknown)

    def test_the_hint_script_listens_to_the_box(self):
        self.assertIn("entry_unknown", self.S.RISK_HINT_SCRIPT)
        self.assertRegex(self.S.RISK_HINT_SCRIPT,
                         r"unknown_box\.addEventListener\('change', show_risks\)")


class LiteAddresses(Base):
    EDITION = "lite"

    # --- 37: an encoded slash does not step round the hidden addresses ---
    def test_an_encoded_slash_does_not_reach_a_hidden_page(self):
        plain = self.answer("/playbook/x")[1]
        for path in ("/%2Fplaybook/x", "//playbook/x", "/playbook%2Fx", "/%2Fcards",
                     "/note/./x"):
            code, page = self.answer(path)
            self.assertEqual(page, plain, path)
        self.assertNotEqual(plain, self.answer("/accounts")[1])

    def test_an_encoded_slash_post_is_a_hidden_post(self):
        k = Plan(id="2026-03-02-eurusd", title="hidden", pair="EURUSD",
                 narrative="bullish", day=datetime(2026, 3, 2))
        store.save_plan(self.root, k)
        code, headers, body = self.raw(
            "POST", f"/%2Fplan/{k.id}/delete", "x=1",
            {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(code, 303, body)
        self.assertTrue(headers["Location"].startswith("/turned-off"), headers)


if __name__ == "__main__":
    unittest.main()
