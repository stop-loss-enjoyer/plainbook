#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Summary figures: WR, R and PnL across slices; the equity curve; R distribution.

Only closed trades count — an open one has neither a result nor an R.
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
        dishonest. What they do cost — commission, the opportunity spent — is
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
    groups = {}
    for t in trades:
        if t.is_open:
            continue
        groups.setdefault(key(t), []).append(t)
    rows = [(value, summary(journal, xs)) for value, xs in groups.items()]
    rows.sort(key=lambda x: -x[1].trades)
    return rows


def r_distribution(journal, trades, step=0.5, limit=4.0):
    """R histogram: [(left edge, right edge, count)]. Tails fold into the edges."""
    buckets = {}
    n = int(limit / step)
    for t in trades:
        if t.is_open:
            continue
        r = journal.r(t.id) or 0.0
        i = int(r // step)
        i = max(-n, min(n - 1, i))
        buckets[i] = buckets.get(i, 0) + 1
    if not buckets:
        return []
    low, high = min(buckets), max(buckets)
    return [(i * step, (i + 1) * step, buckets.get(i, 0)) for i in range(low, high + 1)]


def equity(journal, account_id=None, trades=None):
    """Points of (date, balance) — as in balances, but honouring the filter."""
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
