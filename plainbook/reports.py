#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monthly and quarterly reports.

A report is an ordinary markdown file in journal/reports. The figures are
recomputed on every build, while the "Conclusions" section belongs to the
owner and is NEVER overwritten.
"""
import os
import re
from datetime import datetime

from . import mdfile, stats, store

DIR = "reports"
_PERIOD = re.compile(r"^(\d{4})-(?:(\d{2})|Q([1-4]))$")

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]


def path(root, period):
    return os.path.join(root, store.JOURNAL, DIR, period + ".md")


def parse_period(period):
    """'2026-08' | '2026-Q3' -> (start, end, human readable name)."""
    m = _PERIOD.match(period or "")
    if not m:
        raise ValueError(f"cannot read the period: {period!r}")
    year = int(m.group(1))
    if m.group(2):
        month = int(m.group(2))
        start = datetime(year, month, 1)
        end = datetime(year + (month == 12), (month % 12) + 1, 1)
        return start, end, f"{MONTH_NAMES[month - 1]} {year}"
    q = int(m.group(3))
    start = datetime(year, 3 * (q - 1) + 1, 1)
    end = datetime(year + (q == 4), (3 * q) % 12 + 1, 1)
    return start, end, f"Q{q} {year}"


def trades_of_period(journal, period):
    start, end, _ = parse_period(period)
    return [t for t in journal.trades if start <= t.opened < end]


def previous_conclusions(root, period):
    file = path(root, period)
    if not os.path.exists(file):
        return ""
    with open(file, encoding="utf-8") as f:
        _, body = mdfile.parse(f.read())
    m = re.search(r"^## Conclusions\s*$(.*)", body, re.M | re.S)
    return m.group(1).strip() if m else ""


def build(root, journal, period, conclusions=None):
    """Recomputes the figures. Conclusions: the new ones, or the old ones kept."""
    start, end, name = parse_period(period)
    trades = trades_of_period(journal, period)
    text = conclusions if conclusions is not None else previous_conclusions(root, period)

    total = stats.summary(journal, trades)
    lines = [f"# {name}", "", "## Summary", ""]
    lines += ["| metric | value |", "|---|---|",
              f"| trades | {total.trades} |",
              f"| win / lose / BE | {total.wins} / {total.losses} / {total.be} |",
              f"| winrate (BE not counted) | {total.wr:.1f}% |",
              f"| total R | {total.sum_r:+.2f} |",
              f"| average R | {total.average_r:+.2f} |",
              f"| result in money | {total.sum_pnl:+,.2f} $ |".replace(",", " "),
              ""]

    for heading, key in (("By style", lambda t: t.style),
                         ("By pair", lambda t: t.pair),
                         ("By account", lambda t: t.account)):
        lines += [f"### {heading}", "",
                  "| | trades | WR | Σ R | average R | Σ $ |", "|---|---|---|---|---|---|"]
        for value, s in stats.by_field(journal, trades, key):
            lines.append(f"| {value} | {s.trades} | {s.wr:.1f}% | {s.sum_r:+.2f} "
                         f"| {s.average_r:+.2f} | {s.sum_pnl:+,.0f} |".replace(",", " "))
        lines.append("")

    lines += ["### Balance change by account", "",
              "| account | before | after | change |", "|---|---|---|---|"]
    for account in sorted(journal.accounts):
        before = balance_at(journal, account, start)
        after = balance_at(journal, account, end)
        lines.append(f"| {account} | {before:,.0f} | {after:,.0f} | {after-before:+,.0f} |"
                     .replace(",", " "))
    lines += ["", "## Conclusions", "",
              text or "_(empty, write it in the browser)_"]

    head = {"period": period, "kind": "quarter" if "Q" in period else "month",
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M")}
    file = path(root, period)
    os.makedirs(os.path.dirname(file), exist_ok=True)
    tmp = file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(mdfile.dump(head, "\n".join(lines)))
    os.replace(tmp, file)
    return file


def balance_at(journal, account, moment):
    """The computed balance of an account on a date (everything strictly before)."""
    acc = journal.accounts.get(account)
    b = acc.start_balance if acc else 0.0
    b += sum(c.amount for c in journal.adjustments
             if c.account == account and c.day < moment)
    b += sum(t.pnl or 0.0 for t in journal.trades
             if t.account == account and not t.is_open and t.closed and t.closed < moment)
    return b


def existing(root):
    folder = os.path.join(root, store.JOURNAL, DIR)
    names = [i[:-3] for i in sorted(os.listdir(folder)) if i.endswith(".md")] \
        if os.path.isdir(folder) else []
    return sorted(names, reverse=True)


def read(root, period):
    file = path(root, period)
    if not os.path.exists(file):
        return None, None
    with open(file, encoding="utf-8") as f:
        head, body = mdfile.parse(f.read())
    return head, body
