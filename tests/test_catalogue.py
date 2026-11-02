#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The catalogue of instruments on the Accounts tab: ticked ones join the
owner's list of pairs, nothing else is touched, and the ones the list holds
stand ticked and cannot be sent again."""
import importlib
import os
import sys
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS))

from plainbook import flags, store
from plainbook.model import Account


class Catalogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.make_layout(cls.root)
        store.save_account(cls.root, Account(id="broker", name="Broker",
                                             start_balance=10000))
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

    def setUp(self):
        store.save_pairs(self.root, ["EURUSD.PRO"])

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return r.read().decode("utf-8")

    def post(self, path, fields):
        data = urllib.parse.urlencode(fields, doseq=True).encode("utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data)
        with urllib.request.urlopen(req) as r:
            return r.read().decode("utf-8")

    def test_ticked_ones_join_the_list(self):
        self.post("/pair/catalogue", {"pair": ["SOLUSD", "USDTRY"], "at": "pair-catalogue"})
        self.assertEqual(store.all_pairs(self.root), ["EURUSD.PRO", "SOLUSD", "USDTRY"])

    def test_only_the_catalogue_is_taken(self):
        self.post("/pair/catalogue", {"pair": ["SOLUSD", "NOT A PAIR", "<x>"]})
        self.assertEqual(store.all_pairs(self.root), ["EURUSD.PRO", "SOLUSD"])

    def test_nothing_ticked_is_said(self):
        page = self.post("/pair/catalogue", {"at": "pair-catalogue"})
        self.assertIn("nothing was ticked", page)
        self.assertEqual(store.all_pairs(self.root), ["EURUSD.PRO"])

    def test_the_page_offers_every_instrument(self):
        store.save_pairs(self.root, ["XAUUSD"])
        page = self.get("/accounts")
        for _, symbols in flags.CATALOGUE:
            for s in symbols:
                self.assertIn(f'value="{s}"', page)
        self.assertIn('value="XAUUSD" checked disabled', page)
        # the suggestions of the field leave out what the list has
        suggestions = page.split('<datalist id="pair-suggestions">')[1].split("</datalist>")[0]
        self.assertIn('<option value="BTCUSD">', suggestions)
        self.assertNotIn('"XAUUSD"', suggestions)

    def test_the_pair_field_of_a_trade_suggests_the_catalogue_after_the_list(self):
        """A fresh journal has no pairs of its own, and its first trade is
        still suggested one once a letter is typed."""
        store.save_pairs(self.root, ["XAUUSD"])
        for path in ("/new", "/plan/new"):
            page = self.get(path)
            options = page.split('<div class="options" hidden>')[1].split("</div>")[0]
            own = options.index('data-value="XAUUSD"')
            more = options.index('data-more data-value="BTCUSD"')
            self.assertLess(own, more)                  # the owner's list first
            self.assertEqual(options.count('data-value="XAUUSD"'), 1)
            self.assertNotIn('data-more data-value="XAUUSD"', options)

    def test_a_grey_winrate_says_why_on_hover(self):
        s = self.S.stats.Summary()
        s.wins, s.losses = 2, 1
        cell = self.S.figures_cells(s)
        self.assertIn('title="3 trades won or lost, fewer than 5', cell)
        s.wins = 4
        self.assertNotIn("title=", self.S.figures_cells(s))


if __name__ == "__main__":
    unittest.main()
