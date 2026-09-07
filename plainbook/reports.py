#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monthly and quarterly reports.

A report is composed from the journal every time it is looked at: the figures
on the page are the journal as it is now. Building a report writes the same
figures into an ordinary markdown file in journal/reports, which is the archive
and the place the owner's "Conclusions" live; that section is NEVER overwritten.
"""
import os
import re
from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta

from . import html as H
from . import mdfile, stats, store

DIR = "reports"
_PERIOD = re.compile(r"^(\d{4})-(?:(\d{2})|Q([1-4]))$")

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]

# The slices a report is cut into, in the order they are shown. The heading is
# what the file carries and what a row of the page links by, so it stays put.
SLICES = (("By style", lambda t: [t.style]),
          ("By pair", lambda t: [t.pair]),
          ("By account", lambda t: [t.account]),
          ("By direction", lambda t: [t.direction]),
          ("By entry TF", lambda t: [t.entry_tf or "not set"]),
          ("By execution", lambda t: t.execution or ["not set"]))


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
        if not 1 <= month <= 12:
            raise ValueError(f"cannot read the period: {period!r}")
        start = datetime(year, month, 1)
        end = datetime(year + (month == 12), (month % 12) + 1, 1)
        return start, end, f"{MONTH_NAMES[month - 1]} {year}"
    q = int(m.group(3))
    start = datetime(year, 3 * (q - 1) + 1, 1)
    end = datetime(year + (q == 4), (3 * q) % 12 + 1, 1)
    return start, end, f"Q{q} {year}"


def kind_of(period):
    return "quarter" if "Q" in (period or "") else "month"


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


def next_period(period):
    """'2026-08' -> '2026-09', '2026-Q4' -> '2027-Q1'."""
    m = _PERIOD.match(period or "")
    if not m:
        raise ValueError(f"cannot read the period: {period!r}")
    year = int(m.group(1))
    if m.group(2):
        month = int(m.group(2))
        return f"{year + 1}-01" if month == 12 else f"{year}-{month + 1:02d}"
    q = int(m.group(3))
    return f"{year + 1}-Q1" if q == 4 else f"{year}-Q{q + 1}"


def period_of(moment, kind):
    """The month or the quarter a moment falls in, as a period id."""
    if kind == "quarter":
        return stats.quarter(moment)
    return f"{moment:%Y-%m}"


def period_months(period):
    """'2026-Q3' -> ('2026-07', '2026-09'): the months the journal filters by."""
    start, end, _ = parse_period(period)
    last = end - timedelta(days=1)
    return f"{start:%Y-%m}", f"{last:%Y-%m}"


def trades_of_period(journal, period):
    """The trades that closed in the period.

    A period is measured by the exit, the way a broker states a month and the
    cards count a day: a trade belongs to the month it paid or cost, not to the
    one it was entered in. Without this the result in money and the balance
    change of one report disagreed by every trade that ran across its edge.
    The list on the front page groups by the entry, so a trade that crossed a
    boundary stands in one month there and in the other here."""
    start, end, _ = parse_period(period)
    return [t for t in journal.trades
            if not t.is_open and t.closed and start <= t.closed < end]


def still_open(journal, period, now=None):
    """The positions open now, counted beside the figures of a period that is
    still running. Blue means open everywhere in the journal, so a finished
    period shows none: what it carried over its end has closed since, and a
    position closed long ago has no business standing in blue on an old month.
    They are not in the figures, a period is measured by its exits."""
    start, end, _ = parse_period(period)
    now = now or datetime.now()
    if not start <= now < end:
        return []
    return [t for t in journal.trades if t.is_open]


# Reports built before this used to carry a stub under the heading, and the
# form loaded it as text the owner had to delete before writing anything. It is
# not written any more; this recognises it in the files that already have it.
_STUB = re.compile(r"^_\(empty.*\)_$")


def previous_conclusions(root, period):
    file = path(root, period)
    if not os.path.exists(file):
        return ""
    _, body = read(root, period)
    m = re.search(r"^## Conclusions\s*$(.*)", body, re.M | re.S)
    text = m.group(1).strip() if m else ""
    return "" if _STUB.match(text) else text


# --- the report -----------------------------------------------------------

@dataclass
class Report:
    """Everything a report says, as figures. The page draws it, the file
    keeps it; neither does any arithmetic of its own."""
    period: str
    kind: str
    name: str
    start: datetime
    end: datetime
    earlier: str                    # the period compared with
    earlier_name: str
    trades: list                    # closed inside the period, by the exit
    was_trades: list                # the same for the period before
    total: stats.Summary
    was: stats.Summary
    fall: float                     # deepest fall from a high, in R, <= 0
    was_fall: float
    held: list = field(default_factory=list)      # open now, for a running period only
    playbooks: list = field(default_factory=list)  # [(pid, label, Summary, Compliance, setups)]
    slices: list = field(default_factory=list)     # [(heading, [(value, Summary)])]
    balances: list = field(default_factory=list)   # [(account id, before, after)]
    best: object = None
    worst: object = None
    cards: list = field(default_factory=list)      # the daily cards of the period
    weeks: list = field(default_factory=list)      # the weekly cards that began in it
    days_traded: int = 0
    grades: list = field(default_factory=list)     # [(grade, days)]
    ticked: int = 0                 # trades that went through a checklist
    kept: stats.Summary = None      # the ticked ones that met every rule
    broke: stats.Summary = None     # the ticked ones that broke a rule, at the entry or the close
    rules: list = field(default_factory=list)      # [(playbook label, Rule, trades, Summary)]
    past_stop: list = field(default_factory=list)  # losses of -1.2 R and worse
    entry_broken: int = 0           # ticked trades that broke a rule at the entry
    close_broken: int = 0           # closed trades that broke a management rule
    unticked: int = 0               # tied to a playbook, never ticked
    mistakes: list = field(default_factory=list)   # the trades above, each once
    mistakes_sum: stats.Summary = None
    order: list = field(default_factory=list)      # the closed trades, by the exit


def compose(root, journal, period):
    """The report of a period, from the journal as it stands."""
    start, end, name = parse_period(period)
    trades = trades_of_period(journal, period)
    earlier = previous_period(period)
    was_trades = trades_of_period(journal, earlier)
    r = Report(period=period, kind=kind_of(period), name=name, start=start, end=end,
               earlier=earlier, earlier_name=parse_period(earlier)[2],
               trades=trades, was_trades=was_trades,
               total=stats.summary(journal, trades),
               was=stats.summary(journal, was_trades),
               fall=stats.drawdown_r(journal, trades),
               was_fall=stats.drawdown_r(journal, was_trades))
    r.held = still_open(journal, period)
    r.playbooks = playbook_rows(root, journal, trades)
    r.slices = [(heading, stats.by_values(journal, trades, key))
                for heading, key in SLICES]
    r.balances = [(a, balance_at(journal, a, start), balance_at(journal, a, end))
                  for a in sorted(journal.accounts)
                  if not journal.accounts[a].archived
                  or any(t.account == a for t in trades)]
    r.best, r.worst = extremes(journal, trades)
    r.cards = [k for k in store.all_cards(root) if k.day and start <= k.day < end]
    r.weeks = [k for k in store.all_weeks(root)
               if k.week and start <= k.monday < end]
    r.days_traded = len({t.closed.date() for t in trades if t.closed})
    grades = {}
    for k in r.cards:
        grades[k.grade or "not graded"] = grades.get(k.grade or "not graded", 0) + 1
    r.grades = sorted(grades.items())
    d = discipline(root, journal, trades)
    for f in fields(Discipline):
        setattr(r, f.name, getattr(d, f.name))
    # the order the account felt them: by the exit, the way the tape draws them
    r.order = sorted(trades, key=lambda t: (t.closed, t.id))
    return r


def playbook_rows(root, journal, trades):
    """The trades by the playbook they were opened under, its setups beneath
    it, the ones under none last. Empty when no trade names one."""
    rows = stats.by_playbook(journal, trades)
    if not any(pid != stats.NO_PLAYBOOK for pid, _, _ in rows):
        return []
    names = {b.id: b.name or b.id for b in store.all_playbooks(root, [])}
    out = []
    for pid, s, c in rows:
        if pid == stats.NO_PLAYBOOK:
            out.append((pid, stats.NO_PLAYBOOK, s, None, []))
            continue
        own = [t for t in trades if t.playbook == pid]
        setups = stats.by_setup(journal, own)
        if not (len(setups) > 1 or (setups and setups[0][0] != "-")):
            setups = []
        out.append((pid, names.get(pid, pid), s, c, setups))
    return out


@dataclass
class Discipline:
    """How a set of trades went through the rules: the fields of a Report
    that the Statistics tab reads off its own selection as well."""
    ticked: int = 0
    unticked: int = 0
    kept: stats.Summary = None
    broke: stats.Summary = None
    rules: list = field(default_factory=list)      # [(playbook label, Rule, trades, Summary)]
    past_stop: list = field(default_factory=list)
    entry_broken: int = 0
    close_broken: int = 0
    mistakes: list = field(default_factory=list)
    mistakes_sum: stats.Summary = None


def discipline(root, journal, trades):
    """How the trades went through their checklists, and which rules were
    broken at what cost.

    Only ticked trades say anything, at the entry or at the close: one tied to
    its playbook later and never ticked anywhere was never held against the
    rules. A rule is counted by number, so only the trades
    ticked against the current version of a playbook stand in the rule rows,
    the way the playbook's own page counts them; the shares of clean and
    broken trades take every ticked trade of the period.

    Closed trades only, the way stats.checklist counts them: a position still
    in the market has no R to put against a rule, and every figure standing
    beside this one counts what is closed. A report hands over the trades of
    its period, which are closed by construction; the Statistics tab hands
    over a selection, which is not."""
    trades = [t for t in trades if not t.is_open]
    c = stats.checklist(journal, trades)
    ticked = [t for t in trades if stats.ticked(t)]
    r = Discipline(ticked=c.ticked, unticked=c.unticked, kept=c.kept, broke=c.broke)
    rows = []
    for p in store.all_playbooks(root, []):
        same = [t for t in trades
                if t.playbook == p.id and t.playbook_version == p.version]
        if not same:
            continue
        costs, _ = stats.rule_costs(journal, same, p.rules)
        rows += [(p.name or p.id, rule, n, s) for rule, n, s in costs if n]
    # the dearest first: what cost the most R stands at the top
    rows.sort(key=lambda x: (x[3].sum_r, -x[2]))
    r.rules = rows
    r.past_stop = stats.past_stop(journal, trades)
    r.entry_broken = sum(1 for t in ticked if t.deviations)
    r.close_broken = sum(1 for t in ticked if t.exit_deviations)
    # what the journal itself calls a mistake: a rule ticked as not met, at
    # the entry or at the close, or a loss past the stop. A trade that did two
    # of these is one mistake; a trade never ticked is not one either way
    seen, mistakes = set(), []
    for t in [x for x in ticked if stats.broke(x)] + r.past_stop:
        if t.id not in seen:
            seen.add(t.id)
            mistakes.append(t)
    r.mistakes = mistakes
    r.mistakes_sum = stats.summary(journal, mistakes)
    return r


def extremes(journal, trades):
    """The two trades of the period worth opening again: the best and the
    worst, by R, since by money the largest account would win every month.
    One trade is never both: when every closed trade of the period carries
    the same R there is a best only."""
    closed = [t for t in trades if not t.is_open and journal.r(t.id) is not None]
    if not closed:
        return None, None
    best = max(closed, key=lambda t: journal.r(t.id))
    worst = min(closed, key=lambda t: journal.r(t.id))
    return best, (None if worst.id == best.id else worst)


def balance_at(journal, account, moment):
    """The computed balance of an account on a date (everything strictly before)."""
    acc = journal.accounts.get(account)
    b = acc.start_balance if acc else 0.0
    b += sum(c.amount for c in journal.adjustments
             if c.account == account and c.day < moment)
    b += sum(t.pnl or 0.0 for t in journal.trades
             if t.account == account and not t.is_open and t.closed and t.closed < moment)
    return b


# --- the file -------------------------------------------------------------

def _money(x):
    return f"{x:+,.0f}".replace(",", " ")


def _figures(s):
    return (f"{s.trades} | {s.wr:.1f}% | {s.sum_r:+.2f} | {s.average_r:+.2f} "
            f"| {_money(s.sum_pnl)}")


def to_markdown(r, journal, conclusions):
    """The report as the file keeps it: the same figures, as tables."""
    cur = H.sign(journal.currency())
    total, was = r.total, r.was

    def then(value, shown=True):
        return value if (was.trades and shown) else "-"

    lines = [f"# {r.name}", "", "## Summary", "",
             f"| metric | {r.name} | {r.earlier_name} |", "|---|---|---|",
             f"| trades | {total.trades} | {was.trades or '-'} |",
             f"| win / lose / BE | {total.wins} / {total.losses} / {total.be} "
             f"| {then(f'{was.wins} / {was.losses} / {was.be}')} |",
             f"| winrate (BE not counted) | {f'{total.wr:.1f}%' if total.decided else '-'} "
             f"| {then(f'{was.wr:.1f}%', was.decided)} |",
             f"| total R | {total.sum_r:+.2f} | {then(f'{was.sum_r:+.2f}')} |",
             f"| EV (average R, BE counted) | {total.average_r:+.2f} "
             f"| {then(f'{was.average_r:+.2f}')} |",
             f"| result in money | {_money(total.sum_pnl)} {cur} "
             f"| {then(f'{_money(was.sum_pnl)} {cur}')} |",
             f"| deepest fall from a high | {r.fall:+.2f} R "
             f"| {then(f'{r.was_fall:+.2f} R')} |",
             ""]
    if r.playbooks:
        lines += ["### By playbook", "",
                  f"| | trades | WR | Σ R | EV | Σ {cur} | clean | held |",
                  "|---|---|---|---|---|---|---|---|"]
        for pid, label, s, c, setups in r.playbooks:
            lines.append(f"| {label} | {_figures(s)} | {_clean(c)} | {_held(c)} |")
            for name, ss, cc in setups:
                lines.append(f"| · {name} | {_figures(ss)} | {_clean(cc)} | {_held(cc)} |")
        lines.append("")
    for heading, rows in r.slices:
        lines += [f"### {heading}", "",
                  f"| | trades | WR | Σ R | EV | Σ {cur} |", "|---|---|---|---|---|---|"]
        lines += [f"| {value} | {_figures(s)} |" for value, s in rows]
        lines.append("")
    lines += ["### Balance change by account", "",
              "| account | before | after | change |", "|---|---|---|---|"]
    for account, before, after in r.balances:
        lines.append(f"| {account} | {before:,.0f} | {after:,.0f} | {after - before:+,.0f} |"
                     .replace(",", " "))
    lines.append("")
    if r.best:
        lines += ["### Best and worst trade", "",
                  f"| trade | pair | style | R | {cur} |", "|---|---|---|---|---|"]
        for label, t in (("best", r.best), ("worst", r.worst)):
            if t:
                lines.append(f"| {t.id} | {t.pair} | {t.style} | {journal.r(t.id):+.2f} "
                             f"| {_money(t.pnl or 0.0)} |")
        lines.append("")
    if r.ticked:
        lines += ["### Rules", "",
                  f"{r.ticked} {_trades(r.ticked)} ticked against a playbook: "
                  f"{r.kept.trades} kept every rule, {r.broke.trades} broke one or more.", ""]
        if r.rules:
            lines += ["| rule not met | trades | Σ R | EV |", "|---|---|---|---|"]
            lines += [f"| {label} {rule.number}: {rule.text} | {n} | {s.sum_r:+.2f} "
                      f"| {s.average_r:+.2f} |" for label, rule, n, s in r.rules]
            lines.append("")
    if r.past_stop:
        lines += ["### Losses past the stop", "",
                  "| trade | pair | R |", "|---|---|---|"]
        lines += [f"| {t.id} | {t.pair} | {journal.r(t.id):+.2f} |" for t in r.past_stop]
        lines.append("")
    lines += ["### Process", ""]
    if not r.cards:
        lines += [f"No cards written for this period, and {r.days_traded} "
                  f"{_days(r.days_traded)} had trades.", ""]
    else:
        lines += [f"{len(r.cards)} {_cards(len(r.cards))} written, {r.days_traded} "
                  f"{_days(r.days_traded)} had trades.", "",
                  "| process grade | days |", "|---|---|"]
        lines += [f"| {grade} | {n} |" for grade, n in r.grades]
        lines.append("")
    # An empty section stays empty: whatever stands here is loaded into the
    # form as the owner's own text, so a hint would have to be deleted first.
    lines += ["", "## Conclusions", "", conclusions]
    return "\n".join(lines)


def _clean(c):
    if c is None:
        return "-"
    share = "-" if c.clean_share is None else f"{c.clean_share:.0f}%"
    return share + (f" ({c.unticked} not ticked)" if c.unticked else "")


def _trades(n):
    return "trade" if n == 1 else "trades"


def _days(n):
    return "day" if n == 1 else "days"


def _cards(n):
    return "card" if n == 1 else "cards"


def _held(c):
    if c is None or c.held_share is None:
        return "-"
    return f"{c.held_share:.0f}%"


def build(root, journal, period, conclusions=None):
    """Writes the file. Conclusions: the new ones, or the old ones kept."""
    r = compose(root, journal, period)
    text = conclusions if conclusions is not None else previous_conclusions(root, period)
    head = {"period": period, "kind": r.kind,
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M")}
    file = path(root, period)
    os.makedirs(os.path.dirname(file), exist_ok=True)
    tmp = file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(mdfile.dump(head, to_markdown(r, journal, text)))
    os.replace(tmp, file)
    return file


def is_period(period):
    try:
        parse_period(period)
    except ValueError:
        return False
    return True


def existing(root):
    """The periods a report file stands for. A note or a copy left in the
    folder is passed over: the shelf composes every name it gets."""
    folder = os.path.join(root, store.JOURNAL, DIR)
    if not os.path.isdir(folder):
        return []
    names = [i[:-3] for i in os.listdir(folder)
             if i.endswith(".md") and is_period(i[:-3])]
    return sorted(names, reverse=True)


def read(root, period):
    """The header and the body of a report file, or (None, None) when there is
    none. A header edited by hand into something mdfile cannot read gives an
    empty header and the whole text as the body, so the page still opens."""
    file = path(root, period)
    if not os.path.exists(file):
        return None, None
    with open(file, encoding="utf-8") as f:
        text = f.read()
    try:
        return mdfile.parse(text)
    except ValueError:
        return {}, text


# --- the shelf --------------------------------------------------------------

def periods(journal, kind, now=None):
    """Every month (or quarter) from the first one a trade closed in up to the
    one running now, oldest first: the shelf the Reports tab lays them out on,
    a place for each whether a report stands there or not."""
    now = now or datetime.now()
    closed = [t.closed for t in journal.trades if not t.is_open and t.closed]
    if not closed:
        return []
    first = period_of(min(closed), kind)
    last = period_of(now, kind)
    if first > last:
        first, last = last, first
    out, p = [], first
    while p <= last and len(out) < 600:
        out.append(p)
        p = next_period(p)
    return out
