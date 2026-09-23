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

R = PnL / (risk% x balance at entry), for a break-even as for the rest: a trade
called break-even still paid its commission, and that small R is real.
"""
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import store


@dataclass
class Computed:
    """What has been worked out for a single trade."""
    balance_at_entry: float          # computed account balance at entry
    risk_money: float                # how many dollars were at risk
    r: float = None                  # None for open trades


class Journal:
    """The whole journal: accounts, trades, adjustments and everything derived."""

    def __init__(self, accounts, trades, adjustments, problems=None,
                 stop_edge=store.STOP_EDGE, clock=""):
        self.accounts = accounts                # {id: Account}
        self.stop_edge = stop_edge              # where a stop ends and an overrun begins, in R
        self.clock = clock                      # the clock the times are written in, "" local
        self.trades = sorted(trades, key=lambda t: (t.opened or datetime.max, t.id))
        self.adjustments = sorted(adjustments,
                                  key=lambda c: (c.day or datetime.max, c.id))
        self.problems = list(problems or [])    # (path, reason) of files skipped
        self.computed = self._replay()

    @classmethod
    def load(cls, root="."):
        """Reads the journal. A file that does not load is left out and named
        in `problems`, so that one broken record does not take the rest down."""
        problems = []
        return cls(store.all_accounts(root, problems),
                   store.all_trades(root, problems),
                   store.all_adjustments(root, problems), problems,
                   store.stop_edge(root), store.clock(root))

    # --- replay ------------------------------------------------------------

    def _replay(self):
        """For every trade: the balance at entry, the risk in money and R.

        A close that carries the hour belongs to the balance of a trade opened
        later that day and not to one opened earlier, so there is no single
        order of events to play: each entry asks which movements came before
        it, by the rule of `_before`. The movements of an account are sorted
        once and summed up as they go, so each question is a lookup rather
        than a walk through the whole history, which with a few thousand
        trades took seconds on every page."""
        ledgers = {}
        for e in self._events():
            ledgers.setdefault(e[2], []).append(e)
        ledgers = {a: _Ledger(events) for a, events in ledgers.items()}
        computed = {}
        for t in self.trades:
            ledger = ledgers.get(t.account)
            b = self._start(t.account)
            if ledger is not None:
                b += ledger.before(t)
            risk_money = b * (t.risk or 0.0) / 100.0
            r = None
            if not t.is_open:
                r = 0.0 if risk_money == 0 else (t.pnl or 0.0) / risk_money
            computed[t.id] = Computed(balance_at_entry=b, risk_money=risk_money, r=r)
        return computed

    def _events(self):
        """(moment, kind, account, amount, hour is known, the trade it came
        from) for every movement of money, kind 0 an adjustment, 1 a close."""
        events = []
        for c in self.adjustments:
            events.append((c.day, 0, c.account, c.amount, c.day_time, None))
        for t in self.trades:
            if not t.is_open and t.closed is not None:
                events.append((t.closed, 1, t.account, t.pnl or 0.0,
                               t.closed_time, t.id))
        return events

    # --- slices ------------------------------------------------------------

    def balance(self, account_id):
        """The current computed balance of an account."""
        b = self._start(account_id)
        b += sum(c.amount for c in self.adjustments if c.account == account_id)
        b += sum(t.pnl or 0.0 for t in self.trades
                 if t.account == account_id and not t.is_open)
        return b

    def balance_at(self, account_id, moment, timed=True, trade_id=None):
        """The balance an entry at `moment` is measured against, by the same
        rule the replay uses: what a trade opened then would find. A trade
        written in afterwards for a day already past is sized on the balance
        of that day and not on the one of today."""
        entry = _Entry(moment, timed)
        return self._start(account_id) + sum(
            e[3] for e in self._events()
            if e[2] == account_id and (trade_id is None or e[5] != trade_id)
            and _before(e, entry))

    def history(self, account_id, leave_out=None):
        """The events of an account as the form script replays them for its
        hint: (moment, is an adjustment, the hour is known, amount), the
        trade `leave_out` not among them."""
        return [(f"{e[0]:%Y-%m-%dT%H:%M}", e[1] == 0, bool(e[4]), e[3])
                for e in self._events()
                if e[2] == account_id and (leave_out is None or e[5] != leave_out)]

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

    def currency(self, account_id=None):
        """The currency an amount is in. For one account, its own; for a
        figure that spans accounts, the one they all share, or nothing when
        they differ, because such a sum has no currency to be named in."""
        if account_id is not None:
            account = self.accounts.get(account_id)
            return account.currency if account else "USD"
        names = {a.currency for a in self.accounts.values() if not a.archived} \
            or {a.currency for a in self.accounts.values()}
        return names.pop() if len(names) == 1 else ""

    def closed_on(self, account_id, day):
        """What an account made or lost on that day: the PnL of the trades
        closed on it and the fees charged on it. A prop firm counts a fee in
        the loss of the day, and so does the daily limit."""
        return sum(t.pnl or 0.0 for t in self.trades
                   if t.account == account_id and not t.is_open and t.closed
                   and t.closed.date() == day.date()) + sum(
            c.amount for c in self.adjustments
            if c.account == account_id and c.kind == "fee"
            and c.day.date() == day.date())

    # --- the rules of a prop firm ------------------------------------------

    def now(self):
        """This moment on the clock the journal is written in."""
        tz = store.zone(self.clock)
        return datetime.now(tz).replace(tzinfo=None) if tz else datetime.now()

    def firm_day(self, account, now=None):
        """(start, end, the firm's clock was found) of the day the firm counts
        now, as moments on the journal's clock. A firm's day begins at its own
        hour on its own clock, midnight in Prague for one, five in the
        afternoon in New York for another, and a trade written at 23:30 on the
        journal's clock may belong to the firm's next day."""
        now = now or self.now()
        hour, minute = (int(x) for x in (account.day_start or "00:00").split(":"))
        firm = store.zone(account.zone)
        found = firm is not None or not account.zone
        if firm is None:
            start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now < start:
                start -= timedelta(days=1)
            return start, start + timedelta(days=1), found
        home = store.zone(self.clock)
        here = now.replace(tzinfo=home) if home else now.astimezone()
        there = here.astimezone(firm)
        start = there.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if there < start:
            start = _wall(start, -1, firm)
        end = _wall(start, 1, firm)
        back = (lambda m: m.astimezone(home).replace(tzinfo=None)) if home else \
            (lambda m: m.astimezone().replace(tzinfo=None))
        return back(start), back(end), found

    def prop(self, account_id, now=None):
        """Where a prop account stands against the rules of its firm, worked
        out afresh from the journal: nothing of it is stored."""
        a = self.accounts[account_id]
        now = now or self.now()
        start, end, found = self.firm_day(a, now)
        p = PropState(account=a, day_from=start, day_until=end, zone_found=found)
        for t in self.trades:
            if t.account != account_id or t.is_open or t.closed is None:
                continue
            inside = (start <= t.closed < end if t.closed_time
                      else t.closed.date() == now.date())
            if inside:
                p.today += t.pnl or 0.0
        for c in self.adjustments:
            if c.account == account_id and c.kind == "fee":
                inside = (start <= c.day < end if getattr(c, "day_time", False)
                          else c.day.date() == now.date())
                if inside:
                    p.today += c.amount
        p.at_risk = self.open_risk(account_id)
        p.balance = self.balance(account_id)
        p.made = self.result(account_id)
        p.days = len({t.opened.date() for t in self.trades
                      if t.account == account_id and t.opened})
        if a.max_loss is not None:
            high = running = a.start_balance
            for e in sorted(self._events(), key=lambda e: e[0]):
                if e[2] == account_id:
                    running += e[3]
                    high = max(high, running)
            floor = a.start_balance - a.max_loss
            if a.max_loss_mode == "trailing":
                floor = high - a.max_loss
            elif a.max_loss_mode == "trailing to start":
                floor = min(high - a.max_loss, a.start_balance)
            p.floor, p.high = floor, high
        return p

    def open_risk(self, account_id):
        """The money at stake in the open trades of an account.

        A trade whose stop stands at the entry can no longer lose what it
        was sized for, so it is not in the sum: the risk it was opened with
        is freed for the next trade, and a limit counting the open risk
        does not see it. Its R is still measured against that risk."""
        return sum(self.computed[t.id].risk_money for t in self.trades
                   if t.account == account_id and t.is_open
                   and t.breakeven is None)

    def at_breakeven(self, account_id=None):
        """The open trades whose stop stands at the entry."""
        return [t for t in self.trades if t.is_open and t.breakeven is not None
                and (account_id is None or t.account == account_id)]

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
    if kind == 0:
        # money moved with its hour counts from that moment for an entry that
        # has one; without, from its day on, the whole day
        if timed and trade.opened_time:
            return day <= entry
        return day.date() <= entry.date()
    if timed and trade.opened_time:   # both hours are known: compare moments
        return day <= entry
    return day.date() < entry.date()  # PnL counts from the day after the close


@dataclass
class PropState:
    """A prop account against its rules at one moment. Every figure is money
    in the currency of the account; a rule the firm does not have is None."""
    account: object
    day_from: datetime = None       # the firm's day, on the journal's clock
    day_until: datetime = None
    zone_found: bool = True         # False: the firm's clock is unknown here
    today: float = 0.0              # closed today, fees included
    at_risk: float = 0.0            # what the open trades can still lose at their stops
    balance: float = 0.0
    made: float = 0.0               # the result of the account, money moved in and out aside
    days: int = 0                   # days with an entry
    floor: float = None             # the balance the account may not close under
    high: float = None              # the highest closed balance, for a trailing floor

    @property
    def daily_used(self):
        return max(0.0, -self.today) + self.at_risk

    @property
    def daily_left(self):
        limit = self.account.daily_loss_limit
        return None if limit is None else limit - self.daily_used

    @property
    def floor_left(self):
        """How far the balance stands above the floor, and at the stops of
        the open trades."""
        return None if self.floor is None else self.balance - self.floor

    @property
    def floor_left_at_stops(self):
        return None if self.floor is None else self.balance - self.at_risk - self.floor

    @property
    def target_left(self):
        target = self.account.profit_target
        return None if target is None else max(0.0, target - self.made)

    @property
    def days_left(self):
        need = self.account.min_days
        return None if need is None else max(0, need - self.days)

    @property
    def breached(self):
        """A rule broken: the day past its limit, or the balance on the floor."""
        limit = self.account.daily_loss_limit
        return ((limit is not None and max(0.0, -self.today) >= limit)
                or (self.floor is not None and self.balance <= self.floor))

    @property
    def passed(self):
        """The target made, the days traded, no rule broken; None when the
        firm sets no target."""
        if self.account.profit_target is None:
            return None
        return (not self.breached and self.target_left == 0
                and (self.days_left or 0) == 0)


def _wall(moment, days, zone):
    """The same hour on the wall `days` days away, whatever the clocks did on
    the way: a day with a change of summer time is 23 or 25 hours long."""
    day = (moment.replace(tzinfo=None) + timedelta(days=days))
    return day.replace(tzinfo=zone)


class _Entry:
    """An entry that is not a trade yet, for `_before`."""
    def __init__(self, opened, opened_time):
        self.opened, self.opened_time = opened, opened_time


class _Ledger:
    """The movements of one account, sorted three ways with running sums,
    to answer `_before` for many entries at once.

    An adjustment counts from its day, or from its moment when both it and
    the entry carry an hour. A close counts from the next day, except that a
    close with an hour counts from its moment for an entry that has one too;
    and a trade never counts in its own balance, which only matters for one
    closed within the minute it was opened."""

    def __init__(self, events):
        moves = [e for e in events if e[1] == 0]
        adjustments = sorted((e[0].date(), e[3]) for e in moves)
        self.moves_dated = _Sums(sorted((e[0].date(), e[3]) for e in moves if not e[4]))
        self.moves_timed = _Sums(sorted((e[0], e[3]) for e in moves if e[4]))
        closes = [e for e in events if e[1] == 1]
        by_day = sorted((e[0].date(), e[3]) for e in closes)
        timed = sorted((e[0], e[3]) for e in closes if e[4])
        untimed = sorted((e[0].date(), e[3]) for e in closes if not e[4])
        self.pnl = {e[5]: (e[0], e[3], e[4]) for e in closes}
        self.adjustments, self.by_day, self.timed, self.untimed = (
            _Sums(adjustments), _Sums(by_day), _Sums(timed), _Sums(untimed))

    def before(self, trade):
        entry = trade.opened
        day = entry.date()
        if trade.opened_time:
            b = self.moves_dated.up_to(day) + self.moves_timed.up_to(entry)
            b += self.timed.up_to(entry) + self.untimed.below(day)
            own = self.pnl.get(trade.id)
            if own is not None and own[2] and own[0] <= entry:
                b -= own[1]
        else:
            b = self.adjustments.up_to(day) + self.by_day.below(day)
        return b


class _Sums:
    """Sorted (key, amount) pairs and the running sum of the amounts."""

    def __init__(self, pairs):
        self.keys = [k for k, _ in pairs]
        self.sums = [0.0]
        for _, amount in pairs:
            self.sums.append(self.sums[-1] + amount)

    def up_to(self, key):
        return self.sums[bisect_right(self.keys, key)]

    def below(self, key):
        return self.sums[bisect_left(self.keys, key)]

