#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
An invented journal, for the screenshots in README.md and for looking at a
change without opening anybody's records.

    python3 tools/demo_journal.py /tmp/pb-demo
    PLAINBOOK_ROOT=/tmp/pb-demo PLAINBOOK_PORT=8899 python3 -m plainbook.server

Every number here is made up, and made up the same way every time: the seed is
fixed, so a screenshot taken today differs from one taken last month only in its
dates and where the interface itself changed. The dates run up to today, because
a front page whose current week is empty shows half of what it can do.
"""
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import stats, store
from plainbook.model import (Account, Card, Graded, IdeaBlock, Plan, Trade,
                             Week)

ACCOUNTS = [Account(id="broker", name="broker", start_balance=10000),
            Account(id="prop-100k", name="prop 100k", start_balance=100000)]

# a spread wide enough to show every kind of icon: currencies, an index,
# a metal and an oil
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "EURGBP",
         "XAUUSD", "GER40", "US100", "UKOUSD"]

IDEAS = [
    "Range high swept, price back inside. Waiting for the retest from below.",
    "Daily trend intact, H4 pullback into the imbalance left on the way up.",
    "Second touch of the level, first one took liquidity and rejected.",
    "Session open above the previous day's high, continuation while it holds.",
]

CONCLUSIONS = [
    "Entry was fine, the size was not: half of it would have held the drawdown.",
    "Waited for the retest and got paid for waiting. Do that again.",
    "Took it two hours before the news. Nothing wrong with the setup, wrong hour.",
    "Moved the stop to break-even too early and the trade ran without me.",
]


def build(root, days=40):
    random.seed(12)
    for account in ACCOUNTS:
        store.save_account(root, account)
    store.save_pairs(root, PAIRS)

    today = datetime.now().replace(hour=17, minute=30, second=0, microsecond=0)
    while today.weekday() >= 5:                     # finish the run on a weekday
        today -= timedelta(days=1)
    start = today - timedelta(days=days)

    # a plan for the current week, so that the Plans tab and the plan page
    # have something to show, and a few trades are tied to it below
    monday = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0)
    plan = Plan(id=store.new_plan_id(root, monday, "EURUSD"), title="weekly",
                pair="EURUSD", narrative="bullish", day=monday,
                until=monday + timedelta(days=4),
                analysis=[IdeaBlock(tf="D1", text="Higher lows since the last "
                                    "sweep of the yearly level; the weekly close "
                                    "held above it."),
                          IdeaBlock(tf="H4", text="An imbalance left on Friday's "
                                    "rally is the place to buy from.")],
                plan="Buy from the H4 imbalance only. No shorts this week, and "
                     "no entry in the hour before the Thursday news.",
                updates=f"**{monday + timedelta(days=1):%d.%m.%Y}**: the "
                        f"imbalance was filled overnight, waiting for the retest.")
    store.save_plan(root, plan)

    for i in range(26):
        day = start + timedelta(days=int(i * days / 26), hours=random.randint(-5, 4))
        if day.weekday() >= 5:                      # the market is closed
            day += timedelta(days=2)
        account = random.choice(ACCOUNTS).id
        style = random.choice(["swing", "EMT", "EMT prop"])
        result = random.choices(["Win", "Lose", "BE"], [5, 4, 2])[0]
        risk = random.choice([0.85, 0.9, 1.0])
        base = 100 if account == "broker" else 1000
        pnl = {"Win": round(base * risk * random.uniform(1.4, 2.6)),
               "Lose": -round(base * risk * random.uniform(0.9, 1.1)),
               "BE": -round(base * risk * 0.06)}[result]
        pair = random.choice(PAIRS)
        trade = Trade(
            id=store.new_id(root, day, pair), account=account, pair=pair,
            direction=random.choice(["long", "short"]), style=style,
            entry_tf=random.choice(["H1", "H4", "D1"]),
            execution=random.sample(["Market Entry", "IDM", "SNR", "FVG"], 2),
            risk=risk, opened=day, opened_time=True,
            result=result, pnl=float(pnl),
            closed=(day + timedelta(days=random.randint(0, 3))).replace(
                hour=0, minute=0),
            plan=plan.id if plan.covers(day) and pair == "EURUSD" else "",
            idea=[IdeaBlock(tf="H4", text=random.choice(IDEAS))],
            conclusions=random.choice(CONCLUSIONS))
        store.save_trade(root, trade)

    # one position still open: the front page has a card of its own for those
    open_day = today - timedelta(hours=6)
    store.save_trade(root, Trade(
        id=store.new_id(root, open_day, "EURUSD"), account="broker", pair="EURUSD",
        direction="short", style="EMT", entry_tf="H1", risk=1.0,
        opened=open_day, opened_time=True, plan=plan.id,
        idea=[IdeaBlock(tf="H1", text=IDEAS[0])]))

    store.save_card(root, Card(
        day=today, grade="B", quality="B", pnl=174.0,
        focus="Stop taking the second entry after a loss.",
        process="Two setups planned in the morning, one taken, one skipped for "
                "the right reason, it never came back to the level.",
        learned="Waiting for the retest cost nothing and paid twice today.",
        errors="Sized up on the second trade to make the first one back.",
        best="GBPUSD long from the H4 imbalance: planned, sized, held.",
        overview="A quiet day traded quietly. The plan survived the session.",
        assessment=[Graded("GBPUSD long, H4 imbalance", "A"),
                    Graded("EURUSD long, second entry", "C")]))

    store.save_week(root, Week(
        week=stats.week(today), grade="B", quality="B", progress=3,
        pnl=sum(t.pnl or 0.0 for t in store.all_trades(root)
                if not t.is_open and t.closed
                and stats.week(t.closed) == stats.week(today)),
        trades=sum(1 for t in store.all_trades(root)
                   if not t.is_open and t.closed
                   and stats.week(t.closed) == stats.week(today)),
        focus="Stop taking the second entry after a loss.",
        process="Levels marked on Sunday, and the trades that came from them "
                "were the calm ones. The one taken in the session lost.",
        learned="Every trade held to target was planned before the open.",
        errors="Still adding size after a loss. Twice this week.",
        best="GBPUSD long from the H4 imbalance: planned, sized, held.",
        missed="US100 gave the same setup on Thursday and was watched, not "
               "taken.",
        lesson="The trades that pay are the ones written down before the open.",
        assessment=[Graded("EURUSD long, Monday", "B"),
                    Graded("GBPUSD long, Tuesday", "A"),
                    Graded("XAU short, Thursday", "C")]))


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pb-demo"
    os.makedirs(root, exist_ok=True)
    build(root)
    print(f"invented journal written to {root}\n"
          f"PLAINBOOK_ROOT={root} PLAINBOOK_PORT=8899 python3 -m plainbook.server")
