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
from datetime import datetime, timedelta

from . import html as H
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


def previous_period(period):
    """'2026-08' -> '2026-07', '2026-Q1' -> '2025-Q4'. The one to compare with."""
    m = _PERIOD.match(period or "")
    if not m:
        raise ValueError(f"cannot read the period: {period!r}")
    year = int(m.group(1))
    if m.group(2):
        month = int(m.group(2))
        return f"{year - 1}-12" if month == 1 else f"{year}-{month - 1:02d}"
    q = int(m.group(3))
    return f"{year - 1}-Q4" if q == 1 else f"{year}-Q{q - 1}"


def period_months(period):
    """'2026-Q3' -> ('2026-07', '2026-09'): the months the journal filters by."""
    start, end, _ = parse_period(period)
    last = end - timedelta(days=1)
    return f"{start:%Y-%m}", f"{last:%Y-%m}"


def trades_of_period(journal, period):
    start, end, _ = parse_period(period)
    return [t for t in journal.trades if start <= t.opened < end]


# Reports built before this used to carry a stub under the heading, and the
# form loaded it as text the owner had to delete before writing anything. It is
# not written any more; this recognises it in the files that already have it.
_STUB = re.compile(r"^_\(empty.*\)_$")


def previous_conclusions(root, period):
    file = path(root, period)
    if not os.path.exists(file):
        return ""
    with open(file, encoding="utf-8") as f:
        _, body = mdfile.parse(f.read())
    m = re.search(r"^## Conclusions\s*$(.*)", body, re.M | re.S)
    text = m.group(1).strip() if m else ""
    return "" if _STUB.match(text) else text


def build(root, journal, period, conclusions=None):
    """Recomputes the figures. Conclusions: the new ones, or the old ones kept."""
    start, end, name = parse_period(period)
    trades = trades_of_period(journal, period)
    text = conclusions if conclusions is not None else previous_conclusions(root, period)

    total = stats.summary(journal, trades)
    # the same figures for the period before, so every number has something to
    # be read against: a winrate alone says nothing about whether it is moving
    earlier = previous_period(period)
    before_name = parse_period(earlier)[2]
    was_trades = trades_of_period(journal, earlier)
    was = stats.summary(journal, was_trades)

    cur = H.sign(journal.currency())
    lines = [f"# {name}", "", "## Summary", ""]
    lines += [f"| metric | {name} | {before_name} |", "|---|---|---|",
              f"| trades | {total.trades} | {was.trades or '-'} |",
              f"| win / lose / BE | {total.wins} / {total.losses} / {total.be} "
              f"| {f'{was.wins} / {was.losses} / {was.be}' if was.trades else '-'} |",
              f"| winrate (BE not counted) | {total.wr:.1f}% "
              f"| {f'{was.wr:.1f}%' if was.decided else '-'} |",
              f"| total R | {total.sum_r:+.2f} "
              f"| {f'{was.sum_r:+.2f}' if was.trades else '-'} |",
              f"| average R | {total.average_r:+.2f} "
              f"| {f'{was.average_r:+.2f}' if was.trades else '-'} |",
              f"| result in money | {total.sum_pnl:+,.2f} {cur} "
              f"| {f'{was.sum_pnl:+,.2f} {cur}' if was.trades else '-'} |".replace(",", " "),
              f"| deepest fall from a high | {stats.drawdown_r(journal, trades):+.2f} R "
              f"| {f'{stats.drawdown_r(journal, was_trades):+.2f} R' if was.trades else '-'} |",
              ""]

    for heading, key in (("By style", lambda t: [t.style]),
                         ("By pair", lambda t: [t.pair]),
                         ("By account", lambda t: [t.account]),
                         ("By direction", lambda t: [t.direction]),
                         ("By entry TF", lambda t: [t.entry_tf or "not set"]),
                         ("By execution", lambda t: t.execution or ["not set"])):
        lines += [f"### {heading}", "",
                  f"| | trades | WR | Σ R | average R | Σ {cur} |", "|---|---|---|---|---|---|"]
        for value, s in stats.by_values(journal, trades, key):
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
    lines += ["", *extremes(journal, trades), *process(root, trades, start, end)]

    # An empty section stays empty: whatever stands here is loaded into the
    # form as the owner's own text, so a hint would have to be deleted first.
    lines += ["", "## Conclusions", "", text]

    head = {"period": period, "kind": "quarter" if "Q" in period else "month",
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M")}
    file = path(root, period)
    os.makedirs(os.path.dirname(file), exist_ok=True)
    tmp = file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(mdfile.dump(head, "\n".join(lines)))
    os.replace(tmp, file)
    return file


def extremes(journal, trades):
    """The two trades of the period worth opening again: the best and the worst.

    By R and not by money, or the largest account would win every month."""
    closed = [t for t in trades if not t.is_open and journal.r(t.id) is not None]
    if not closed:
        return []
    best = max(closed, key=lambda t: journal.r(t.id))
    worst = min(closed, key=lambda t: journal.r(t.id))
    lines = ["### Best and worst trade", "",
             f"| trade | pair | style | R | {H.sign(journal.currency())} |", "|---|---|---|---|---|"]
    for label, t in (("best", best), ("worst", worst)):
        if label == "worst" and worst.id == best.id:
            continue
        lines.append(f"| {t.id} | {t.pair} | {t.style} | {journal.r(t.id):+.2f} "
                     f"| {t.pnl:+,.0f} |".replace(",", " "))
    return lines + [""]


def process(root, trades, start, end):
    """The daily cards of the period: the process behind the figures.

    A month is not only its result. The grades of the cards say how the days
    were traded, and the count says how many of them were reviewed at all."""
    cards = [k for k in store.all_cards(root) if k.day and start <= k.day < end]
    days = {t.opened.date() for t in trades if t.opened}
    lines = ["### Process", ""]
    if not cards:
        return lines + [f"No cards written for this period, and {len(days)} days "
                        f"had trades.", ""]
    grades = {}
    for k in cards:
        grades[k.grade or "not graded"] = grades.get(k.grade or "not graded", 0) + 1
    lines += [f"{len(cards)} cards written, {len(days)} days had trades.", "",
              "| process grade | days |", "|---|---|"]
    lines += [f"| {grade} | {n} |"
              for grade, n in sorted(grades.items(), key=lambda x: x[0])]
    return lines + [""]


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
