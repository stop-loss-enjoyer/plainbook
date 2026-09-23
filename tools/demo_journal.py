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
from plainbook.model import (Account, Adjustment, Card, Graded, IdeaBlock,
                             Playbook, Setup, Rule,
                             Plan, Note, Trade, Week)

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


# --- an invented chart -------------------------------------------------------
# A trade page with an empty idea looks like a form, not a journal, so the demo
# pastes a picture where a trader would: a candlestick chart drawn from a random
# walk, in the colours of the interface. The standard library writes the PNG.

def chart_png(seed, width=800, height=420):
    """A dark chart of invented candles, a level and a marked zone, as PNG bytes."""
    import struct
    import zlib
    rnd = random.Random(seed)
    bg, grid, up, down = (13, 15, 20), (28, 31, 40), (61, 176, 116), (217, 95, 95)
    level, zone = (230, 176, 60), (28, 52, 44)
    px = bytearray(bg * (width * height))

    def fill(x0, y0, x1, y1, rgb):
        x0, x1 = max(0, min(x0, x1)), min(width, max(x0, x1) + 1)
        y0, y1 = max(0, min(y0, y1)), min(height, max(y0, y1) + 1)
        row = bytes(rgb) * (x1 - x0)
        for y in range(y0, y1):
            px[(y * width + x0) * 3:(y * width + x1) * 3] = row

    for y in range(0, height, 60):
        fill(0, y, width - 1, y, grid)
    for x in range(0, width, 80):
        fill(x, 0, x, height - 1, grid)

    # the walk: sixty candles that drift, then react at a level
    n, step = 60, width // 64
    price, candles = 100.0, []
    drift = rnd.choice([0.25, -0.25])
    for i in range(n):
        if i == 40:
            drift = -drift
        o = price
        c = o + rnd.gauss(drift, 0.9)
        hi = max(o, c) + abs(rnd.gauss(0, 0.5))
        lo = min(o, c) - abs(rnd.gauss(0, 0.5))
        candles.append((o, c, hi, lo))
        price = c
    top = max(h for _, _, h, _ in candles)
    bottom = min(l for _, _, _, l in candles)
    pad = (top - bottom) * 0.12 or 1

    def y_of(v):
        return int((top + pad - v) / (top - bottom + 2 * pad) * (height - 1))

    turn = candles[40][0]
    fill(0, y_of(turn) - 12, width - 1, y_of(turn) + 12, zone)
    for x in range(0, width, 14):
        fill(x, y_of(turn), x + 7, y_of(turn), level)
    for i, (o, c, hi, lo) in enumerate(candles):
        x = 24 + i * step
        rgb = up if c >= o else down
        fill(x, y_of(hi), x, y_of(lo), rgb)
        fill(x - 3, y_of(o), x + 3, y_of(c), rgb)

    raw = b"".join(b"\x00" + bytes(px[y * width * 3:(y + 1) * width * 3])
                   for y in range(height))

    def chunk(tag, data):
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xffffffff))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def shot(folder, name, seed):
    """Writes one invented chart into the shots folder of a record and returns
    the path the record keeps for it."""
    os.makedirs(os.path.join(folder, store.SHOTS), exist_ok=True)
    with open(os.path.join(folder, store.SHOTS, name), "wb") as f:
        f.write(chart_png(seed))
    return f"{store.SHOTS}/{name}"


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
    folder = store.plan_dir(root, plan.id)
    plan.analysis[0].images = [shot(folder, "idea-01-01.png", 101)]
    plan.analysis[1].images = [shot(folder, "idea-02-01.png", 102)]
    plan.plan += "\n\n![](" + shot(folder, "plan-01.png", 103) + ")"
    store.save_plan(root, plan)

    # a plan of the week before, called off when the market went the other
    # way: the Plans tab shows what a voided plan looks like
    before = monday - timedelta(days=7)
    gone = Plan(id=store.new_plan_id(root, before, "GBPUSD"), title="weekly",
                pair="GBPUSD", narrative="bearish", day=before,
                until=before + timedelta(days=4), voided=before + timedelta(days=2),
                analysis=[IdeaBlock(tf="D1", text="Lower highs into the monthly "
                                    "level; a close under it opens the range "
                                    "below.")],
                plan="Sell the retest of the level only. No longs this week.",
                updates=f"**{before + timedelta(days=2):%d.%m.%Y}**: voided: the "
                        f"level held and the week closed above it, the "
                        f"direction was wrong")
    store.save_plan(root, gone)

    # a playbook, so that the Playbooks tab and its page have rules to show
    store.save_playbook(root, Playbook(
        id="pullback", name="Pullback", styles=["swing"], status="experiment",
        version="1.0", since=start, block=40,
        intro="The one way I enter with the trend: a pullback into an area the "
              "higher timeframe left behind. Written before the first trade "
              "counted here; the rules change between blocks only.",
        setups=[
            Setup(name="A: reaction at a higher level",
                  text="The level was hit and the first reaction is in.",
                  rules=[Rule(1, "Level on W or D",
                              "A fractal level or zone of the weekly or the daily "
                              "chart; a reaction in the premium of the range is "
                              "only sold, in the discount only bought"),
                         Rule(2, "Reaction seen on H4 or H1",
                              "A rejection, a rejection block, a fractal or a "
                              "slowdown; a fractal counts only against the range "
                              "or a major level"),
                         Rule(3, "Entry at market after the reaction is confirmed"),
                         Rule(4, "The stop is behind the extreme of the reaction, "
                                 "with a buffer"),
                         Rule(5, "The nearest target is at least 2R away, or "
                                 "there is no trade")]),
            Setup(name="B: continuation from an imbalance",
                  text="A strong trend, an imbalance left behind, entry with the "
                       "trend to the next level.",
                  rules=[Rule(6, "The trend is visible on the daily chart"),
                         Rule(7, "Entry from the touch when a stop fits behind "
                                 "the fractal, otherwise on confirmation"),
                         Rule(8, "The next level is at least 2R away")])],
        filters=[Rule(9, "More than an hour to the next high-impact release"),
                 Rule(10, "No other position of this playbook is open"),
                 Rule(11, "This is not the fourth trade of the week")],
        management=[Rule(12, "Stop never moved against the position",
                         "The stop stays where the idea dies; it moves only to "
                         "break-even and only after the first target"),
                    Rule(13, "Held to the target or to the stop",
                         "No exit on a feeling; a close by hand is a rule broken"),
                    Rule(14, "Closed by Friday", "No position over the weekend")],
        limits=[("risk", "1"), ("max per week", "3"), ("min rr", "2")],
        sections=[("Math", "Break-even win rate at 2R is 33%. The block is "
                           "reviewed at 40 trades; below 30% the rules are "
                           "rewritten before the next one.")]))

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
        # the swing trades are taken under the playbook: most ticked clean,
        # some with a rule or two not met and a word on why, so that the
        # figures of the playbook have something to say
        if style == "swing":
            trade.playbook, trade.playbook_version = "pullback", "1.0"
            trade.setup = random.choice(["A: reaction at a higher level",
                                         "B: continuation from an imbalance"])
            # a rule is broken more often on the trades that lost: the demo
            # should show what the figures are for, a rule with a price on it
            lost = result == "Lose"
            broke = random.choice([[2], [5], [9], [2, 9], [], []] if lost else
                                  [[], [], [], [], [], [9]])
            if trade.setup.startswith("B"):
                broke = [n for n in broke if n not in (2, 5)]
            trade.deviations = broke
            trade.exit_deviations = random.choice([[13], [12], [], []] if lost else
                                                  [[], [], [], [12]])
            why = {2: "no reaction yet, went in early", 5: "target 1.6R, took it anyway",
                   9: "forgot the calendar", 12: "moved the stop at the news",
                   13: "closed by hand at the first pullback"}
            trade.reasons = {n: why[n] for n in broke + trade.exit_deviations}
        folder = store.trade_dir(root, trade.id)
        trade.idea[0].images = [shot(folder, "idea-01-01.png", 200 + i)]
        trade.exit_images = [shot(folder, "exit-01.png", 300 + i)]
        store.save_trade(root, trade)

    # one position still open: the front page has a card of its own for those
    open_day = today - timedelta(hours=6)
    open_id = store.new_id(root, open_day, "EURUSD")
    store.save_trade(root, Trade(
        id=open_id, account="broker", pair="EURUSD",
        direction="short", style="swing", entry_tf="H4", risk=1.0,
        opened=open_day, opened_time=True, plan=plan.id,
        playbook="pullback", playbook_version="1.0",
        setup="A: reaction at a higher level", deviations=[],
        idea=[IdeaBlock(tf="H4", text=IDEAS[0],
                        images=[shot(store.trade_dir(root, open_id),
                                     "idea-01-01.png", 400)])],
        updates=f"**{open_day + timedelta(hours=3):%d.%m.%Y %H:%M}**: first "
                "push down held under the level, stop left where it was"))

    # one deposit half way, so that the equity curve has a hollow dot and a
    # step in its base line to show
    topped = start + timedelta(days=days // 2)
    store.save_adjustment(root, Adjustment(
        id=f"{topped:%Y-%m-%d}-deposit-broker", account="broker", kind="deposit",
        amount=300, day=topped.replace(hour=0, minute=0), comment="top up"))

    store.save_card(root, Card(
        day=today, grade="B", quality="B", pnl=174.0,
        focus="Stop taking the second entry after a loss.",
        process="Two setups planned in the morning, one taken, one skipped for "
                "the right reason, it never came back to the level.",
        learned="Waiting for the retest cost nothing and paid twice today.",
        errors="Sized up on the second trade to make the first one back.",
        best="GBPUSD long from the H4 imbalance: planned, sized, held.",
        overview="A quiet day traded quietly. The plan survived the session.",
        assessment=[Graded("GBPUSD long, H4 imbalance", "A", "Win +2.40 R"),
                    Graded("EURUSD long, second entry", "C", "Lose -1.04 R")]))

    store.save_week(root, Week(
        week=stats.week(today), grade="B", quality="B", progress=7,
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
        assessment=[Graded("EURUSD long, Monday", "B", "Win +1.53 R"),
                    Graded("GBPUSD long, Tuesday", "A", "Win +2.09 R"),
                    Graded("XAU short, Thursday", "C", "Lose -0.98 R")]))

    # a market note, with two of the trades above as its examples, so that
    # the Notes tab, the note page and the way back from a trade can be seen
    examples = [t.id for t in store.all_trades(root)
                if t.pair == "GBPUSD" and not t.is_open][:2]
    note_id = store.new_note_id(root, today - timedelta(days=3),
                                "Sweep before the London open")
    store.save_note(root, Note(
        id=note_id,
        title="Sweep before the London open",
        day=today - timedelta(days=3),
        blocks=[IdeaBlock(text="GBPUSD takes the Asian high or low in the hour "
                          "before London opens, then turns. The turn is the "
                          "trade; the sweep itself is not.",
                          images=[shot(store.note_dir(root, note_id),
                                       "note-01-01.png", 500)]),
                IdeaBlock(tf="What to wait for",
                          text="The M15 close back inside the range. An entry "
                               "on the wick alone was stopped twice in August.")],
        trades=examples))


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pb-demo"
    os.makedirs(root, exist_ok=True)
    build(root)
    print(f"invented journal written to {root}\n"
          f"PLAINBOOK_ROOT={root} PLAINBOOK_PORT=8899 python3 -m plainbook.server")
