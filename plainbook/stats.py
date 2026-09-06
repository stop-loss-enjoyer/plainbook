#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Summary figures: WR, R and PnL across slices; the equity curve; R distribution.

Only closed trades count: an open one has neither a result nor an R.
"""
import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Summary:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    be: int = 0
    sum_r: float = 0.0
    sum_pnl: float = 0.0
    sum_r_win: float = 0.0
    sum_r_lose: float = 0.0
    sum_r_be: float = 0.0

    @property
    def decided(self):
        """Trades that ended one way or the other: a win or a loss."""
        return self.wins + self.losses

    @property
    def wr(self):
        """The share of wins among the trades that were decided.

        Break-even trades stay out of the denominator: a trade closed at zero
        was neither won nor lost, and diluting the hit rate with it would be
        dishonest. What they do cost (commission, the opportunity spent) is
        fully visible in the sum and the average R, where BE counts like
        everything else."""
        return 100.0 * self.wins / self.decided if self.decided else 0.0

    @property
    def average_r(self):
        """What a closed trade brought on average, in R: the EV.

        Unlike the winrate, it counts the break-evens. A trade closed at zero
        still paid its commission and swap and never comes back at exactly
        zero R, so leaving it out would flatter the figure. The three sums
        below say how much of it came from each kind of trade."""
        return self.sum_r / self.trades if self.trades else 0.0


def summary(journal, trades):
    s = Summary()
    for t in trades:
        if t.is_open:
            continue
        s.trades += 1
        s.wins += t.result == "Win"
        s.losses += t.result == "Lose"
        s.be += t.result == "BE"
        r = journal.r(t.id) or 0.0
        s.sum_r += r
        s.sum_r_win += r if t.result == "Win" else 0.0
        s.sum_r_lose += r if t.result == "Lose" else 0.0
        s.sum_r_be += r if t.result == "BE" else 0.0
        s.sum_pnl += t.pnl or 0.0
    return s


def by_field(journal, trades, key):
    """[(value, Summary)] ordered by the number of trades, descending."""
    return by_values(journal, trades, lambda t: [key(t)])


def by_values(journal, trades, key):
    """The same, for a field a trade can hold several of at once.

    Execution is a list on the trade: one entered on IDM and on SNR stands in
    both rows, so that table counts more trades than the period has. Every
    other slice puts a trade in exactly one row."""
    groups = {}
    for t in trades:
        if t.is_open:
            continue
        for value in key(t) or [""]:
            groups.setdefault(value, []).append(t)
    rows = [(value, summary(journal, xs)) for value, xs in groups.items()]
    rows.sort(key=lambda x: -x[1].trades)
    return rows


# --- playbooks ---------------------------------------------------------------

NO_PLAYBOOK = "no playbook"


@dataclass
class Compliance:
    """How the trades of a playbook went through its checklist."""
    clean: int = 0          # ticked, every rule met
    deviated: int = 0       # ticked, some rule not met
    unticked: int = 0       # tied to the playbook later, never ticked
    held: int = 0           # closed, the management rules ticked and all met
    held_broken: int = 0    # closed, ticked, some management rule not met
    held_unticked: int = 0  # closed without the management ticked

    @property
    def ticked(self):
        return self.clean + self.deviated

    @property
    def clean_share(self):
        """The share of ticked trades that met every rule, or None when
        nothing was ticked: an unticked trade says nothing either way."""
        return 100.0 * self.clean / self.ticked if self.ticked else None

    @property
    def held_ticked(self):
        return self.held + self.held_broken

    @property
    def held_share(self):
        """The same for the management rules, over the closed trades that
        ticked them."""
        return 100.0 * self.held / self.held_ticked if self.held_ticked else None


def compliance(trades):
    c = Compliance()
    for t in trades:
        if t.deviations is None:
            c.unticked += 1
        elif t.deviations:
            c.deviated += 1
        else:
            c.clean += 1
        if t.is_open:
            continue
        if t.exit_deviations is None:
            c.held_unticked += 1
        elif t.exit_deviations:
            c.held_broken += 1
        else:
            c.held += 1
    return c


def by_playbook(journal, trades):
    """[(playbook id or NO_PLAYBOOK, Summary, Compliance)] over the closed
    trades, the playbooks by their number of trades, the trades without one
    last."""
    groups = {}
    for t in trades:
        if t.is_open:
            continue
        groups.setdefault(t.playbook or NO_PLAYBOOK, []).append(t)
    rows = [(pid, summary(journal, xs), compliance(xs)) for pid, xs in groups.items()]
    rows.sort(key=lambda x: (x[0] == NO_PLAYBOOK, -x[1].trades))
    return rows


def by_setup(journal, trades):
    """[(setup, Summary, Compliance)] over the closed trades of one playbook;
    a trade with no setup named stands under '-'."""
    groups = {}
    for t in trades:
        if t.is_open:
            continue
        groups.setdefault(t.setup or "-", []).append(t)
    rows = [(name, summary(journal, xs), compliance(xs)) for name, xs in groups.items()]
    rows.sort(key=lambda x: -x[1].trades)
    return rows


def ticked(t):
    """Whether the trade went through a checklist at all: at the entry, at the
    close, or both. A trade tied to its playbook later and never ticked says
    nothing about the rules."""
    return t.deviations is not None or t.exit_deviations is not None


def broke(t):
    """Whether a ticked trade has a rule marked as not met, at the entry or at
    the close."""
    return bool(t.deviations or t.exit_deviations)


def rule_costs(journal, trades, rules):
    """What each rule cost: for every rule, (rule, how many ticked trades
    broke it, Summary of those trades). Alongside, the Summary of the trades
    that met every rule, which is what a broken rule is measured against.

    Only ticked trades take part, ticked at the entry or at the close: a trade
    tied to the playbook later and never ticked says nothing about any rule.
    Open trades are counted as breaking a rule but
    carry no R yet, the Summary being of closed trades. The management rules
    are in the same table, their breaks read from the close; the measure is
    the trades that kept every rule, at the entry and after."""
    held = [t for t in trades if ticked(t)]
    clean = summary(journal, [t for t in held if not broke(t)])
    rows = []
    for r in rules:
        missed = [t for t in held
                  if r.number in (t.deviations or []) or r.number in (t.exit_deviations or [])]
        rows.append((r, len(missed), summary(journal, missed)))
    return rows, clean


def _figure(limits, key):
    try:
        return float(str(limits.get(key, "")).replace(",", "."))
    except ValueError:
        return None


def frame(journal, playbook, now=None):
    """The limits of a playbook held against its trades at this moment, for
    the form of a new trade: [(what, value, limit, reached)]. A count that
    has reached its limit is flagged, because the trade being opened would
    go past it; the loss of the week is flagged once it has reached the
    fuse. Nothing is refused, the figures are only shown."""
    now = now or datetime.now()
    limits = dict(playbook.limits)
    own = [t for t in journal.trades if t.playbook == playbook.id]
    this_week, this_month = week(now), f"{now:%Y-%m}"
    rows = []
    n = _figure(limits, "max per week")
    if n is not None:
        count = sum(1 for t in own if t.opened and week(t.opened) == this_week)
        rows.append(("trades this week", count, n, count >= n))
    n = _figure(limits, "max per month")
    if n is not None:
        count = sum(1 for t in own if t.opened and f"{t.opened:%Y-%m}" == this_month)
        rows.append(("trades this month", count, n, count >= n))
    n = _figure(limits, "weekly loss limit")
    if n is not None:
        r = sum(journal.r(t.id) or 0.0 for t in own
                if not t.is_open and t.closed and week(t.closed) == this_week)
        rows.append(("R this week", r, -n, r <= -n))
    n = _figure(limits, "open at once")
    if n is not None:
        count = sum(1 for t in own if t.is_open)
        rows.append(("open now", count, n, count >= n))
    return rows


_ENTRY = re.compile(r"^\*\*\d\d\.\d\d\.\d{4}\*\*:")


def reviews_written(playbook):
    """How many dated entries the review holds: one per block reviewed. An
    entry starts with the date the page stamps it with; a bold word inside
    an entry is not one."""
    return sum(1 for line in playbook.review.split("\n") if _ENTRY.match(line))


def review_due(playbook, count):
    """Has a block run its course without its review: the trades make more
    full blocks than there are reviews."""
    if not playbook.block:
        return False
    return count // playbook.block > reviews_written(playbook)


def drawdown_r(journal, trades):
    """The deepest fall of the cumulative R curve, zero or negative.

    The trades are taken in the order they closed, because that is the order
    the account felt them: a trade opened first but closed last moves the curve
    last. Says how far the equity went below its own high inside the selection,
    which the total R of the period does not show."""
    curve = sorted((t.closed, journal.r(t.id) or 0.0) for t in trades
                   if not t.is_open and t.closed)
    peak = total = worst = 0.0
    for _, r in curve:
        total += r
        peak = max(peak, total)
        worst = min(worst, total - peak)
    return worst


# The R buckets of the two rings. Coarse at the tails on purpose: a ring is
# only readable up to about six slices, and the difference between +3R and +4R
# matters less than the difference between a small win and a big one.
#
# The losses are cut where a stop actually lands. A trade taken to the stop
# comes back a little worse than -1R, because commission and swap are paid on
# top of it, so -1 to -1.2 is one bucket: the stop, as designed. Anything past
# -1.2 was not the stop but too much size, and it is kept apart to be seen.
# Every bucket holds its lower edge and not its upper one, so exactly -1R is a
# stop and not a loss that stayed short of it.
# A label reads from zero outwards, like the wins, and the far edge of a bucket
# belongs to the next one: exactly -1R is in "-1…-1.2", the stop.
LOSS_BUCKETS = [("0…-0.5", 0.5), ("-0.5…-1", 1.0), ("-1…-1.2", 1.2),
                ("-1.2R and worse", None)]
WIN_BUCKETS = [("0…+0.5", 0.5), ("+0.5…+1", 1.0), ("+1…+2", 2.0),
               ("+2…+3", 3.0), ("+3R and more", None)]


def _bucket(buckets, size):
    for i, (label, top) in enumerate(buckets):
        if top is None or size < top:
            return i, label
    return len(buckets) - 1, buckets[-1][0]


def r_split(journal, trades):
    """Closed trades cut into two ordered piles: [(label, count, sum_r)] for
    the losses and for the wins, then the break-evens.

    The pile is chosen by the result, not by the sign of R, so these counts are
    the same wins and losses the winrate is built from. Inside a pile the
    bucket is chosen by the size of R."""
    piles = {"Lose": [[label, 0, 0.0] for label, _ in LOSS_BUCKETS],
             "Win": [[label, 0, 0.0] for label, _ in WIN_BUCKETS]}
    be = 0
    for t in trades:
        if t.is_open:
            continue
        r = journal.r(t.id) or 0.0
        if t.result == "BE":
            be += 1
            continue
        if t.result not in piles:
            continue
        buckets = LOSS_BUCKETS if t.result == "Lose" else WIN_BUCKETS
        i, _ = _bucket(buckets, abs(r))
        piles[t.result][i][1] += 1
        piles[t.result][i][2] += r
    return ([tuple(row) for row in piles["Lose"]],
            [tuple(row) for row in piles["Win"]], be)


def equity(journal, account_id=None, trades=None, since=None):
    """Points of (date, balance), as in balances, but honouring the filter.

    Everything that happened before `since` is folded into the first point,
    whatever the selection says: a curve that starts in August starts at the
    balance the account had in August, not at the day it was opened. From
    `since` on only the chosen trades move the line, so a selection by style
    or by pair draws what those trades alone did to the account."""
    return [(day, balance) for day, balance, what in
            equity_events(journal, account_id, trades, since) if what != "start"]


def equity_events(journal, account_id=None, trades=None, since=None):
    """The equity walk with a word on what moved each point.

    Every point is (date, balance, what): `what` is None for a trade, the
    Adjustment for money that moved outside a trade, "start" for the opening
    balance placed before the first event, or "since" for the balance the
    period was entered with. The chart marks the adjustments, so that a
    deposit is not read as a big win; the balances are the ones of `equity`."""
    chosen = None if trades is None else {t.id for t in trades}
    start = sum(acc.start_balance for a, acc in journal.accounts.items()
                if account_id in (None, a))
    events = [(c.day, c.amount, c) for c in journal.adjustments
              if account_id in (None, c.account)]
    events += [(t.closed, t.pnl or 0.0, None) for t in journal.trades
               if not t.is_open and t.closed
               and (chosen is None or t.id in chosen
                    or (since is not None and t.closed < since))
               and account_id in (None, t.account)]
    events.sort(key=lambda e: e[0])
    points, b = [], start
    for day, amount, what in events:
        if not points:
            if since is None:
                points.append((day, b, "start"))
            elif day >= since:
                points.append((since, b, "since"))
        b += amount
        if since is None or day >= since:
            points.append((day, b, what))
    return points


def streaks(journal, trades):
    """Runs of wins and of losses, in the order the trades closed.

    Returns (longest run of wins, longest run of losses, the run going on now)
    where the last is (result, length). Break-evens neither extend a run nor
    break it: a trade that ended at zero says nothing about the streak."""
    closed = sorted((t for t in trades if not t.is_open and t.closed),
                    key=lambda t: (t.closed, t.id))
    best_win = best_loss = 0
    current, length = None, 0
    for t in closed:
        if t.result not in ("Win", "Lose"):
            continue
        if t.result == current:
            length += 1
        else:
            current, length = t.result, 1
        if current == "Win":
            best_win = max(best_win, length)
        else:
            best_loss = max(best_loss, length)
    return best_win, best_loss, (current, length)


def months(trades):
    """Months as 'YYYY-MM' by the entry, oldest first: what the list filters by."""
    return sorted({f"{t.opened:%Y-%m}" for t in trades})


def closing_months(trades):
    """Months as 'YYYY-MM' by the exit, oldest first: what a report is built for."""
    return sorted({f"{t.closed:%Y-%m}" for t in trades if not t.is_open and t.closed})


def quarter(date):
    return f"{date.year}-Q{(date.month - 1) // 3 + 1}"


def week(date):
    """The trading week as an ISO key, 'YYYY-Www', Monday being the first day.

    The year comes from the ISO calendar rather than from the date itself: a
    week that straddles New Year belongs wholly to the year ISO gives it.
    """
    year, number, _ = date.isocalendar()
    return f"{year}-W{number:02d}"
