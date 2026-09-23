#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Summary figures: WR, R and PnL across slices; the equity curve; R distribution.

Only closed trades count: an open one has neither a result nor an R.
"""
import copy
import math
import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta


# Below this many decided trades a winrate is a coincidence and not a rate:
# one trade is 100% or 0%, three trades move by a third at a time. The figure
# is greyed rather than hidden, because the trades behind it are real. It is
# not a confidence interval: there is nothing here to compute one with, and a
# band would be read as a promise.
THIN = 5


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
    gross_won: float = 0.0          # the money of the trades that made money
    gross_lost: float = 0.0         # the money of the ones that lost it, positive

    @property
    def profit_factor(self):
        """The money made for every unit of money lost, or None with nothing
        lost. The payoff says the same in R, trade by trade; this one is the
        account's, fees and sizes included."""
        return self.gross_won / self.gross_lost if self.gross_lost else None

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

    @property
    def average_win(self):
        """What a winning trade brought on average, in R, or None with no win."""
        return self.sum_r_win / self.wins if self.wins else None

    @property
    def average_loss(self):
        """What a losing trade cost on average, in R and negative, or None
        with no loss."""
        return self.sum_r_lose / self.losses if self.losses else None

    @property
    def payoff(self):
        """How many R a win brings for every R a loss costs, or None when
        there is no win and loss to weigh against each other.

        Break-evens are on neither side of it, the same trades the winrate
        leaves out; what they cost is in the EV."""
        win, lose = self.average_win, self.average_loss
        if win is None or lose is None or win <= 0 or lose >= 0:
            return None
        return win / -lose

    @property
    def needed_wr(self):
        """The winrate this selection would need to come out at zero, in
        percent, or None when there is no win and loss to weigh.

            wins * W + losses * L + sum_r_be = 0,   wins = p * decided
            p = (-L - sum_r_be / decided) / (W - L)

        The break-evens are charged into it on purpose. Written the textbook
        way, 100 / (1 + payoff), the figure would be worked out from the wins
        and the losses alone while the EV beside it counts the break-evens
        too, and a selection full of them could then read "needs 33%, has 40%"
        two tiles away from a negative EV. With the term above, the winrate
        stands over this figure exactly when the sum of R stands over zero."""
        win, lose = self.average_win, self.average_loss
        if win is None or lose is None or win - lose <= 0:
            return None
        return 100.0 * (-lose - self.sum_r_be / self.decided) / (win - lose)

    @property
    def thin(self):
        """Too few decided trades for the winrate to be read as a rate."""
        return self.decided < THIN


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
        s.gross_won += max(0.0, t.pnl or 0.0)
        s.gross_lost += max(0.0, -(t.pnl or 0.0))
    return s


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


# --- prices ------------------------------------------------------------------
# A trade may carry the prices it was planned and run at. The stop distance
# is 1 R by price, so every other price reads in R on its own: the target is
# the RR that was planned, the best price is how far the trade went for you
# (MFE), the worst how far against (MAE), the exit what was taken. None
# where a price is missing.

@dataclass
class Prices:
    planned: float = None       # the RR of the target
    taken: float = None         # the exit, in R by price
    best: float = None          # the furthest the market went for the trade, in R
    worst: float = None         # the furthest it went against, in R, zero or negative

    @property
    def left(self):
        """What the trade gave back from its best: the R it reached and did
        not take."""
        if self.best is None or self.taken is None:
            return None
        return max(0.0, self.best - self.taken)

    @property
    def reached(self):
        """Did the market reach the target, whether or not it was taken."""
        if self.planned is None:
            return None
        far = max(x for x in (self.best, self.taken, -1e9) if x is not None)
        return far >= self.planned - 1e-9


def prices(t):
    """The prices of a trade in R, or None without an entry and a stop."""
    if t.entry_price is None or t.stop_price is None:
        return None
    side = 1 if t.direction == "long" else -1
    one_r = (t.entry_price - t.stop_price) * side
    if one_r <= 0:
        return None
    at = lambda price: None if price is None else (price - t.entry_price) * side / one_r
    worst = at(t.worst_price)
    return Prices(planned=at(t.target_price), taken=at(t.exit_price),
                  best=at(t.best_price), worst=None if worst is None else min(0.0, worst))


