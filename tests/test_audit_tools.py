#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The tools, the desktop files and the workflows after the audit of
09.11.2026: the README rewriter that wants a tag, the demo that will not
write over records, the importer that settles the order of a date and refuses
a comma it cannot read, the checker that names a broken version and a trade
with no account, the toggle, the manifest of the sdist and the workflows.

The shell, Node and YAML files are read as text and, where a parser is on the
machine, parsed; the sdist does not carry desktop/ or .github/, so those tests
skip there."""
import argparse
import csv
import io
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import check_journal
import import_csv
import pypi_readme
import screenshots
from plainbook import store
from plainbook.model import Account, Playbook, Rule, Setup, Trade

TOOLS = os.path.join(ROOT, "tools")
DESKTOP = os.path.join(ROOT, "desktop")
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def code_of(text):
    """A workflow without its comment lines: the comments name the rules in
    the same words the rules are asserted in."""
    return "\n".join(line for line in text.split("\n")
                     if not line.lstrip().startswith("#"))


def run_tool(name, *args, cwd=None):
    done = subprocess.run([sys.executable, os.path.join(TOOLS, name), *args],
                          cwd=cwd, capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


class PypiReadmeTag(unittest.TestCase):
    """Item 1: only a tag may get as far as the file."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pb-readme-")
        self.path = os.path.join(self.dir, "README.md")
        self.text = "![a](docs/journal.png)\n[g](GUIDE.md)\n[x](https://example.com)\n"
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(self.text)
        self.saved = pypi_readme.README
        pypi_readme.README = self.path

    def tearDown(self):
        pypi_readme.README = self.saved
        shutil.rmtree(self.dir)

    def run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                pypi_readme.main(list(argv))
                return None, out.getvalue()
            except SystemExit as e:
                return e, out.getvalue()

    def test_anything_but_a_tag_prints_the_usage_and_leaves_the_file(self):
        for bad in ("--help", "-h", "latest", "1.9.0", "v1.9", "v1.9.0 ", "v1.9.0.1",
                    "v1.9.0-rc1", "", "../v1.9.0"):
            refused, _ = self.run_main(bad)
            self.assertIsNotNone(refused, bad)
            self.assertIn("usage: pypi_readme.py", str(refused))
            self.assertEqual(read_back(self.path), self.text, bad)
        refused, _ = self.run_main()
        self.assertIn("usage", str(refused))
        refused, _ = self.run_main("v1.9.0", "v1.9.1")
        self.assertIn("usage", str(refused))
        self.assertEqual(read_back(self.path), self.text)

    def test_a_tag_rewrites_the_file_and_says_how_much(self):
        refused, out = self.run_main("v12.3.45")
        self.assertIsNone(refused)
        self.assertIn("2 lines rewritten for v12.3.45", out)
        done = read_back(self.path)
        self.assertIn("raw.githubusercontent.com/stop-loss-enjoyer/plainbook/v12.3.45/docs/journal.png",
                      done)
        self.assertIn("(https://example.com)", done)

    def test_the_publish_workflow_passes_a_tag_of_that_shape(self):
        # publish.yml hands the tag of the release it is run for
        if not os.path.isdir(WORKFLOWS):
            self.skipTest("no .github in this tree")
        text = read(".github", "workflows", "publish.yml")
        self.assertIn('python tools/pypi_readme.py "$TAG"', text)
        # the releases of this project are named vX.Y.Z (AGENTS.md section 7)
        self.assertTrue(pypi_readme.TAG.fullmatch("v1.14.0"))


