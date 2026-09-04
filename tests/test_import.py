#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The import of old trades from a table."""
import csv
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))

import import_csv
from plainbook import store
from plainbook.model import Account

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
       b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

HEADER = ["Name", "Account", "Pair", "Direction", "Style", "Date", "Result",
          "PnL", "Risk", "TF", "Idea", "Files", "Notion id"]
ROWS = [
    ["Trade 1", "Bybit", "EUR/USD", "Long", "swing", "August 3, 2026 9:15 AM → August 4, 2026 6:00 PM",
     "Win", "$1,250.50", "1%", "H4", "sweep of the high", "one.png (https://x/one.png)", "n1"],
    ["Trade 2", "Bybit", "GBPUSD", "sell", "EMT", "2026-08-05 10:00", "Loss", "-300", "", "H1",
     "", "", "n2"],
    ["Trade 3", "FTMO 100k", "XAUUSD", "short", "EMT prop", "06.08.2026", "Break even", "", "0.5",
     "", "", "", "n3"],
]


class ImportCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pb-import-")
        os.makedirs(os.path.join(self.root, "journal"))
        store.save_account(self.root, Account(id="broker", start_balance=10000))
        store.save_account(self.root, Account(id="prop-100k", start_balance=100000))
        self.pictures = os.path.join(self.root, "export", "deep")
        os.makedirs(self.pictures)
        with open(os.path.join(self.pictures, "one.png"), "wb") as f:
            f.write(PNG)
        self.csv = os.path.join(self.root, "trades.csv")
        self.write_csv(ROWS)

    def tearDown(self):
        shutil.rmtree(self.root)

    def write_csv(self, rows):
        with open(self.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(HEADER)
            w.writerows(rows)

    def run_import(self, *extra):
        argv = [self.csv, "--root", self.root, "--account-column", "Account",
                "--accounts", "Bybit=broker,FTMO 100k=prop-100k",
                "--pair", "Pair", "--direction", "Direction", "--style", "Style",
                "--entry", "Date", "--exit", "Date", "--result", "Result",
                "--pnl", "PnL", "--risk", "Risk", "--entry-tf", "TF",
                "--idea", "Idea", "--id", "Notion id", "--pictures", "Files",
                "--pictures-dir", os.path.join(self.root, "export")] + list(extra)
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                code = import_csv.main(argv)
            except SystemExit as e:                 # a refusal, with its reason
                code = e
        return code, out.getvalue()

    def test_every_row_becomes_a_trade_the_interface_could_have_written(self):
        code, out = self.run_import()
        self.assertEqual(code, 0)
        self.assertIn("3 rows read, 3 written, 0 already in the journal", out)
        trades = {t.notion_id: t for t in store.all_trades(self.root)}
        self.assertEqual(set(trades), {"n1", "n2", "n3"})
        one = trades["n1"]
        self.assertEqual(one.account, "broker")
        self.assertEqual(one.pair, "EURUSD")
        self.assertEqual(one.direction, "long")
        self.assertEqual(one.opened, datetime(2026, 8, 3, 9, 15))
        self.assertTrue(one.opened_time)
        self.assertEqual(one.closed, datetime(2026, 8, 4, 18, 0))
        self.assertEqual(one.result, "Win")
        self.assertEqual(one.pnl, 1250.5)
        self.assertEqual(one.risk, 1.0)
        self.assertEqual(one.idea[0].tf, "H4")
        self.assertEqual(one.idea[0].text, "sweep of the high")
        # the picture found under the export folder, at any depth
        self.assertEqual(one.idea[0].images, ["shots/idea-01-01.png"])
        self.assertTrue(os.path.exists(os.path.join(
            store.shots_dir(self.root, one.id), "idea-01-01.png")))
        two = trades["n2"]
        self.assertEqual(two.direction, "short")
        self.assertEqual(two.result, "Lose")
        self.assertEqual(two.risk, 1.0)                # the default
        self.assertEqual(two.closed, datetime(2026, 8, 5, 10, 0))  # no exit: the entry
        three = trades["n3"]
        self.assertEqual(three.account, "prop-100k")
        self.assertEqual(three.result, "BE")
        self.assertEqual(three.pnl, 0.0)               # a break-even without a figure
        self.assertEqual(three.risk, 0.5)
        # the words of the table are offered by the form from now on
        self.assertIn("EMT prop", store.all_words(self.root, "styles"))
        self.assertIn("XAUUSD", store.all_pairs(self.root))
        # the ids count the day, as the interface does
        self.assertTrue(one.id.startswith("2026-08-03-01-"))
        # the summary carries figures, not the rows
        self.assertIn("broker: 2 trades, PnL +950.50", out)
        self.assertNotIn("sweep of the high", out)

    def test_a_second_run_writes_nothing(self):
        self.run_import()
        code, out = self.run_import()
        self.assertEqual(code, 0)
        self.assertIn("3 rows read, 0 written, 3 already in the journal", out)
        self.assertEqual(len(store.all_trades(self.root)), 3)

    def test_a_dry_run_reads_everything_and_writes_nothing(self):
        code, out = self.run_import("--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("3 rows read, 3 would write", out)
        self.assertEqual(store.all_trades(self.root), [])

    def test_one_bad_row_stops_the_whole_run(self):
        rows = [list(r) for r in ROWS]
        rows[1][6] = "maybe"                          # not a result
        self.write_csv(rows)
        code, out = self.run_import()
        self.assertIsInstance(code, SystemExit)
        self.assertIn("row 3", out)
        self.assertIn("nothing was written", str(code))
        self.assertEqual(store.all_trades(self.root), [])

    def test_an_account_the_journal_does_not_have_is_refused(self):
        rows = [list(r) for r in ROWS]
        rows[0][1] = "Somewhere else"
        self.write_csv(rows)
        code, _ = self.run_import()
        self.assertIsInstance(code, SystemExit)
        self.assertIn("somewhere else", str(code).lower())
        self.assertEqual(store.all_trades(self.root), [])

    def test_a_missing_column_is_named(self):
        code, _ = self.run_import("--note", "Nope")
        self.assertIsInstance(code, SystemExit)
        self.assertIn("Nope", str(code))


if __name__ == "__main__":
    unittest.main()