@dataclass
class PriceSummary:
    trades: int = 0             # closed trades with an entry and a stop
    planned: list = field(default_factory=list)
    reached: int = 0            # of the ones with a target, how many got there
    best: list = field(default_factory=list)
    worst: list = field(default_factory=list)
    left: list = field(default_factory=list)   # given back, of the winners

    @staticmethod
    def mean(xs):
        return sum(xs) / len(xs) if xs else None


def price_summary(trades):
    """What the prices of the closed trades say together: the RR planned,
    how often the target was reached, how far the trades went for and
    against, and what the winners gave back from their best."""
    out = PriceSummary()
    for t in trades:
        if t.is_open:
            continue
        p = prices(t)
        if p is None:
            continue
        out.trades += 1
        if p.planned is not None:
            out.planned.append(p.planned)
            out.reached += bool(p.reached)
        if p.best is not None:
            out.best.append(p.best)
        if p.worst is not None:
            out.worst.append(p.worst)
        if t.result == "Win" and p.left is not None:
            out.left.append(p.left)
    return out


# --- one position on several accounts ----------------------------------------
# A trade taken on a prop account and on one's own is entered once and written
# twice, one file per account (the duplicate of the trade form). For the money
# both are real; for the system they are one decision, and counted twice they
# double the sample, the streak and the fall in R. The Statistics tab can read
# them either way; nothing is stored about it, the copies are found the way
# the trade form finds them: the same pair, side and entry on another account.

def twin_key(t):
    return (t.pair, t.direction, t.opened)


def copies(trades):
    """How many closed trades of a selection repeat a position already counted
    on another account."""
    seen, extra = {}, 0
    for t in trades:
        if t.is_open:
            continue
        accounts = seen.setdefault(twin_key(t), set())
        if accounts and t.account not in accounts:
            extra += 1
        accounts.add(t.account)
    return extra


class Ideas:
    """A journal read with the copies of a position folded into one: the R
    of the idea is the mean R of its copies, each measured against its own
    account, and everything else is asked of the journal underneath."""

    def __init__(self, journal, r):
        self._journal, self._r = journal, r

    def r(self, trade_id):
        return self._r[trade_id] if trade_id in self._r else self._journal.r(trade_id)

    def __getattr__(self, name):
        return getattr(self._journal, name)


def ideas(journal, trades):
    """(journal, trades) with every position held on several accounts counted
    once. The trade that stands for it is a copy of the first, carrying the
    PnL of all of them and the mean R; its result is theirs when they agree
    and the sign of that R when a fee tipped one of them over."""
    groups, order = {}, []
    for t in trades:
        key = twin_key(t) if not t.is_open else ("open", t.id)
        if key not in groups:
            order.append(key)
        groups.setdefault(key, []).append(t)
    out, r = [], {}
    for key in order:
        group = sorted(groups[key], key=lambda t: t.id)
        if len(group) == 1 or len({t.account for t in group}) == 1:
            out.extend(group)
            continue
        first = copy.copy(group[0])
        rs = [journal.r(t.id) or 0.0 for t in group]
        mean = sum(rs) / len(rs)
        first.pnl = sum(t.pnl or 0.0 for t in group)
        results = {t.result for t in group}
        first.result = (results.pop() if len(results) == 1
                        else "Win" if mean > 0 else "Lose" if mean < 0 else "BE")
        r[first.id] = mean
        out.append(first)
    return Ideas(journal, r), out


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


@dataclass
class Checklist:
    """How the closed trades of a selection went through the rules of the
    playbooks they were opened under."""
    ticked: int = 0         # went through a checklist, at the entry or at the close
    unticked: int = 0       # named a playbook and was never ticked
    kept: Summary = None    # ticked, every rule met
    broke: Summary = None   # ticked, at least one rule not met


def checklist(journal, trades):
    """The trades of a selection against their rules.

    Named checklist and not discipline, so that it is not read as the same
    thing as reports.discipline, which composes a whole report. Open trades
    are out of every count, because every figure standing beside this one
    counts closed trades."""
    closed = [t for t in trades if not t.is_open]
    done = [t for t in closed if ticked(t)]
    return Checklist(
        ticked=len(done),
        unticked=sum(1 for t in closed if t.playbook and not ticked(t)),
        kept=summary(journal, [t for t in done if not broke(t)]),
        broke=summary(journal, [t for t in done if broke(t)]))


