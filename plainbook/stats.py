#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Summary figures: WR, R and PnL across slices; the equity curve; R distribution.

Only closed trades count: an open one has neither a result nor an R.
"""
from dataclasses import dataclass


@dataclass
class Summary:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    be: int = 0
    sum_r: float = 0.0
    sum_pnl: float = 0.0

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
        s.sum_r += journal.r(t.id) or 0.0
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
LOSS_BUCKETS = [("-0.5…0", 0.5), ("-1.0…-0.5", 1.0), ("-1R and worse", None)]
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


def equity(journal, account_id=None, trades=None):
    """Points of (date, balance), as in balances, but honouring the filter."""
    if trades is None:
        return journal.equity(account_id)
    chosen = {t.id for t in trades}
    start = sum(acc.start_balance for a, acc in journal.accounts.items()
                if account_id in (None, a))
    events = [(c.day, c.amount) for c in journal.adjustments
              if account_id in (None, c.account)]
    events += [(t.closed, t.pnl or 0.0) for t in journal.trades
               if not t.is_open and t.closed and t.id in chosen
               and account_id in (None, t.account)]
    events.sort(key=lambda e: e[0])
    points, b = [], start
    for day, amount in events:
        b += amount
        points.append((day, b))
    return points


def months(trades):
    """Months as 'YYYY-MM', oldest first."""
    return sorted({f"{t.opened:%Y-%m}" for t in trades})


def quarter(date):
    return f"{date.year}-Q{(date.month - 1) // 3 + 1}"


def week(date):
    """The trading week as an ISO key, 'YYYY-Www', Monday being the first day.

    The year comes from the ISO calendar rather than from the date itself: a
    week that straddles New Year belongs wholly to the year ISO gives it.
    """
    year, number, _ = date.isocalendar()
    return f"{year}-W{number:02d}"
