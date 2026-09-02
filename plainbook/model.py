#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Journal records: trade, account, adjustment, daily card.

Storage is one markdown file per record (see mdfile.py). Header keys are the
same words the interface shows, so a file reads like the screen it came from.
Anything that can be computed (balance, R) is NOT stored; see balances.py.
"""
from dataclasses import dataclass, field
from datetime import date, datetime

# --- domain vocabulary -----------------------------------------------------

DIRECTIONS = ("long", "short")
RESULTS = ("Win", "Lose", "BE")
ADJUSTMENT_KINDS = ("deposit", "withdrawal", "fee", "reconciliation")
# what the plan expects the market to do; "no trade" is a decision as well
NARRATIVES = ("bullish", "bearish", "neutral", "no trade")

# The three lists the trade form offers. They belong to the owner: the lists
# are edited in the interface and kept in journal/vocabulary.md, and these are
# what a journal starts with. A trade is not checked against them, because a
# word taken out of a list must still load in the trades that carry it.
STYLES = ("swing", "EMT", "EMT prop")
TIMEFRAMES = ("M15", "H1", "H4", "D1")
EXECUTION = ("Market Entry", "IDM", "SNR", "FVG")

PAIR_NOT_SET = "pair not set"


class RecordError(ValueError):
    """A record fails its check: a broken file or junk from a form."""


def _day(moment):
    """The calendar day of a datetime, or the date itself when that is all
    there is: a record built by hand may carry either."""
    return moment.date() if isinstance(moment, datetime) else moment


# --- trade -----------------------------------------------------------------

TRADE_KEYS = [
    ("id", "id"),
    ("account", "account"),
    ("pair", "pair"),
    ("direction", "direction"),
    ("style", "style"),
    ("entry_tf", "entry tf"),
    ("execution", "execution"),
    ("risk", "risk %"),
    ("opened", "entry"),
    ("result", "result"),
    ("pnl", "pnl $"),
    ("closed", "exit"),
    ("note", "note"),
    ("plan", "plan"),
    ("notion_id", "notion id"),
]


@dataclass
class Trade:
    id: str
    account: str
    pair: str = PAIR_NOT_SET
    direction: str = ""
    style: str = ""
    entry_tf: str = ""
    execution: list = field(default_factory=list)   # a trade usually has two
    risk: float = 1.0                               # percent: 1.0 == 1%
    opened: datetime = None
    opened_time: bool = False                       # is the entry time known
    result: str = None                              # None = position is open
    pnl: float = None
    closed: date = None
    closed_time: bool = False                       # is the exit time known
    note: str = ""
    plan: str = ""                                  # id of the plan it follows
    notion_id: str = ""
    idea: list = field(default_factory=list)        # list of IdeaBlock
    exit_images: list = field(default_factory=list)
    conclusions: str = ""
    extra: dict = field(default_factory=dict)       # unknown header keys

    @property
    def is_open(self):
        return self.result is None

    def check(self):
        if not self.id:
            raise RecordError("trade has no id")
        if not self.account:
            raise RecordError(f"{self.id}: account is not set")
        if self.direction not in DIRECTIONS:
            raise RecordError(f"{self.id}: bad direction {self.direction!r}")
        if not self.style:
            raise RecordError(f"{self.id}: style is not set")
        if self.opened is None:
            raise RecordError(f"{self.id}: entry date is missing")
        if not self.risk or self.risk <= 0:
            raise RecordError(f"{self.id}: bad risk {self.risk!r}")
        if self.result is not None and self.result not in RESULTS:
            raise RecordError(f"{self.id}: bad result {self.result!r}")
        if self.result is not None and self.pnl is None:
            raise RecordError(f"{self.id}: closed trade without PnL")
        if self.result is None and self.pnl is not None:
            raise RecordError(f"{self.id}: open trade must not have PnL")
        if self.closed is not None and self.opened is not None:
            # a close with no hour is a date, and a date is not earlier than
            # the entry of the same day, whatever hour that entry carries
            early = (self.closed < self.opened
                     if self.closed_time and self.opened_time
                     and isinstance(self.closed, datetime)
                     else _day(self.closed) < _day(self.opened))
            if early:
                raise RecordError(f"{self.id}: the exit is before the entry")
        return self


@dataclass
class IdeaBlock:
    """One piece of the idea: a timeframe, the text and its screenshots."""
    tf: str = ""
    text: str = ""
    images: list = field(default_factory=list)


# --- trading plan ----------------------------------------------------------
# Written before the market opens: the analysis by timeframe, what will be done
# and what will not, the notes added while it runs, and the review after. A
# trade points at the plan it followed; the plan does not list its trades,
# because that list is computable from the trades themselves.

PLAN_KEYS = [
    ("id", "id"),
    ("title", "title"),
    ("pair", "pair"),
    ("narrative", "narrative"),
    ("day", "from"),
    ("until", "until"),
]


@dataclass
class Plan:
    id: str
    title: str = ""                                 # a name of your own
    pair: str = PAIR_NOT_SET
    narrative: str = ""                             # bullish, bearish, neutral
    day: date = None                                # the first day it covers
    until: date = None                              # the last one, or the same
    analysis: list = field(default_factory=list)    # IdeaBlock per timeframe
    plan: str = ""                                  # what will be done, and not
    updates: str = ""                               # notes added while it runs
    review: str = ""                                # how it went, with shots
    extra: dict = field(default_factory=dict)

    @property
    def last_day(self):
        return self.until or self.day

    def covers(self, moment):
        """Is that day inside the plan: an open plan is the one to attach to."""
        if self.day is None or moment is None:
            return False
        return self.day.date() <= moment.date() <= self.last_day.date()

    def check(self):
        if not self.id:
            raise RecordError("plan has no id")
        if self.day is None:
            raise RecordError(f"{self.id}: the plan has no date")
        if self.until is not None and self.until < self.day:
            raise RecordError(f"{self.id}: the plan ends before it starts")
        if self.narrative and self.narrative not in NARRATIVES:
            raise RecordError(f"{self.id}: bad narrative {self.narrative!r}")
        return self


# --- daily card ------------------------------------------------------------

CARD_KEYS = [
    ("day", "date"),
    ("grade", "process grade"),
    ("pnl", "pnl $"),
    ("quality", "opportunity quality"),
]

# Card sections: object field -> heading in the file -> label in the interface.
# The order is the one on the paper Daily Report Card.
CARD_SECTIONS = [
    ("focus", "Focus", "current focus (goal)"),
    ("process", "Process", "trading process"),
    ("learned", "Learned", "what I learned / did well today?"),
    ("errors", "Errors", "errors & improvement"),
    ("best", "Best trade", "best trade of the day"),
    ("overview", "Overview", "overview"),
]


@dataclass
class Card:
    """The day reviewed: the paper Daily Report Card, kept in the journal."""
    day: date = None
    grade: str = ""                 # process grade: A, B, C…
    pnl: float = None
    quality: str = ""               # how good the opportunities were
    focus: str = ""
    process: str = ""
    learned: str = ""
    errors: str = ""
    best: str = ""
    overview: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def id(self):
        return f"{self.day:%Y-%m-%d}" if self.day else ""

    @property
    def is_empty(self):
        return not any(getattr(self, name).strip()
                       for name, _, _ in CARD_SECTIONS)

    def check(self):
        if self.day is None:
            raise RecordError("card without a date")
        return self


# --- account ---------------------------------------------------------------

ACCOUNT_KEYS = [
    ("id", "id"),
    ("name", "name"),
    ("start_balance", "start balance"),
    ("currency", "currency"),
    ("archived", "archived"),
    ("daily_loss_limit", "daily loss limit"),
    ("notion_id", "notion id"),
]


@dataclass
class Account:
    id: str                       # bybit, prop-100k
    name: str = ""
    start_balance: float = 0.0
    currency: str = "USD"
    archived: bool = False        # archived ones stay in statistics, not in forms
    daily_loss_limit: float = None  # a prop rule: how much a day may lose
    notion_id: str = ""
    note: str = ""
    extra: dict = field(default_factory=dict)

    def check(self):
        if not self.id:
            raise RecordError("account has no id")
        if self.daily_loss_limit is not None and self.daily_loss_limit <= 0:
            raise RecordError(f"{self.id}: the daily loss limit must be above zero")
        return self


# --- adjustment ------------------------------------------------------------

ADJUSTMENT_KEYS = [
    ("id", "id"),
    ("account", "account"),
    ("kind", "kind"),
    ("amount", "amount"),
    ("day", "date"),
]


@dataclass
class Adjustment:
    """Money moving outside trades: deposit, withdrawal, fee, reconciliation."""
    id: str
    account: str
    kind: str = "reconciliation"
    amount: float = 0.0
    day: date = None
    comment: str = ""
    extra: dict = field(default_factory=dict)

    def check(self):
        if not self.account:
            raise RecordError(f"{self.id}: account is not set")
        if self.kind not in ADJUSTMENT_KINDS:
            raise RecordError(f"{self.id}: bad kind {self.kind!r}")
        if self.day is None:
            raise RecordError(f"{self.id}: date is missing")
        return self