def past_stop(journal, trades):
    """The losses that went deeper than the risk allowed, worst first.

    The edge is the one the buckets cut at, so the two agree by construction
    and not by agreement: a stop that worked costs -1 R, up to the journal's
    stop edge (1.2 R unless the owner set it) once commission and swap are
    paid on top of it. Past that, the loss was larger than the trade was
    sized for."""
    edge = journal.stop_edge
    return sorted((t for t in trades if not t.is_open and t.result == "Lose"
                   and abs(journal.r(t.id) or 0.0) >= edge),
                  key=lambda t: journal.r(t.id) or 0.0)


def past_stop_over(journal, trade):
    """How far one loss went beyond the stop it was sized for, never above
    zero.

    The stop itself is not the mistake: -1 R is the attempt working as it was
    meant to, and commission and swap carry it to the stop edge, which the
    trade was still sized for. Only what lies past that edge was lost to the
    risk being overrun, and it is the part discipline could have kept. The
    edge is the one the buckets cut at, so a loss counted as past the stop and
    the price put on it are measured by the same number.
    """
    edge = journal.stop_edge
    r = journal.r(trade.id)
    return 0.0 if r is None else min(0.0, r + edge)


def past_stop_cost(journal, past):
    """What a list of losses past the stop cost beyond the stop itself."""
    return sum(past_stop_over(journal, t) for t in past)


@dataclass
class Breakeven:
    """The closed trades whose stop was moved to the entry, against the ones
    whose stop stayed where it was written.

    What the journal can say: how the moved ones ended and what they brought
    against the rest, and how soon after the entry the stop was moved. What
    it cannot say is whether a trade stopped at the entry would have reached
    its target; that is read off the chart."""
    moved: Summary = field(default_factory=Summary)
    stayed: Summary = field(default_factory=Summary)
    hours: list = field(default_factory=list)     # entry to move, per moved trade
                                                  # whose entry carries an hour
    shares: list = field(default_factory=list)    # the move as a share of the hold,
                                                  # 0..1, where both ends carry an hour

    @property
    def median_hours(self):
        return statistics.median(self.hours) if self.hours else None

    @property
    def median_share(self):
        return statistics.median(self.shares) if self.shares else None


def breakeven_split(journal, trades):
    """The moved trades against the rest, closed trades only."""
    b = Breakeven()
    moved = [t for t in trades if not t.is_open and t.breakeven is not None]
    stayed = [t for t in trades if not t.is_open and t.breakeven is None]
    b.moved, b.stayed = summary(journal, moved), summary(journal, stayed)
    for t in moved:
        # an entry without an hour is midnight, and a move at noon would
        # read as twelve hours of holding that never were
        if not t.opened_time:
            continue
        held = (t.breakeven - t.opened).total_seconds() / 3600
        b.hours.append(max(0.0, held))
        if t.closed_time and t.closed > t.opened:
            whole = (t.closed - t.opened).total_seconds() / 3600
            b.shares.append(min(1.0, max(0.0, held / whole)))
    return b


def _figure(limits, key):
    try:
        x = float(str(limits.get(key, "")).replace(",", "."))
    except ValueError:
        return None
    return x if math.isfinite(x) else None


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


@dataclass
class Fall:
    """The deepest fall of the cumulative R curve, and when it happened."""
    worst: float = 0.0          # zero or negative
    peak_at: datetime = None    # the high it fell from, None when that was the start
    trough_at: datetime = None
    back_at: datetime = None    # when the curve regained that high, None while it has not
    now: float = 0.0            # how far under its running high the curve ends


