#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Counterparts that were missing: the account of a trade that has gone, the
note of an imported trade, the entries of a playbook review, the conclusions
of a report in Search, the name and currency of an account."""
import importlib
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS))
sys.path.insert(0, TESTS)

from formpost import form_fields
from plainbook import store
from plainbook.model import Account, IdeaBlock, Playbook, Rule, Setup, Trade

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "05572bd6a20000000049454e44ae426082")


class AuditDepsCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.save_account(cls.root, Account(id="broker", name="Broker",
                                             start_balance=10000))
        store.save_account(cls.root, Account(id="other", name="Other",
                                             start_balance=5000))
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

    def post(self, path, fields, code=None):
        data = urllib.parse.urlencode(fields, doseq=True).encode("utf-8")
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url(path), data=data)) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            e.close()
            return e.code, body

    def trade(self, trade_id, **over):
        folder = store.trade_dir(self.root, trade_id)
        os.makedirs(folder, exist_ok=True)
        fields = dict(id=trade_id, account="broker", pair="EURUSD",
                      direction="long", style="swing", entry_tf="H4", risk=1.0,
                      opened=datetime(2026, 8, 29, 14, 30), opened_time=True,
                      idea=[IdeaBlock(tf="H4", text="an idea")])
        fields.update(over)
        t = Trade(**fields)
        store.save_trade(self.root, t)
        self.S.drop_cache()
        return t

    # --- an account that has gone ---
    def test_the_account_of_a_trade_that_has_gone_is_kept_in_the_form(self):
        tid = "2026-08-29-01-eurusd"
        self.trade(tid, account="gone")
        path = f"/edit/{urllib.parse.quote(tid)}"
        html = self.get(path)
        self.assertIn('<option value="gone" selected>', html)
        fields = form_fields(html, path)
        self.assertEqual(fields["account"], ["gone"])
        code, body = self.post(path, fields)
        self.assertEqual(code, 400)
        self.assertIn("no account", body)
        self.assertEqual(store.load_trade(self.root, tid).account, "gone")

    # --- the note ---
    def test_the_note_is_drawn_when_there_is_one_and_cleared_when_blank(self):
        plain = self.trade("2026-08-29-02-gbpusd", pair="GBPUSD")
        html = self.get(f"/edit/{plain.id}")
        self.assertNotIn('name="note"', html)
        tid = "2026-08-29-03-usdjpy"
        self.trade(tid, pair="USDJPY", note="from the old sheet")
        path = f"/edit/{tid}"
        fields = form_fields(self.get(path), path)
        self.assertEqual(fields["note"], ["from the old sheet"])
        fields["note"] = ["corrected"]
        self.assertEqual(self.post(path, fields)[0], 200)
        self.assertEqual(store.load_trade(self.root, tid).note, "corrected")
        fields["note"] = [""]
        self.post(path, fields)
        self.assertEqual(store.load_trade(self.root, tid).note, "")
        # a form that does not draw it leaves it alone
        self.trade("2026-08-29-04-audjpy", pair="AUDJPY", note="kept")
        path = "/edit/2026-08-29-04-audjpy"
        fields = form_fields(self.get(path), path)
        fields.pop("note")
        self.post(path, fields)
        self.assertEqual(store.load_trade(self.root, "2026-08-29-04-audjpy").note, "kept")

    # --- the review of a playbook ---
    def test_a_review_entry_is_corrected_and_its_picture_taken_off(self):
        store.save_playbook(self.root, Playbook(
            id="pull", name="Pullback", styles=["swing"], version="1.0",
            setups=[Setup(rules=[Rule(1, "Level")])]))
        folder = store.playbook_dir(self.root, "pull")
        os.makedirs(os.path.join(folder, store.SHOTS), exist_ok=True)
        for n in ("review-01.png", "review-02.png"):
            with open(os.path.join(folder, store.SHOTS, n), "wb") as f:
                f.write(PNG)
        p = store.load_playbook(self.root, "pull")
        p.review = ("**01.09.2026**: a typo here\n![](shots/review-01.png)\n\n"
                    "**02.09.2026**: second\n![](shots/review-02.png)")
        store.save_playbook(self.root, p)
        self.S.drop_cache()
        path = "/playbook/pull/edit"
        fields = form_fields(self.get(path), path)
        self.assertIn("a typo here", fields["review"][0])
        # saved as drawn, nothing changes
        self.assertEqual(self.post(path, fields)[0], 200)
        self.assertEqual(store.load_playbook(self.root, "pull").review, p.review)
        # a slip put right, the first picture taken off
        fields["review"] = [fields["review"][0].replace("a typo here", "fixed")]
        fields["have_review"] = ["shots/review-02.png"]
        self.assertEqual(self.post(path, fields)[0], 200)
        q = store.load_playbook(self.root, "pull")
        self.assertIn("fixed", q.review)
        self.assertNotIn("review-01.png", q.review)
        self.assertIn("review-02.png", q.review)
        self.assertEqual(sorted(os.listdir(os.path.join(folder, store.SHOTS))),
                         ["review-02.png"])
        # an entry taken out whole
        fields["review"] = [""]
        fields["have_review"] = []
        self.post(path, fields)
        self.assertEqual(store.load_playbook(self.root, "pull").review, "")

    # --- search reads the reports ---
    def test_search_finds_the_conclusions_of_a_report(self):
        self.trade("2026-09-02-01-eurusd", result="Win", pnl=50.0,
                   closed=date(2026, 9, 3))
        self.assertEqual(self.post("/report/2026-09",
                                   {"conclusions": "Zebraword lesson"})[0], 200)
        html = self.get("/search?q=zebraword")
        self.assertIn('href="/report/2026-09"', html)
        self.assertIn("1 record", html)

    # --- name and currency ---
    def test_the_name_and_currency_of_an_account_are_corrected(self):
        path = "/account/other/rules"
        fields = form_fields(self.get(path), path)
        self.assertEqual((fields["name"], fields["currency"]), (["Other"], ["USD"]))
        fields["name"], fields["currency"] = ["Second"], ["eur"]
        self.assertEqual(self.post(path, fields)[0], 200)
        a = store.all_accounts(self.root)["other"]
        self.assertEqual((a.name, a.currency, a.start_balance), ("Second", "EUR", 5000))
        fields["currency"] = ["no way!"]
        fields["name"] = ["Third"]
        self.assertEqual(self.post(path, fields)[0], 400)
        a = store.all_accounts(self.root)["other"]
        self.assertEqual((a.name, a.currency), ("Second", "EUR"))


if __name__ == "__main__":
    unittest.main()