def read_back(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class DemoWontWriteOverRecords(unittest.TestCase):
    """Item 22."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pb-demo-guard-")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_a_folder_with_a_record_is_refused_and_force_goes_through(self):
        mine = os.path.join(self.dir, "mine")
        store.save_account(mine, Account(id="real", start_balance=5000))
        store.save_trade(mine, Trade(id="2026-01-05-01-eurusd", account="real",
                                     pair="EURUSD", direction="long", style="swing",
                                     opened=datetime(2026, 1, 5)))
        record = os.path.join(store.trade_dir(mine, "2026-01-05-01-eurusd"), "trade.md")
        before = read_back(record)
        shown = sorted(os.listdir(os.path.join(mine, "journal")))
        code, out = run_tool("demo_journal.py", mine)
        self.assertEqual(code, 1, out)
        self.assertIn("already has records", out)
        self.assertEqual(sorted(os.listdir(os.path.join(mine, "journal"))), shown)
        self.assertEqual(len(store.all_trades(mine)), 1)
        self.assertEqual(read_back(record), before)
        code, out = run_tool("demo_journal.py", mine, "--force")
        self.assertEqual(code, 0, out)
        self.assertGreater(len(store.all_trades(mine)), 1)

    def test_an_owner_file_alone_counts_as_records(self):
        mine = os.path.join(self.dir, "mine")
        os.makedirs(os.path.join(mine, "journal"))
        with open(os.path.join(mine, "journal", "settings.md"), "w") as f:
            f.write("edition: lite\n")
        code, out = run_tool("demo_journal.py", mine)
        self.assertEqual(code, 1, out)
        self.assertEqual(os.listdir(os.path.join(mine, "journal")), ["settings.md"])

    def test_an_empty_folder_and_the_empty_layout_of_the_repository_pass(self):
        fresh = os.path.join(self.dir, "fresh")
        code, out = run_tool("demo_journal.py", fresh)
        self.assertEqual(code, 0, out)
        layout = os.path.join(self.dir, "layout")
        os.makedirs(os.path.join(layout, "journal", "trades"))
        open(os.path.join(layout, "journal", "trades", ".gitkeep"), "w").close()
        code, out = run_tool("demo_journal.py", layout)
        self.assertEqual(code, 0, out)

    def test_the_demo_writes_a_second_time_only_by_force(self):
        again = os.path.join(self.dir, "again")
        self.assertEqual(run_tool("demo_journal.py", again)[0], 0)
        self.assertEqual(run_tool("demo_journal.py", again)[0], 1)


HEADER = ["Account", "Pair", "Direction", "Style", "Date", "Exit", "Result",
          "PnL", "Risk", "Id"]


class ImportCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pb-import-audit-")
        os.makedirs(os.path.join(self.root, "journal"))
        store.save_account(self.root, Account(id="broker", start_balance=10000))
        self.csv = os.path.join(self.root, "trades.csv")

    def tearDown(self):
        shutil.rmtree(self.root)

    def table(self, rows):
        with open(self.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(HEADER)
            w.writerows(rows)

    def row(self, date, pnl="100", pair="EURUSD", exit="", ident=""):
        return ["broker", pair, "long", "swing", date, exit, "Win", pnl, "1", ident]

    def run_import(self, *extra):
        argv = [self.csv, "--root", self.root, "--account", "broker",
                "--pair", "Pair", "--direction", "Direction", "--style", "Style",
                "--entry", "Date", "--exit", "Exit", "--result", "Result",
                "--pnl", "PnL", "--risk", "Risk", "--id", "Id", *extra]
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                code = import_csv.main(argv)
            except SystemExit as e:
                code = e
        return code, out.getvalue()

    def opened(self):
        return sorted(t.opened for t in store.all_trades(self.root))

    # item 23: the order of a date with slashes is settled once
    def test_a_part_above_twelve_settles_the_whole_column_day_first(self):
        self.table([self.row("03/04/2026"), self.row("13/04/2026", pair="GBPUSD")])
        code, out = self.run_import()
        self.assertEqual(code, 0, out)
        # the first row is the 3rd of April and not the 4th of March
        self.assertEqual(self.opened(), [datetime(2026, 4, 3), datetime(2026, 4, 13)])

    def test_a_part_above_twelve_settles_the_whole_column_month_first(self):
        self.table([self.row("03/04/2026"), self.row("04/13/2026", pair="GBPUSD")])
        code, out = self.run_import()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.opened(), [datetime(2026, 3, 4), datetime(2026, 4, 13)])

    def test_the_exit_column_counts_with_the_entry_column(self):
        self.table([self.row("03/04/2026", exit="05/04/2026"),
                    self.row("06/04/2026", exit="13/04/2026", pair="GBPUSD")])
        code, out = self.run_import()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.opened(), [datetime(2026, 4, 3), datetime(2026, 4, 6)])

    def test_an_ambiguous_column_is_refused_until_the_order_is_given(self):
        self.table([self.row("03/04/2026"), self.row("05/06/2026", pair="GBPUSD")])
        code, out = self.run_import()
        self.assertIsInstance(code, SystemExit)
        self.assertIn("--date-order", str(code))
        self.assertEqual(store.all_trades(self.root), [])
        code, out = self.run_import("--date-order", "mdy")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.opened(), [datetime(2026, 3, 4), datetime(2026, 5, 6)])

    def test_the_order_given_wins_and_a_row_that_does_not_fit_is_named(self):
        self.table([self.row("03/04/2026"), self.row("13/04/2026", pair="GBPUSD")])
        code, out = self.run_import("--date-order", "mdy")
        self.assertIsInstance(code, SystemExit)
        self.assertIn("row 3", out)
        self.assertEqual(store.all_trades(self.root), [])

    def test_a_column_that_mixes_the_two_orders_is_refused(self):
        self.table([self.row("13/04/2026"), self.row("04/13/2026", pair="GBPUSD")])
        code, out = self.run_import()
        self.assertIsInstance(code, SystemExit)
        self.assertIn("day first in some rows", str(code))
        self.assertEqual(store.all_trades(self.root), [])

    def test_a_date_that_means_one_day_needs_no_order(self):
        self.table([self.row("05/05/2026"), self.row("2026-05-06", pair="GBPUSD"),
                    self.row("07.05.2026", pair="USDJPY")])
        code, out = self.run_import()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.opened(), [datetime(2026, 5, 5), datetime(2026, 5, 6),
                                         datetime(2026, 5, 7)])

    def test_slash_dates_with_an_hour_follow_the_order_too(self):
        self.table([self.row("03/04/2026 09:15"), self.row("13/04/2026 10:00",
                                                           pair="GBPUSD")])
        code, out = self.run_import()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.opened(), [datetime(2026, 4, 3, 9, 15),
                                         datetime(2026, 4, 13, 10, 0)])

    def test_parse_date_alone_refuses_a_date_that_could_be_two_days(self):
        with self.assertRaises(import_csv.RowError):
            import_csv.parse_date("03/04/2026")
        self.assertEqual(import_csv.parse_date("03/04/2026", "dmy")[0], datetime(2026, 4, 3))
        self.assertEqual(import_csv.parse_date("03/04/2026", "mdy")[0], datetime(2026, 3, 4))
        self.assertEqual(import_csv.parse_date("13/04/2026")[0], datetime(2026, 4, 13))
        self.assertEqual(import_csv.parse_date("04/13/2026")[0], datetime(2026, 4, 13))

    # item 49: a comma in a PnL, and a repeated row
    def test_a_pnl_with_a_comma_is_refused_with_its_row_number(self):
        for pnl in ("1,234", "1,234.56", "1.234,56", "0,250", "3,5"):
            self.table([self.row("2026-05-05"), self.row("2026-05-06", pnl=pnl,
                                                         pair="GBPUSD")])
            code, out = self.run_import()
            self.assertIsInstance(code, SystemExit, pnl)
            self.assertIn("row 3", out, pnl)
            self.assertIn("--decimal-comma", out, pnl)
            self.assertEqual(store.all_trades(self.root), [], pnl)

    def test_decimal_comma_reads_a_lone_comma_as_the_decimal_point(self):
        self.table([self.row("2026-05-05", pnl="0,250"),
                    self.row("2026-05-06", pnl="1.234,5", pair="GBPUSD"),
                    self.row("2026-05-07", pnl="-3,5", pair="USDJPY"),
                    self.row("2026-05-08", pnl="12.5", pair="AUDUSD")])
        code, out = self.run_import("--decimal-comma")
        self.assertEqual(code, 0, out)
        got = {t.pair: t.pnl for t in store.all_trades(self.root)}
        self.assertEqual(got, {"EURUSD": 0.25, "GBPUSD": 1234.5,
                               "USDJPY": -3.5, "AUDUSD": 12.5})

    def test_decimal_comma_refuses_two_commas(self):
        with self.assertRaises(import_csv.RowError):
            import_csv.parse_money("1,2,3", True)

    def test_a_pnl_with_a_point_or_none_is_as_before(self):
        self.table([self.row("2026-05-05", pnl="$1250.50"),
                    self.row("2026-05-06", pnl="-300", pair="GBPUSD")])
        code, out = self.run_import()
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(t.pnl for t in store.all_trades(self.root)),
                         [-300.0, 1250.5])

    def test_a_group_starting_with_zero_is_never_thousands(self):
        self.assertEqual(import_csv.parse_money("0,250"), 0.25)
        self.assertEqual(import_csv.parse_money("-0,250"), -0.25)
        self.assertEqual(import_csv.parse_money("1,250"), 1250)
        self.assertEqual(import_csv.parse_money("12,345,678"), 12345678)

    def test_the_same_row_twice_in_one_table_is_written_once(self):
        # by id
        self.table([self.row("2026-05-05", ident="n1"),
                    self.row("2026-05-05", ident="n1")])
        code, out = self.run_import()
        self.assertEqual(code, 0, out)
        self.assertIn("2 rows read, 1 written, 1 already in the journal", out)
        self.assertEqual(len(store.all_trades(self.root)), 1)

    def test_the_same_row_twice_without_an_id_is_written_once(self):
        self.table([self.row("2026-05-06"), self.row("2026-05-06"),
                    self.row("2026-05-06", pair="GBPUSD")])
        code, out = self.run_import()
        self.assertEqual(code, 0, out)
        self.assertIn("3 rows read, 2 written, 1 already in the journal", out)
        self.assertEqual(len(store.all_trades(self.root)), 2)

    def test_a_dry_run_counts_a_repeated_row_the_way_the_run_does(self):
        self.table([self.row("2026-05-06"), self.row("2026-05-06")])
        code, out = self.run_import("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("2 rows read, 1 would write, 1 already in the journal", out)
        self.assertEqual(store.all_trades(self.root), [])

    def test_the_lose_with_a_gain_check_still_names_its_row(self):
        args = argparse.Namespace(
            account="broker", account_column=None, pair="Pair", direction="Dir",
            style="Style", entry="Date", exit=None, result="Result", pnl="PnL",
            risk=None, entry_tf=None, note=None, conclusions=None, id=None,
            idea=None, pictures=None, pictures_dir=None, risk_default=1.0)
        row = {"Pair": "EURUSD", "Dir": "long", "Style": "swing",
               "Date": "2026-08-05 10:00", "Result": "Lose", "PnL": "+45"}
        with self.assertRaises(import_csv.RowError) as ctx:
            import_csv.build(row, args, {}, 7)
        self.assertIn("row 7", str(ctx.exception))


class CheckJournalCase(unittest.TestCase):
    """Item 48."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pb-check-audit-")
        store.save_account(self.root, Account(id="broker", start_balance=10000))
        store.save_playbook(self.root, Playbook(
            id="pull", name="Pull", styles=["swing"], version="1.0",
            setups=[Setup(rules=[Rule(1, "one")])]))

    def tearDown(self):
        shutil.rmtree(self.root)

    def trade(self, account):
        t = Trade(id="2026-01-05-01-eurusd", account=account, pair="EURUSD",
                  direction="long", style="swing", opened=datetime(2026, 1, 5))
        store.save_trade(self.root, t)
        return t

    def test_a_broken_version_of_a_playbook_is_named(self):
        store.freeze_playbook(self.root, "pull")
        code, out = run_tool("check_journal.py", self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("1 playbook versions", out)
        version = os.path.join(self.root, "journal", "playbooks", "pull",
                               "versions", "1.0.md")
        with open(version, "w", encoding="utf-8") as f:
            f.write("---\nid: pull\nname: Pull\nsince: not a date\n---\n")
        code, out = run_tool("check_journal.py", self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("CANNOT READ journal/playbooks/pull/versions/1.0.md", out)
        self.assertIn("1 record left out", out)

    def test_a_version_of_a_playbook_whose_own_file_is_gone_is_still_read(self):
        store.freeze_playbook(self.root, "pull")
        os.remove(os.path.join(self.root, "journal", "playbooks", "pull", "playbook.md"))
        counts, problems, _, _ = check_journal.check(self.root)
        self.assertEqual(counts["playbook versions"], 1)
        self.assertEqual(problems, [])

    def test_a_trade_whose_account_is_not_there_is_named(self):
        self.trade("ghost")
        code, out = run_tool("check_journal.py", self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("NO ACCOUNT 2026-01-05-01-eurusd", out)
        self.assertIn("'ghost'", out)
        self.assertIn("1 with no account", out)

    def test_a_trade_of_a_known_account_is_not(self):
        self.trade("broker")
        code, out = run_tool("check_journal.py", self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("clean:", out)


class ScreenshotsTool(unittest.TestCase):
    """Items 7 and 54, the parts that Python can run without taking a picture."""

    def test_the_lite_pictures_are_the_two_the_readme_shows(self):
        names = [name for name, _, _ in screenshots.lite_pages("/nonexistent")]
        self.assertEqual(names, ["journal.png", "accounts.png"])

    def test_a_free_port_can_be_bound(self):
        port = screenshots.free_port()
        with socket.socket() as s:
            s.bind(("127.0.0.1", port))

    def test_a_server_that_exits_is_a_failure_not_a_picture_of_something_else(self):
        child = subprocess.Popen([sys.executable, "-c", "raise SystemExit(3)"])
        child.wait()
        with self.assertRaises(SystemExit) as ctx:
            screenshots.wait_for(f"http://127.0.0.1:{screenshots.free_port()}", child)
        self.assertIn("exited with code 3", str(ctx.exception))

    def test_a_server_that_never_answers_is_a_failure(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            with self.assertRaises(SystemExit) as ctx:
                screenshots.wait_for(f"http://127.0.0.1:{screenshots.free_port()}",
                                     child, seconds=0.5)
            self.assertIn("did not answer", str(ctx.exception))
        finally:
            child.kill()
            child.wait()

    def test_a_server_that_answers_passes(self):
        import http.server
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            screenshots.wait_for(f"http://127.0.0.1:{server.server_address[1]}", child)
        finally:
            child.kill()
            child.wait()
            server.shutdown()
            server.server_close()

    def test_no_fixed_port_is_left(self):
        self.assertNotIn("8897", read("tools", "screenshots.py"))


@unittest.skipUnless(shutil.which("node"), "no node on this machine")
class BrowserCheckScript(unittest.TestCase):
    def test_it_parses_and_has_no_fixed_port_or_shared_profile(self):
        path = os.path.join(TOOLS, "browser_check.mjs")
        done = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        text = read("tools", "browser_check.mjs")
        self.assertNotIn("9333", text)
        self.assertNotIn("/tmp/plainbook-browser-check-profile", text)
        self.assertIn("--remote-debugging-port=0", text)
        self.assertIn("mkdtempSync", text)
        # the wait for a load ends the run in the end
        loaded = text[text.index("async function loaded()"):text.index("const api = {")]
        self.assertIn("rej(new Error(", loaded)


@unittest.skipUnless(os.path.isdir(DESKTOP), "no desktop/ in this tree")
class DesktopFiles(unittest.TestCase):
    TOGGLE = os.path.join(DESKTOP, "plainbook-toggle")

    def test_the_toggle_matches_the_dash_before_the_host(self):
        text = read("desktop", "plainbook-toggle")
        self.assertIn('test("-localhost__")', text)
        self.assertNotIn('test("localhost__")', text)
        install = read("INSTALL.md")
        self.assertIn('`test("-localhost__")`', install)
        self.assertNotIn('`test("localhost__")`', install)

    @unittest.skipUnless(shutil.which("jq"), "no jq on this machine")
    def test_the_class_filter_keeps_out_a_localhost_subdomain(self):
        text = read("desktop", "plainbook-toggle")
        pattern = re.search(r'test\("([^"]+)"\)', text).group(1)
        classes = ["brave-localhost__-Default", "chromium-localhost__-Default",
                   "brave-plaindesk.localhost__-Default", "kitty", "Plainbook"]
        listing = "[" + ",".join('{"class":"%s","address":"0x%d"}' % (c, i)
                                 for i, c in enumerate(classes)) + "]"
        done = subprocess.run(
            ["jq", "-r", f'.[] | select(.class | test("{pattern}")) | .class'],
            input=listing, capture_output=True, text=True)
        self.assertEqual(done.stdout.split(),
                         ["brave-localhost__-Default", "chromium-localhost__-Default"])

    @unittest.skipUnless(shutil.which("bash") and shutil.which("jq")
                         and os.name != "nt", "needs bash and jq")
    def test_the_toggle_opens_the_port_of_the_environment(self):
        stubs = tempfile.mkdtemp(prefix="pb-toggle-")
        try:
            for name, body in (("hyprctl", "echo '[]'"),
                               ("omarchy-launch-webapp", 'echo "opened $1"')):
                path = os.path.join(stubs, name)
                with open(path, "w") as f:
                    f.write("#!/bin/bash\n" + body + "\n")
                os.chmod(path, 0o755)

            def run(**extra):
                env = {k: v for k, v in os.environ.items() if k != "PLAINBOOK_PORT"}
                env["PATH"] = stubs + os.pathsep + env["PATH"]
                env.update(extra)
                return subprocess.run(["bash", self.TOGGLE], env=env,
                                      capture_output=True, text=True).stdout.strip()

            self.assertEqual(run(), "opened http://localhost:8778")
            self.assertEqual(run(PLAINBOOK_PORT="9123"), "opened http://localhost:9123")
        finally:
            shutil.rmtree(stubs)

    @unittest.skipUnless(shutil.which("bash"), "no bash on this machine")
    def test_the_toggle_is_valid_shell(self):
        done = subprocess.run(["bash", "-n", self.TOGGLE], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_install_makes_the_folder_before_it_copies_into_it(self):
        for text in (read("INSTALL.md"), read("desktop", "README.md")):
            for folder in ("~/.config/systemd/user", "~/Library/LaunchAgents"):
                self.assertIn(f"mkdir -p {folder}", text, folder)
        install = read("INSTALL.md")
        for folder, source in (("~/.config/systemd/user", "plainbook.service"),
                               ("~/Library/LaunchAgents", "plainbook.plist")):
            made = install.index(f"mkdir -p {folder}")
            self.assertLess(made, install.index(f"cp desktop/{source}"))

    def test_install_names_the_two_files_that_hold_the_port(self):
        install = read("INSTALL.md")
        self.assertIn("`plainbook-toggle`", install)
        self.assertIn("`trader.plainbook/Journal.qml`", install)
        self.assertIn("PLAINBOOK_PORT", read("desktop", "plainbook-toggle"))


class SdistManifest(unittest.TestCase):
    """Item 50. The sdist build itself is checked by hand (python -m build
    --sdist into a scratch folder, the suite run from the unpacked file); this
    keeps the rules that make it work from being taken out."""

    def test_the_manifest_ships_the_helper_of_the_tests_and_the_tools(self):
        manifest = read("MANIFEST.in")
        rules = [line.strip() for line in manifest.splitlines()
                 if line.strip() and not line.startswith("#")]
        self.assertIn("include tests/*.py", rules)
        self.assertIn("recursive-include tools *.py *.mjs", rules)

    def test_every_tool_the_tests_use_is_a_file_the_manifest_matches(self):
        used = set()
        for name in os.listdir(os.path.join(ROOT, "tests")):
            if name.endswith(".py"):
                text = read("tests", name)
                used |= set(re.findall(r'"tools",\s*"([\w.]+\.(?:py|mjs))"', text))
                used |= set(re.findall(r'run_tool\(\s*"([\w.]+\.py)"', text))
                used |= set(re.findall(r'tool_run\(\s*"([\w.]+\.py)"', text))
        for name in used:
            self.assertTrue(os.path.isfile(os.path.join(TOOLS, name)), name)
            self.assertTrue(name.endswith((".py", ".mjs")), name)


@unittest.skipUnless(os.path.isdir(WORKFLOWS), "no .github in this tree")
class Workflows(unittest.TestCase):
    """Item 52, read as text: the three files carry no YAML parser of their own
    on a runner, and what is asserted here is where permissions sit."""

    @staticmethod
    def jobs(text):
        """{job name: its lines} of a workflow, cut at the two-space keys under
        the top-level `jobs:`."""
        body = text.split("\njobs:\n", 1)[1]
        found, name = {}, None
        for line in body.split("\n"):
            m = re.match(r"^  ([\w-]+):\s*$", line)
            if m:
                name = m.group(1)
                found[name] = []
            elif name is not None:
                found[name].append(line)
        return {k: "\n".join(v) for k, v in found.items()}

    def test_publish_holds_the_id_token_only_in_the_job_that_uploads(self):
        text = code_of(read(".github", "workflows", "publish.yml"))
        top = text.split("\njobs:\n", 1)[0]
        self.assertNotIn("id-token", top.split("\npermissions:", 1)[1])
        jobs = self.jobs(text)
        self.assertEqual(set(jobs), {"build", "tests-green", "publish"})
        with_token = [n for n, body in jobs.items() if "id-token: write" in body]
        self.assertEqual(with_token, ["publish"])
        # the build tools and the package's own tests run where no token is
        self.assertIn("python -m build", jobs["build"])
        self.assertIn("unittest discover", jobs["build"])
        self.assertIn("tools/pypi_readme.py", jobs["build"])
        self.assertNotIn("pip install", jobs["publish"])
        self.assertIn("gh-action-pypi-publish", jobs["publish"])
        self.assertIn("environment: pypi", jobs["publish"])
        self.assertIn("needs: [build, tests-green]", jobs["publish"])

    def test_publish_waits_for_the_tests_of_the_commit_of_the_tag(self):
        jobs = self.jobs(code_of(read(".github", "workflows", "publish.yml")))
        gate = jobs["tests-green"]
        self.assertIn("workflows/tests.yml/runs", gate)
        self.assertIn("head_sha=$SHA", gate)
        self.assertIn("actions: read", gate)
        self.assertIn("exit 1", gate)
        self.assertNotIn("write", gate)
        self.assertIn("needs.build.outputs.sha", gate)
        self.assertIn("git rev-parse HEAD", jobs["build"])

    def test_the_artifact_goes_from_the_build_to_the_publish(self):
        jobs = self.jobs(code_of(read(".github", "workflows", "publish.yml")))
        self.assertIn("actions/upload-artifact@", jobs["build"])
        self.assertIn("name: dist", jobs["build"])
        self.assertIn("actions/download-artifact@", jobs["publish"])
        self.assertIn("name: dist", jobs["publish"])
        self.assertIn("path: dist", jobs["publish"])

    def test_release_writes_to_the_release_only_in_the_upload_job(self):
        text = code_of(read(".github", "workflows", "release.yml"))
        top = text.split("\njobs:\n", 1)[0]
        self.assertNotIn("contents: write", top)
        jobs = self.jobs(text)
        self.assertEqual(set(jobs), {"build", "upload"})
        writers = [n for n, body in jobs.items() if "contents: write" in body]
        self.assertEqual(writers, ["upload"])
        self.assertNotIn("PyInstaller", jobs["upload"])
        self.assertNotIn("pip install", jobs["upload"])
        self.assertIn("gh release upload", jobs["upload"])
        self.assertNotIn("gh release upload", jobs["build"])
        # the attestation stays with the build that made the file
        self.assertIn("attest-build-provenance", jobs["build"])
        self.assertIn("attestations: write", jobs["build"])
        self.assertIn("needs: build", jobs["upload"])
        self.assertIn("GH_REPO", jobs["upload"])        # no checkout to find the repository in

    def test_every_action_is_pinned_to_a_commit(self):
        for name in ("publish.yml", "release.yml", "tests.yml"):
            for line in read(".github", "workflows", name).splitlines():
                m = re.match(r"\s*-?\s*uses:\s*(\S+)", line)
                if m:
                    self.assertRegex(m.group(1), r"@[0-9a-f]{40}$", f"{name}: {line}")

    def test_the_files_are_yaml_where_a_parser_is_at_hand(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("no YAML parser on this machine")
        for name in ("publish.yml", "release.yml", "tests.yml"):
            doc = yaml.safe_load(read(".github", "workflows", name))
            self.assertIn("jobs", doc, name)


if __name__ == "__main__":
    unittest.main()
