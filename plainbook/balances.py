#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic balances and R.

Account balance = start balance + sum of PnL of closed trades + adjustments.
Risk in dollars and R are measured against the balance AT THE MOMENT OF ENTRY,
not against a fixed number, or 1% of risk would always look like the
same amount of money no matter how the account has grown.

Order of events when replaying the history:
  - an adjustment counts from its own date, inclusive;
  - a trade's PnL counts from the moment of the close when the exit carries an
    hour and the entry does too, so a trade closed at noon is already in the
    balance of one opened at three and is not in the balance of one opened at
    nine;
  - without those hours the PnL counts from the day after the close, because a
    date alone cannot say which of the two came first.

R = PnL / (risk% x balance at entry). For BE, R is 0.
"""
from dataclasses import dataclass
from datetime import datetime

from . import store


@dataclass
class Computed:
    """What has been worked out for a single trade."""
    balance_at_entry: float          # computed account balance at entry
    risk_money: float                # how many dollars were at risk
    r: float = None                  # None for open trades


class Journal:
    """The whole journal: accounts, trades, adjustments and everything derived."""

    def __init__(self, accounts, trades, adjustments):
        self.accounts = accounts                # {id: Account}
        self.trades = sorted(trades, key=lambda t: (t.opened or datetime.max, t.id))
        self.adjustments = sorted(adjustments,
                                  key=lambda c: (c.day or datetime.max, c.id))
        self.computed = self._replay()

    @classmethod
    def load(cls, root="."):
        return cls(store.all_accounts(root), store.all_trades(root),
                   store.all_adjustments(root))

    # --- replay ------------------------------------------------------------

    def _replay(self):
        """For every trade: the balance at entry, the risk in money and R.

        Every event is weighed against every entry instead of being played once
        in order. A close that carries the hour belongs to the balance of a
        trade opened later that day and not to one opened earlier, and a single
        pass through a list of events cannot give both answers on one day."""
        events = []            # (moment, kind, account, amount, hour is known)
        for c in self.adjustments:
            events.append((c.day, 0, c.account, c.amount, False))
        for t in self.trades:
            if not t.is_open and t.closed is not None:
                events.append((t.closed, 1, t.account, t.pnl or 0.0,
                               t.closed_time))

        computed = {}
        for t in self.trades:
            b = self._start(t.account) + sum(
                e[3] for e in events if e[2] == t.account and _before(e, t))
            risk_money = b * (t.risk or 0.0) / 100.0
            r = None
            if not t.is_open:
                r = 0.0 if risk_money == 0 else (t.pnl or 0.0) / risk_money
            computed[t.id] = Computed(balance_at_entry=b, risk_money=risk_money, r=r)
        return computed

    # --- slices ------------------------------------------------------------

    def balance(self, account_id):
        """The current computed balance of an account."""
        b = self._start(account_id)
        b += sum(c.amount for c in self.adjustments if c.account == account_id)
        b += sum(t.pnl or 0.0 for t in self.trades
                 if t.account == account_id and not t.is_open)
        return b

    def balances(self):
        return {a: self.balance(a) for a in self.accounts}

    def cashed_out(self, account_id):
        """How much has been taken off the account, as a positive number.

        Withdrawals are the one movement worth a running total: money that left
        the account is not a loss, and without this figure the growth of an
        account that pays out looks worse than it was."""
        return -sum(c.amount for c in self.adjustments
                    if c.account == account_id and c.kind == "withdrawal")

    def deposited(self, account_id):
        return sum(c.amount for c in self.adjustments
                   if c.account == account_id and c.kind == "deposit")

    def result(self, account_id):
        """What the account earned by itself: the balance less the money moved
        in and out. Trading PnL plus fees and reconciliations, so that
        start + result + deposited - cashed out is exactly the balance."""
        return (self.balance(account_id) - self._start(account_id)
                - self.deposited(account_id) + self.cashed_out(account_id))

    def _start(self, account_id):
        account = self.accounts.get(account_id)
        return account.start_balance if account else 0.0

    def risk_in_money(self, account_id, risk_percent):
        """A hint for the form: how many dollars that is right now."""
        return self.balance(account_id) * risk_percent / 100.0

    def r(self, trade_id):
        computed = self.computed.get(trade_id)
        return computed.r if computed else None

    def open_trades(self):
        return [t for t in self.trades if t.is_open]

    def equity(self, account_id=None):
        """Points of (date, balance) at every close and adjustment."""
        start = sum(acc.start_balance for a, acc in self.accounts.items()
                    if account_id in (None, a))
        events = [(c.day, c.amount) for c in self.adjustments
                  if account_id in (None, c.account)]
        events += [(t.closed, t.pnl or 0.0) for t in self.trades
                   if not t.is_open and t.closed and account_id in (None, t.account)]
        events.sort(key=lambda e: e[0])
        points, b = [], start
        for day, amount in events:
            b += amount
            points.append((day, b))
        return points


def _before(event, trade):
    """Does this event affect the balance by the moment of entry?"""
    day, kind, timed = event[0], event[1], event[4]
    entry = trade.opened
    if kind == 0:                     # an adjustment counts from its date on
        return day.date() <= entry.date()
    if timed and trade.opened_time:   # both hours are known: compare moments
        return day <= entry
    return day.date() < entry.date()  # PnL counts from the day after the close