def drawdown(journal, trades):
    """The deepest fall of the cumulative R curve, with its dates.

    The trades are taken in the order they closed, because that is the order
    the account felt them: a trade opened first but closed last moves the curve
    last. Says how far the selection went below its own high, when it got
    there and whether it has come back, which the total R does not show. A
    figure on its own answers how deep and not whether the hole is still open.
    """
    # two trades closed at the same stamp are taken in the order the tape
    # draws them, by id, so the picture and the figure agree
    curve = sorted(((t.closed, t.id, journal.r(t.id) or 0.0) for t in trades
                    if not t.is_open and t.closed), key=lambda x: (x[0], x[1]))
    f = Fall()
    peak = total = 0.0
    peak_at, from_peak, at = None, 0.0, None
    for i, (day, _, r) in enumerate(curve):
        total += r
        # a curve that comes back exactly to its high stands on it again:
        # the fall that follows is dated from there, not from the first time
        if total >= peak - 1e-9:
            peak, peak_at = max(peak, total), day
        if total - peak < f.worst:
            f.worst = total - peak
            f.peak_at, f.trough_at = peak_at, day
            from_peak, at = peak, i
        f.now = total - peak
    if at is not None:
        total = 0.0
        for i, (day, _, r) in enumerate(curve):
            total += r
            if i > at and total >= from_peak - 1e-9:
                f.back_at = day
                break
    return f


@dataclass
class MoneyFall:
    """The deepest fall of an account's balance, in money and as a share of
    the high it fell from."""
    worst: float = 0.0          # zero or negative
    share: float = 0.0          # of the high, in percent, zero or negative
    peak_at: datetime = None
    trough_at: datetime = None


def money_fall(journal, account_id):
    """The deepest fall of one account's balance from a high, its money moved
    in and out included the way the balance has it: a withdrawal lowers the
    balance and is not a loss, so money taken out is added back before the
    fall is measured."""
    points = equity_events(journal, account_id)
    f = MoneyFall()
    peak = peak_at = None
    out = 0.0
    for day, balance, what in points:
        if what is not None and what != "start" and getattr(what, "kind", "") == "withdrawal":
            out -= what.amount
        level = balance + out
        if peak is None or level >= peak:
            peak, peak_at = level, day
            continue
        if level - peak < f.worst:
            f.worst = level - peak
            f.share = 100.0 * f.worst / peak if peak else 0.0
            f.peak_at, f.trough_at = peak_at, day
    return f


def drawdown_r(journal, trades):
    """The deepest fall, in R, zero or negative."""
    return drawdown(journal, trades).worst


# The R buckets of the distribution. Coarse at the tails on purpose: a legend is
# only readable up to about six rows, and the difference between +3R and +4R
# matters less than the difference between a small win and a big one.
#
# The losses are cut where a stop actually lands. A trade taken to the stop
# comes back a little worse than -1R, because commission and swap are paid on
# top of it, so -1 to the stop edge is one bucket: the stop, as designed.
# Anything past the edge lost more than the risk allowed, and it is kept apart
# to be seen. The edge is the owner's (`Journal.stop_edge`, 1.2 unless set),
# so the buckets are built for a journal rather than kept as a constant.
# Every bucket holds its lower edge and not its upper one, so exactly -1R is a
# stop and not a loss that stayed short of it.
# A label reads from zero outwards, like the wins, and the far edge of a bucket
# belongs to the next one: exactly -1R is in "-1…-1.2", the stop.
WIN_BUCKETS = [("0…+0.5", 0.5), ("+0.5…+1", 1.0), ("+1…+2", 2.0),
               ("+2…+3", 3.0), ("+3R and more", None)]


