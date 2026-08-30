#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic balances and R.

Account balance = start balance + sum of PnL of closed trades + adjustments.
Risk in dollars and R are measured against the balance AT THE MOMENT OF ENTRY,
not against a fixed number — otherwise 1% of risk would always look like the
same amount of money no matter how the account has grown.

Order of events when replaying the history:
  - an adjustment counts from its own date, inclusive;
  - a trade's PnL counts from the CLOSING date, and does not affect an entry
    made the same day (a trade closed today does not change today's entry).

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
        """For every trade: the balance at entry, the risk in money and R."""
        events = []                             # (date, order, account, amount)
        for c in self.adjustments:
            events.append((c.day, 0, c.account, c.amount))
        for t in self.trades:
            if not t.is_open and t.closed is not None:
                events.append((t.closed, 1, t.account, t.pnl or 0.0))
        events.sort(key=lambda e: (e[0], e[1]))

        balance = {a: acc.start_balance for a, acc in self.accounts.items()}
        computed, i = {}, 0
        for t in self.trades:
            # play everything that happened before the entry day
            # (adjustments including that day)
            while i < len(events) and _before(events[i], t.opened):
                _, _, account, amount = events[i]
                balance[account] = balance.get(account, 0.0) + amount
                i += 1
            b = balance.get(t.account, 0.0)
            risk_money = b * (t.risk or 0.0) / 100.0
            r = None
            if not t.is_open:
                r = 0.0 if risk_money == 0 else (t.pnl or 0.0) / risk_money
            computed[t.id] = Computed(balance_at_entry=b, risk_money=risk_money, r=r)
        return computed

    # --- slices ------------------------------------------------------------

    def balance(self, account_id):
        """The current computed balance of an account."""
        account = self.accounts.get(account_id)
        b = account.start_balance if account else 0.0
        b += sum(c.amount for c in self.adjustments if c.account == account_id)
        b += sum(t.pnl or 0.0 for t in self.trades
                 if t.account == account_id and not t.is_open)
        return b

    def balances(self):
        return {a: self.balance(a) for a in self.accounts}

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


def _before(event, entry):
    """Does this event affect the balance by the moment of entry?"""
    day, order = event[0], event[1]
    if order == 0:                    # an adjustment counts from its date on
        return day.date() <= entry.date()
    return day.date() < entry.date()  # PnL counts from the day after the close
