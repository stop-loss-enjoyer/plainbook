#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The import of old trades from a table."""
import csv
import io
import os
import shutil
import subprocess
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
          "PnL", "Risk", "TF", "Idea", "Files", "Notion id", "Lessons"]
ROWS = [
    ["Trade 1", "Bybit", "EUR/USD", "Long", "swing", "August 3, 2026 9:15 AM → August 4, 2026 6:00 PM",
     "Win", "$1,250.50", "1%", "H4", "sweep of the high", "one.png (https://x/one.png)", "n1", "held it to the target"],
    ["Trade 2", "Bybit", "GBPUSD", "sell", "EMT", "2026-08-05 10:00", "Loss", "-300", "", "H1",
     "", "", "n2", ""],
    ["Trade 3", "FTMO 100k", "XAUUSD", "short", "EMT prop", "06.08.2026", "Break even", "", "0.5",
     "", "", "", "n3", ""],
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
                "--conclusions", "Lessons",
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
        self.assertEqual(one.conclusions, "held it to the target")
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


class GuardCase(unittest.TestCase):
    """The two tools the documents lean on, shown to fire and to pass."""
    TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")

    def run_tool(self, name, cwd, *args):
        done = subprocess.run([sys.executable, os.path.join(self.TOOLS, name), *args],
                              cwd=cwd, capture_output=True, text=True)
        return done.returncode, done.stdout

    def test_check_public_names_each_kind_of_leak_and_passes_a_clean_tree(self):
        tmp = tempfile.mkdtemp(prefix="pb-guard-")
        try:
            code, out = self.run_tool("check_public.py", tmp)
            self.assertEqual(code, 0, out)
            self.assertIn("clean:", out)
            leaks = {"a.md": "a word in \u0420\u0443\u0441\u0441\u043a\u0438\u0439\n",
                     # pieced together so that the guard does not fire on this file
                     "b.py": "path = '/ho" + "me/somebody/x'\n",
                     "c.txt": "id " + "0123456789abcdef" * 2 + "\n",
                     "d.md": "one \u2014 two\n"}
            for name, text in leaks.items():
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
                    f.write(text)
            code, out = self.run_tool("check_public.py", tmp)
            self.assertEqual(code, 1)
            for word in ("cyrillic", "home path", "foreign id", "long dash"):
                self.assertIn(f"FOUND: ", out)
                self.assertIn(word, out, word)
        finally:
            shutil.rmtree(tmp)

    def test_check_journal_names_a_broken_record_and_reads_a_demo_clean(self):
        tmp = tempfile.mkdtemp(prefix="pb-check-")
        try:
            code, out = self.run_tool("demo_journal.py", tmp, os.path.join(tmp, "demo"))
            self.assertEqual(code, 0, out)
            demo = os.path.join(tmp, "demo")
            code, out = self.run_tool("check_journal.py", tmp, demo)
            self.assertEqual(code, 0, out)
            self.assertIn("clean:", out)
            self.assertTrue(any(t.is_open for t in store.all_trades(demo)))
            folder = store.trade_dir(demo, "2026-01-05-01-eurusd")
            os.makedirs(folder)
            with open(os.path.join(folder, "trade.md"), "w", encoding="utf-8") as f:
                f.write("---\nid: 2026-01-05-01-eurusd\naccount: broker\npair: EURUSD\n"
                        "direction: long\nstyle: swing\nrisk %: 1\nentry: 05.01.2026\n---\n")
            code, out = self.run_tool("check_journal.py", tmp, demo)
            self.assertEqual(code, 1)
            self.assertIn("CANNOT READ", out)
            self.assertIn("2026-01-05-01-eurusd/trade.md", out)
            self.assertIn("1 record left out", out)
        finally:
            shutil.rmtree(tmp)


class AttachCase(unittest.TestCase):
    def test_trades_of_the_styles_since_the_date_are_tied(self):
        from plainbook.model import Playbook, Rule, Setup, Trade
        import subprocess, sys
        with tempfile.TemporaryDirectory() as root:
            store.save_account(root, Account(id="broker", start_balance=1000))
            store.save_playbook(root, Playbook(
                id="pull", name="Pull", styles=["swing"], version="1.0",
                since=datetime(2026, 8, 15),
                setups=[Setup(rules=[Rule(1, "one")])]))
            def trade(n, style, day, **kw):
                return Trade(id=f"2026-08-{day:02d}-{n:02d}-eurusd", account="broker",
                             pair="EURUSD", direction="long", style=style,
                             opened=datetime(2026, 8, day), **kw)
            for t in (trade(1, "swing", 14), trade(1, "swing", 15), trade(2, "EMT", 15),
                      trade(1, "swing", 20, playbook="other", playbook_version="2")):
                store.save_trade(root, t)
            tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "tools", "attach_playbook.py")
            dry = subprocess.run([sys.executable, tool, root, "pull"],
                                 capture_output=True, text=True).stdout
            self.assertIn("trades to tie: 1", dry)
            self.assertEqual([t.playbook for t in store.all_trades(root)],
                             ["", "", "", "other"])
            done = subprocess.run([sys.executable, tool, root, "pull", "--apply"],
                                  capture_output=True, text=True).stdout
            self.assertIn("written: 1", done)
            tied = {t.id: (t.playbook, t.playbook_version) for t in store.all_trades(root)}
            self.assertEqual(tied["2026-08-15-01-eurusd"], ("pull", ""))   # no tick, no version
            with open(os.path.join(store.trade_dir(root, "2026-08-15-01-eurusd"),
                                   "trade.md")) as f:
                self.assertNotIn("deviations", f.read())
            self.assertEqual(tied["2026-08-14-01-eurusd"], ("", ""))
            self.assertEqual(tied["2026-08-15-02-eurusd"], ("", ""))
            self.assertEqual(tied["2026-08-20-01-eurusd"], ("other", "2"))
            again = subprocess.run([sys.executable, tool, root, "pull", "--apply"],
                                   capture_output=True, text=True).stdout
            self.assertIn("written: 0", again)
