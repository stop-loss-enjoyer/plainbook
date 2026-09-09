#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Journal records: trade, account, adjustment, daily and weekly card.

Storage is one markdown file per record (see mdfile.py). Header keys are the
same words the interface shows, so a file reads like the screen it came from.
Anything that can be computed (balance, R) is NOT stored; see balances.py.
"""
import re
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
    ("breakeven", "stop at breakeven"),
    ("note", "note"),
    ("plan", "plan"),
    ("playbook", "playbook"),
    ("playbook_version", "playbook version"),
    ("setup", "setup"),
    ("deviations", "deviations"),
    ("exit_deviations", "exit deviations"),
    ("reasons", "reasons"),
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
    breakeven: datetime = None                      # when the stop went to the
                                                    # entry: the risk is freed
    note: str = ""
    plan: str = ""                                  # id of the plan it follows
    playbook: str = ""                              # id of the playbook, if any
    playbook_version: str = ""                      # the rules it was ticked against
    setup: str = ""                                 # the setup taken, if the playbook has them
    deviations: list = None                         # numbers of the rules not met;
                                                    # None: the rules were never ticked
    exit_deviations: list = None                    # the same for the management
                                                    # rules, ticked when it is closed
    reasons: dict = field(default_factory=dict)     # {rule number: why it was not met}
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
        if self.breakeven is not None and self.opened is not None:
            if _day(self.breakeven) < _day(self.opened):
                raise RecordError(f"{self.id}: the stop went to breakeven before the entry")
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
    def label(self):
        """A plan in one line, for a list, for the menu of the trade form and
        for the trade that followed it."""
        span = f"{self.day:%d.%m.%Y}"
        if self.until and self.until != self.day:
            span += f" to {self.until:%d.%m.%Y}"
        bits = [span, "" if self.pair == PAIR_NOT_SET else self.pair,
                self.title, self.narrative]
        return " · ".join(b for b in bits if b)

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


# --- playbook --------------------------------------------------------------
# The standing rules of one way of trading: what has to be true before a trade
# is opened. A plan is written for a day and a pair; a playbook has no date and
# no pair, it is the system itself. A trade will name the playbook it was taken
# under and the rules it did not meet, so that a rule can be priced in R.

PLAYBOOK_KEYS = [
    ("id", "id"),
    ("name", "name"),
    ("styles", "styles"),
    ("status", "status"),
    ("version", "version"),
    ("since", "since"),
    ("block", "block"),
]

# experiment: rules on trial, the sample is being built; active: the system
# is trusted; retired: kept for the trades that carry it, not offered any more
PLAYBOOK_STATUSES = ("active", "experiment", "retired")

# The limits a playbook can set as figures: (key in the file, label in the
# interface, unit). The form offers a field for each, so that nobody has to
# know the key, and the journal will count them against the trades. A limit
# of another kind is written as text and shown as written.
LIMITS = [
    ("risk", "risk per trade", "%"),
    ("max per week", "trades per week, at most", ""),
    ("max per month", "trades per month, at most", ""),
    ("weekly loss limit", "loss per week, at most", "R"),
    ("open at once", "positions open at once", ""),
    ("max hold", "longest hold", "days"),
    ("min rr", "least RR", ""),
]


@dataclass
class Rule:
    """One line to tick before the trade: numbered through the whole playbook,
    so that a trade can name the rules it did not meet by number. The text is
    the few words the checklist shows; the detail is the whole rule, for the
    page and for a look while ticking."""
    number: int
    text: str
    detail: str = ""


@dataclass
class Setup:
    """A way to enter under the playbook, with its own rules. A playbook with
    one way of entering keeps its rules in a setup with no name."""
    name: str = ""
    text: str = ""                                  # what the setup is about
    rules: list = field(default_factory=list)       # [Rule]


@dataclass
class Playbook:
    id: str
    name: str = ""
    styles: list = field(default_factory=list)      # the styles it is for
    status: str = "active"
    version: str = ""                               # rules change by version
    since: date = None                              # the first trade it counts
    block: int = None                               # trades per review, or none
    intro: str = ""                                 # what the playbook is
    setups: list = field(default_factory=list)      # [Setup]
    filters: list = field(default_factory=list)     # [Rule], for every setup
    management: list = field(default_factory=list)  # [Rule], ticked at the close
    limits: list = field(default_factory=list)      # [(what, value)] as text
    sections: list = field(default_factory=list)    # [(heading, text)] the rest
    review: str = ""                                # dated entries, with shots
    extra: dict = field(default_factory=dict)

    @property
    def rules(self):
        """Every rule in the order it is numbered: the setups, then the
        filters, then the management."""
        out = []
        for s in self.setups:
            out.extend(s.rules)
        out.extend(self.filters)
        out.extend(self.management)
        return out

    def checklist(self, setup):
        """The rules a trade is held to: those of its setup, then the filters.
        A playbook whose setups have no names has one, and every trade takes
        it. The management rules are not here: they are ticked at the close."""
        named = any(x.name for x in self.setups)
        rules = []
        for x in self.setups:
            if not named or x.name == setup:
                rules.extend(x.rules)
        return rules + list(self.filters)

    @property
    def offered(self):
        return self.status != "retired"

    def check(self):
        if not self.id:
            raise RecordError("playbook has no id")
        if not self.name.strip():
            raise RecordError(f"{self.id}: the playbook has no name")
        if self.status not in PLAYBOOK_STATUSES:
            raise RecordError(f"{self.id}: bad status {self.status!r}")
        if self.block is not None and self.block <= 0:
            raise RecordError(f"{self.id}: the block must be above zero")
        if len(self.setups) > 1 and not all(x.name for x in self.setups):
            raise RecordError(f"{self.id}: with several setups, every setup needs a name")
        return self


# --- the trades assessment -------------------------------------------------
# Both report cards end with the same table: the trades of the period and the
# mark each one earned, on numbered lines, as many as the paper has.

ASSESSMENT_ROWS = 5


@dataclass
class Graded:
    """One line of the trades assessment: a trade, the mark it earned, and how
    it ended. The result is text, as on paper: the journal offers what it
    knows, the owner keeps the last word.

    `id` is the trade the line names, kept when the line was picked from the
    ones the journal offers. A line that has it is drawn with the journal's
    answer every time the card is opened, and the answer is not stored: a
    swing graded while it was still running says "open" that week and says
    what it made once it closes, a fortnight later if that is how long it
    took. A result the owner typed is stored and stands."""
    trade: str = ""
    grade: str = ""
    result: str = ""
    id: str = ""


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
    assessment: list = field(default_factory=list)   # [Graded]
    extra: dict = field(default_factory=dict)

    @property
    def id(self):
        return f"{self.day:%Y-%m-%d}" if self.day else ""

    @property
    def is_empty(self):
        return not any(getattr(self, name).strip()
                       for name, _, _ in CARD_SECTIONS) and not self.assessment

    def check(self):
        if self.day is None:
            raise RecordError("card without a date")
        return self


# --- weekly card -----------------------------------------------------------

WEEK_KEYS = [
    ("week", "week"),
    ("grade", "process grade"),
    ("pnl", "pnl $"),
    ("trades", "trades"),
    ("quality", "opportunity quality"),
    ("progress", "progress"),
]

# The same shape as the daily card, with the headings of the paper Weekly
# Report Card. The trades assessment is not here: it is a table, not a text.
WEEK_SECTIONS = [
    ("focus", "Focus", "current focus (progress)"),
    ("process", "Process", "weekly trading process"),
    ("learned", "Learned", "what I learned / did well this week?"),
    ("errors", "Errors", "errors & improvement"),
    ("best", "Best trade", "best trade of the week"),
    ("missed", "Missed", "missed / underexploited opportunities"),
    ("lesson", "Key lesson", "key lesson of the week"),
]

_WEEK_ID = re.compile(r"^\d{4}-W\d{2}$")


@dataclass
class Week:
    """The week reviewed: the paper Weekly Report Card, kept in the journal."""
    week: str = ""                  # ISO key, 2026-W36, as stats.week gives it
    grade: str = ""                 # process grade: A, B, C...
    pnl: float = None
    trades: int = None              # how many trades the week held
    quality: str = ""               # how good the opportunities were
    progress: int = None            # 1 to 10 on the current focus
    focus: str = ""
    process: str = ""
    learned: str = ""
    errors: str = ""
    best: str = ""
    missed: str = ""
    lesson: str = ""
    assessment: list = field(default_factory=list)   # [Graded]
    extra: dict = field(default_factory=dict)

    @property
    def id(self):
        return self.week

    @property
    def monday(self):
        """The first day of the week, worked out from the key."""
        year, number = int(self.week[:4]), int(self.week[6:])
        return datetime.fromisocalendar(year, number, 1)

    @property
    def number(self):
        return int(self.week[6:])

    @property
    def is_empty(self):
        return not any(getattr(self, name).strip()
                       for name, _, _ in WEEK_SECTIONS) and not self.assessment

    def check(self):
        if not _WEEK_ID.match(self.week or ""):
            raise RecordError(f"bad week {self.week!r}: expected YYYY-Www")
        if not 1 <= self.number <= 53:
            raise RecordError(f"no week {self.number} in a year")
        if self.progress is not None and not 1 <= self.progress <= 10:
            raise RecordError(f"{self.week}: progress is 1 to 10")
        try:
            self.monday
        except ValueError:
            raise RecordError(f"there is no week {self.week} in that year")
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


# --- market note -----------------------------------------------------------
# A page about the market rather than about one trade: a pattern seen, a
# behaviour of a pair, a lesson that does not belong to a single day. It is
# written in blocks, each a heading of its own, text and screenshots, and it
# names the trades that show it, so that a note can be read with its examples
# open beside it.

NOTE_KEYS = [
    ("id", "id"),
    ("title", "title"),
    ("day", "date"),
    ("trades", "trades"),
]


@dataclass
class Note:
    id: str
    title: str = ""
    day: date = None                                # the day it was written
    blocks: list = field(default_factory=list)      # IdeaBlock: heading, text, shots
    trades: list = field(default_factory=list)      # ids of the example trades
    extra: dict = field(default_factory=dict)

    def check(self):
        if not self.id:
            raise RecordError("note has no id")
        if not self.title.strip():
            raise RecordError(f"{self.id}: the note has no title")
        if self.day is None:
            raise RecordError(f"{self.id}: the note has no date")
        return self