def loss_buckets(edge):
    """The loss buckets for a stop edge. At an edge of exactly 1 the stop
    bucket would be empty, so there the stop and the overrun share the last
    bucket and the legend has one row fewer."""
    buckets = [("0…-0.5", 0.5), ("-0.5…-1", 1.0)]
    if edge > 1.0:
        buckets.append((f"-1…-{edge:g}", edge))
    buckets.append((f"-{edge:g}R and worse", None))
    return buckets


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
    loss_buckets_ = loss_buckets(journal.stop_edge)
    piles = {"Lose": [[label, 0, 0.0] for label, _ in loss_buckets_],
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
        buckets = loss_buckets_ if t.result == "Lose" else WIN_BUCKETS
        i, _ = _bucket(buckets, abs(r))
        piles[t.result][i][1] += 1
        piles[t.result][i][2] += r
    return ([tuple(row) for row in piles["Lose"]],
            [tuple(row) for row in piles["Win"]], be)


def r_line(journal, trades):
    """The closed trades on one axis of R: [(trade, r, pile, bucket)], pile
    being "Lose", "Win" or "BE" and bucket the index into the buckets of that
    pile, chosen the way `r_split` chooses it, so the dots and the counts of
    the legend are the same trades. Ordered by R."""
    losses = loss_buckets(journal.stop_edge)
    out = []
    for t in trades:
        if t.is_open or t.result not in ("Win", "Lose", "BE"):
            continue
        r = journal.r(t.id) or 0.0
        if t.result == "BE":
            out.append((t, r, "BE", 0))
            continue
        i, _ = _bucket(losses if t.result == "Lose" else WIN_BUCKETS, abs(r))
        out.append((t, r, t.result, i))
    out.sort(key=lambda x: (x[1], x[0].id))
    return out


def by_exit_day(journal, trades):
    """{date: Summary} of the closed trades, by the day of the exit: what a
    day made, the way a report counts its month (invariant 12)."""
    piles = {}
    for t in trades:
        if not t.is_open and t.closed:
            piles.setdefault(t.closed.date(), []).append(t)
    return {day: summary(journal, xs) for day, xs in piles.items()}


def by_entry_weekday(journal, trades):
    """{weekday: Summary} of the closed trades by the day of the week they
    were entered on, Monday 0. By the entry, since the day a trade was taken
    on is the thing being asked about, and every trade has its date."""
    piles = {}
    for t in trades:
        if not t.is_open and t.opened:
            piles.setdefault(t.opened.weekday(), []).append(t)
    return {day: summary(journal, xs) for day, xs in piles.items()}


def cumulative_r(journal, trades):
    """The running sum of R over the closed trades in the order they closed,
    starting at zero: the path a period took to its total."""
    closed = sorted((t for t in trades if not t.is_open and t.closed),
                    key=lambda t: (t.closed, t.id))
    path, total = [0.0], 0.0
    for t in closed:
        total += journal.r(t.id) or 0.0
        path.append(total)
    return path


def equity(journal, account_id=None, trades=None, since=None):
    """Points of (date, balance), as in balances, but honouring the filter.

    Everything that happened before `since` is folded into the first point,
    whatever the selection says: a curve that starts in August starts at the
    balance the account had in August, not at the day it was opened. From
    `since` on only the chosen trades move the line, so a selection by style
    or by pair draws what those trades alone did to the account."""
    return [(day, balance) for day, balance, what in
            equity_events(journal, account_id, trades, since) if what != "start"]


def equity_events(journal, account_id=None, trades=None, since=None, until=None):
    """The equity walk with a word on what moved each point.

    Every point is (date, balance, what): `what` is None for a trade, the
    Adjustment for money that moved outside a trade, "start" for the opening
    balance placed before the first event, or "since" for the balance the
    period was entered with. The chart marks the adjustments, so that a
    deposit is not read as a big win; the balances are the ones of `equity`.

    `until` ends the walk: a curve cut to August must not step on a deposit
    made in September, which would hang past the last trade of the month."""
    chosen = None if trades is None else {t.id for t in trades}
    start = sum(acc.start_balance for a, acc in journal.accounts.items()
                if account_id in (None, a))
    events = [(c.day, c.amount, c) for c in journal.adjustments
              if account_id in (None, c.account)
              and (until is None or c.day < until)]
    events += [(t.closed, t.pnl or 0.0, None) for t in journal.trades
               if not t.is_open and t.closed
               and (until is None or t.closed < until)
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


# How long a position was carried. Coarse on purpose, and cut where a
# discretionary trader changes his mind about a trade: inside the day, over a
# night or two, over a week. Every bucket holds its lower edge and not its
# upper one.
HOLD_BUCKETS = [("same day", 1), ("1 to 2 days", 3), ("3 to 5 days", 6),
                ("6 days or more", None)]


def held_days(t):
    """Whole days from the entry to the exit, or None while the trade is open
    or a date is missing.

    Days and not hours: an exit is often written without an hour, and then it
    is midnight, so a trade opened at nine and closed the same evening would
    come out as minus fifteen hours. The dates alone are always there."""
    if t.is_open or not t.closed or not t.opened:
        return None
    return (t.closed.date() - t.opened.date()).days


def by_hold(journal, trades):
    """[(label, Summary)] by how long a position was carried, in the order of
    the buckets and not of their size: the length is the thing being read.
    A bucket with no trade in it is left out."""
    piles = {}
    for t in trades:
        days = held_days(t)
        if days is None:
            continue
        _, label = _bucket(HOLD_BUCKETS, days)
        piles.setdefault(label, []).append(t)
    return [(label, summary(journal, piles[label]))
            for label, _ in HOLD_BUCKETS if label in piles]


def _period_start(day, group):
    """The first moment of the week, month or quarter a day falls in."""
    if group == "week":
        return datetime(day.year, day.month, day.day) - timedelta(days=day.weekday())
    if group == "quarter":
        return datetime(day.year, 3 * ((day.month - 1) // 3) + 1, 1)
    return datetime(day.year, day.month, 1)


def _next_period(start, group):
    if group == "week":
        return start + timedelta(days=7)
    if group == "quarter":
        month = start.month + 3
        return datetime(start.year + (month > 12), (month - 1) % 12 + 1, 1)
    return datetime(start.year + (start.month == 12), start.month % 12 + 1, 1)


def period_key(day, group):
    """The key of the week, month or quarter a day falls in. The keys of one
    grain sort in the order they read."""
    if group == "week":
        return week(day)
    if group == "quarter":
        return quarter(day)
    return f"{day:%Y-%m}"


_PERIOD_KEY = re.compile(r"^\d{4}-(?:W\d{2}|\d{2}|Q[1-4])$")


def grain_of(key):
    """Which grain a period key is of, or None when it is not one: 2026-W36
    is a week, 2026-08 a month, 2026-Q3 a quarter.

    The shape alone is not enough: 2026-13 and 2025-W53 look like keys and
    name no period, and a key typed by hand into the address must be
    answered with the whole journal, not with a traceback."""
    if not _PERIOD_KEY.match(key or ""):
        return None
    group = "week" if "W" in key else "quarter" if "Q" in key else "month"
    try:
        _next_period(period_start(key, group), group)
    except (ValueError, OverflowError):
        return None
    return group


def period_start(key, group):
    """The first moment of the period a key names."""
    if group == "week":
        return datetime.fromisocalendar(int(key[:4]), int(key[6:]), 1)
    if group == "quarter":
        return datetime(int(key[:4]), 3 * (int(key[6]) - 1) + 1, 1)
    return datetime(int(key[:4]), int(key[5:]), 1)


def period_bounds(key):
    """The first moment of a period and the first moment after it, so that
    what happened inside it is `start <= day < end`; None for a key that is
    not a period."""
    group = grain_of(key)
    if not group:
        return None
    start = period_start(key, group)
    return start, _next_period(start, group)


def closed_in(trades, key):
    """The trades of one period, by the exit.

    The months of the filter pick trades by the entry, the way the list of
    trades does; this picks them the way a report and the tile of the current
    period do. Both exist on purpose: one narrows a list, the other narrows a
    figure, and a page that mixed them would print a total that disagrees with
    the row it was clicked on."""
    group = grain_of(key)
    if not group:
        return list(trades)
    return [t for t in trades if not t.is_open and t.closed
            and period_key(t.closed, group) == key]


def by_period(journal, trades, group="month"):
    """[(period key, Summary)] over the closed trades, oldest first, and the
    periods that closed nothing standing empty between them.

    Measured by the exit, the way a report counts a month and the front page
    counts this week, so a row here holds exactly the trades of the report of
    that period. by_values with a lambda comes close, but it orders by the
    number of trades and leaves the entry or the exit to the caller, which is
    where invariant 12 gets broken; the choice is made here, once, where it
    can be tested. A period with nothing in it keeps its place: a month the
    account stood still is part of the picture, and a chart with the gaps
    squeezed out would draw a year of trading as if it had been continuous."""
    closed = [t for t in trades if not t.is_open and t.closed]
    if not closed:
        return []
    piles = {}
    for t in closed:
        piles.setdefault(period_key(t.closed, group), []).append(t)
    last = max(t.closed for t in closed)
    rows, cursor = [], _period_start(min(t.closed for t in closed), group)
    while cursor <= last:
        key = period_key(cursor, group)
        rows.append((key, summary(journal, piles.get(key, []))))
        cursor = _next_period(cursor, group)
    return rows


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
