#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The pictures of README.md, retaken on the demo journal.

    python3 tools/screenshots.py            # writes docs/*.png
    python3 tools/screenshots.py /tmp/out   # somewhere else

Builds an invented journal in a temporary folder, serves it on a port of its
own, builds one report, shoots every page the README shows with a headless
Chromium at 1400 by 1000, and stops the server. Nothing of anybody's records
is touched: the journal it shoots is the one tools/demo_journal.py writes.
Needs a Chromium-family browser on the PATH (chromium, google-chrome, brave).
Run it after a release, so that the version on the pictures is the one people
download.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import reports, store

PORT = 8897
BROWSERS = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
            "brave", "brave-browser")


def pages(root):
    """(file name, path, window height): the pages the README shows, picked
    off the demo journal by what they hold."""
    trades = store.all_trades(root)
    # the trade the pictures show is the one with the most to show: a win
    # under the playbook, with its prices and its conclusions
    closed = [t for t in trades if not t.is_open and t.playbook and t.conclusions]
    closed.sort(key=lambda t: (t.result == "Win", t.best_price is not None,
                               t.closed), reverse=True)
    trade = closed[0]
    quarter = max(p for p in reports.existing(root) if "Q" in p)
    # the passport reads best on a win from the middle of the history, with
    # its prices, its hours and its stop moved to the entry, so that the
    # marks on the curve of its account stand clear of its ends
    rich = sorted((t for t in trades if not t.is_open and t.result == "Win"
                   and t.breakeven and t.best_price is not None and t.closed_time
                   and t.account == "broker"), key=lambda t: t.closed)
    shown = rich[len(rich) // 2] if rich else trade
    plan = store.all_plans(root)[0]
    note = store.all_notes(root)[0]
    card = store.all_cards(root)[0]
    week = store.all_weeks(root)[0]
    report = quarter
    return [
        ("journal.png", "/", 1000),
        ("new-trade.png", f"/edit/{trade.id}", 1000),
        ("trade.png", f"/trade/{shown.id}", 1000),
        ("playbook.png", "/playbook/pullback", 1000),
        ("plan.png", f"/plan/{plan.id}", 1000),
        ("note.png", f"/note/{note.id}", 1000),
        ("card.png", f"/card/{card.day:%Y-%m-%d}", 900),
        ("week.png", f"/week/{week.week}", 900),
        ("statistics.png", "/stats", 1000),
        # tall enough for the tape, the R distribution and the day by day of
        # a quarter; a headless shot of an address with an anchor comes out
        # blank, so the pictures are cut by their height and not by scrolling
        ("report.png", f"/report/{report}", 1130),
        ("reports.png", "/reports", 1000),
        ("accounts.png", "/accounts", 800),
        ("share.png", f"/share/trade/{trade.id}", 1000),
        ("search.png", "/search?q=retest", 700),
    ]


def main():
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                          os.path.join(os.path.dirname(os.path.dirname(
                              os.path.abspath(__file__))), "docs"))
    browser = next((b for b in BROWSERS if shutil.which(b)), None)
    if not browser:
        print("no Chromium-family browser on the PATH")
        return 2
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmp = tempfile.mkdtemp(prefix="pb-shots-")
    root = os.path.join(tmp, "demo")
    # months of history before the demo proper: the year, the shelf and a
    # quarter of the reports need a run longer than six weeks to show
    subprocess.run([sys.executable, os.path.join(here, "tools", "demo_journal.py"), root,
                    "--months=8"], check=True, capture_output=True)
    env = dict(os.environ, PLAINBOOK_ROOT=root, PLAINBOOK_PORT=str(PORT), PLAINBOOK_OPEN="0")
    server = subprocess.Popen([sys.executable, "-m", "plainbook.server"], cwd=here, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{PORT}"
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(base + "/").close()
                break
            except OSError:
                time.sleep(0.1)
        # the report of the month before the last closed trade, so that the
        # shelf and the report page have something built to show
        last = max(t.closed for t in store.all_trades(root) if t.closed)
        period = reports.previous_period(f"{last:%Y-%m}")
        quarter = reports.previous_period(reports.period_of(last, "quarter"))
        for what, key in (("month", period), ("quarter", quarter)):
            urllib.request.urlopen(urllib.request.Request(
                base + "/report/build", data=f"what={what}&period_{what}={key}".encode(),
                headers={"Origin": base})).close()
        os.makedirs(out, exist_ok=True)
        profile = os.path.join(tmp, "profile")
        for name, path, height in pages(root):
            target = os.path.join(out, name)
            subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            f"--user-data-dir={profile}", f"--window-size=1400,{height}",
                            f"--screenshot={target}", base + path],
                           check=True, capture_output=True)
            print(f"{name:16} {path}")
    finally:
        server.terminate()
        server.wait()
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
