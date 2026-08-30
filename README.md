# TradingJournal

A local trading journal. It runs entirely on your own machine: no cloud, no
account, no telemetry. Your records are plain text files and images you can
read with any editor.

No dependencies — the Python standard library and nothing else.

- **A trade is written in two steps**: you open the position (account, pair,
  direction, style, timeframes, risk, screenshots of the idea) and later close
  it (result, PnL, exit screenshot, conclusions). The idea gets written down
  before the market says who was right.
- **A daily card** — the day reviewed on the pattern of a paper Daily Report
  Card: process grade, opportunity quality, focus, errors, best trade, overview.
- **Balances are computed, never stored**: start balance + PnL of closed trades
  + adjustments. A balance cannot drift away from reality because nothing keeps
  a stale copy of it.
- **Statistics in R**: R = PnL / (risk% × account balance at the moment of
  entry) — not against a fixed number, so 1% of risk stops looking like the
  same amount of money forever.
- The list of trades is **grouped by trading weeks**, switchable to months and
  quarters.
- **Monthly and quarterly reports** at the press of a button: the figures are
  recomputed, your conclusions are never overwritten.
- Screenshots are pasted into the form with **Ctrl+V** and removed with a cross.
- Deleted trades and cards go to `.trash`, they are not shredded.

Everything is served from `127.0.0.1` and nothing leaves the machine.

![The journal](docs/journal.png)

<p align="center">
  <img src="docs/card.png" width="49%" alt="The daily card">
  <img src="docs/statistics.png" width="49%" alt="Statistics">
</p>

*The screenshots are made on invented data.*

## Getting started

    python3 -m tj.server          # Windows: py -m tj.server

Then open http://localhost:8778 and create an account on the **Accounts** tab.
The start balance is a point of reference, not a memory of the past: opening an
account today, put in today's real balance.

- `TJ_PORT` changes the port (8778 by default).
- `TJ_ROOT` changes where the records live (the project folder by default).

Full install, including autostart on Linux, Windows and macOS: **[INSTALL.md](INSTALL.md)**.
How to use it day to day: **[GUIDE.md](GUIDE.md)**. What changed: **[CHANGELOG.md](CHANGELOG.md)**.

## Keeping the records apart from the program

Set `TJ_ROOT` to a folder of your own and the journal keeps its records there:

    TJ_ROOT=~/TradingJournal-data python3 -m tj.server

That is the arrangement to prefer once the program is under git — the code can
then be shared or published while the records stay private, in a repository of
their own that is never pushed anywhere.

## Layout

    journal/                       the source of truth, worth keeping under git
      accounts/<id>.md             account: start balance, currency, archived
      trades/<id>/trade.md         one trade = one folder
      trades/<id>/shots/           the pictures of that trade
      cards/YYYY-MM-DD.md          the daily card
      adjustments/<id>.md          deposit, withdrawal, fee, reconciliation
      reports/2026-08.md           monthly and quarterly reports
    .trash/                        deleted records, outside git
    .drafts/                       screenshots of unsubmitted forms, swept daily
    tj/                            the code
    tests/                         the tests
    tools/                         one-off utilities
    desktop/                       desktop integration samples (Linux)

A trade id is `YYYY-MM-DD-NN-pair`, for example `2026-08-29-01-eurusd`.

## The format of a trade

    ---
    id: 2026-08-29-01-eurusd
    account: broker
    pair: EURUSD
    direction: long
    style: swing
    entry tf: H4
    execution:
      - M15
    risk %: 1
    entry: 2026-08-29 14:30
    result: Win          <- these three lines are absent while the position is open
    pnl $: 174
    exit: 2026-08-31
    ---

    ## Idea

    ### H4

    Range breakout, waiting for a retest.

    ![](shots/idea-01.png)

    ## Exit

    ![](shots/exit-01.png)

    ## Conclusions

    Held to target, did not move the stop.

## The format of a daily card

    ---
    date: 2026-08-30
    process grade: B
    pnl $: 250
    opportunity quality: A
    ---

    ## Focus
    ## Process
    ## Learned
    ## Errors
    ## Best trade
    ## Overview

## How the figures are worked out

**Balance** = start balance + Σ PnL of closed trades + Σ adjustments. It is
never written into a file.

**R** = PnL / (risk% × the account balance at the moment of entry). The balance
is taken as of the entry day: a trade closed today does not change today's entry.

**Winrate** = wins / (wins + losses). Break-even trades stay out of the
denominator — such a trade ended neither way; what it cost is fully visible in
the sum and the average R, where BE counts like everything else.

**Total R** is more honest than a total in money once there is more than one
account: a dollar on a prop account and a dollar on your own are different kinds
of money, which is why the front page has no grand total in dollars.

## Tests

    python3 -m unittest discover -s tests

## Licence

MIT — see [LICENSE](LICENSE).
