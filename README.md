# Plainbook

**A plain-text trading journal that lives on your machine.** Local, private,
fast, and built to be kept by an agent. Your trades are markdown files and
screenshots in a folder you own: no account, no cloud, no network calls.

[![tests](https://github.com/stop-loss-enjoyer/plainbook/actions/workflows/tests.yml/badge.svg)](https://github.com/stop-loss-enjoyer/plainbook/actions/workflows/tests.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#what-it-is-not)

![The journal](docs/journal.png)

<p align="center">
  <img src="docs/card.png" width="49%" alt="The daily card">
  <img src="docs/statistics.png" width="49%" alt="Statistics">
</p>

<p align="center"><i>The screenshots are made on invented data.</i></p>

## Why

A trading journal holds the most private thing a trader has: every position, its
size, and the reasoning behind it. Most journals are web services, so you type
all that into someone else's database and hope for the best.

This one is a small program that serves a web interface on `127.0.0.1` and
writes plain files into a folder. Nothing is uploaded, because nothing here
knows how to upload. If the project disappears tomorrow, your records stay
exactly as they are: text you can read in any editor, images you can open in any
viewer.

It is opinionated where it matters. Balances are computed from history rather
than stored, so they cannot drift. Risk and R are measured against the balance
**at the moment of entry**, not against a number typed in once. Break-even
trades are kept out of the win rate, because a trade that ended at zero was
neither won nor lost.

## What it does

**Trades, written in two steps.** You open a position (account, pair, direction,
style, timeframes, risk, screenshots of the idea) and close it later with the
result, the PnL, the exit screenshot and your conclusions. The idea
gets written down before the market says who was right.

**A daily card.** The day reviewed on the pattern of a paper Daily Report Card:
process grade, opportunity quality, focus, what went well, errors, best trade,
overview. The day's PnL is filled in from the trades you closed, and stays
editable.

**Statistics that answer honest questions.** An equity curve per account, the
distribution of R as two rings, losses and wins each cut by size, slices by
style, pair and account, and a monthly or quarterly report built on a button,
with the figures recomputed and your conclusions kept. Every row of a report is
a link back to the trades it was counted from.

**Pairs you recognise before you read them.** EURUSD carries two round flags,
GER40 the German one, gold and the coins a lettered face. The flags are drawn in
the code, so nothing is fetched from anywhere.

**A list you can actually read.** Trades are grouped by trading weeks, with the
count, win rate, Σ PnL and Σ R in the total row; one switch turns it into months
or quarters. Filters hide behind a funnel button that says how many of them are on.

**Screenshots by Ctrl+V.** Click the drop zone, paste, done. From TradingView,
from a screen capture, from anywhere. A cross on the thumbnail takes it back out.

**Money in and out, counted apart from trading.** Deposits, withdrawals and
fees are written down on the Accounts tab, and the money taken off an account
has a running total of its own. A payout is not a loss, and an account that pays
out should not look worse than it was. When the broker shows a different
balance, you type the real number and the journal records the difference as a
correction: history is never edited to make a figure agree.

**Nothing is shredded.** Deleting a trade, a card or a money record moves it to
`.trash`. A mis-click should not cost a record.

## Built to be kept by an agent

Most software tolerates a coding agent. This one is arranged for it, and the
arrangement is the same one that makes the journal private and durable in the
first place: plain files, no dependencies, a small surface.

- **Nothing to resolve, nothing to build.** No package manager, no lockfile, no
  bundler. An agent that can run `python3` can run the whole project.
- **The tests finish in under a second.** 85 of them, no fixtures, no network.
  A change can be verified in the same breath it was written.
- **The rules are written down, not remembered.** [AGENTS.md](AGENTS.md) holds
  the map of the code, the invariants that must not be broken, recipes for the
  usual tasks, and the traps that have already bitten this project, each one
  with the reason it exists.
- **A guard stands between an agent and your records.** `tools/check_public.py`
  refuses a commit that would carry trade records, private paths or anything
  else it recognises as yours; it runs as a pre-push hook and in CI.
- **The whole program is ~4 000 lines** of straightforward Python, and the
  routing table fits on one screen. It fits in a context window, so an agent
  reasons about the real thing rather than about a summary of it.
- **One language throughout:** code, comments, documents and commit messages.
  The guard enforces it, so a contributor's own language never leaks into a
  public page.

`CLAUDE.md` points at the same guide, so Claude Code picks it up unprompted.

## Quick start

Python 3.10 or newer. Nothing to install.

```bash
git clone https://github.com/stop-loss-enjoyer/plainbook.git
cd plainbook
python3 -m plainbook.server
```

Open <http://localhost:8778>, go to **Accounts** and create one: a name and a
start balance. The start balance is a point of reference, not a memory of the
past. Opening an account today, put in today's real balance, and the computed
balance is right from the first minute.

- `PLAINBOOK_PORT` changes the port (8778 by default).
- `PLAINBOOK_ROOT` changes where the records live (the project folder by default).

Autostart on Linux, Windows and macOS, plus desktop integration:
**[INSTALL.md](INSTALL.md)**. The day-to-day guide: **[GUIDE.md](GUIDE.md)**.

## Your data

A trade is a folder. Inside it, one markdown file and the pictures:

```
journal/trades/2026-08-29-01-eurusd/
├── trade.md
└── shots/
    ├── idea-01-01.png
    └── exit-01.png
```

And `trade.md` reads like this:

```markdown
---
id: 2026-08-29-01-eurusd
account: broker
pair: EURUSD
direction: long
style: swing
entry tf: H4
execution:
  - Market Entry
risk %: 1
entry: 2026-08-29 14:30
result: Win
pnl $: 174
exit: 2026-08-31
---

## Idea

### H4

Range breakout, waiting for a retest.

![](shots/idea-01-01.png)

## Exit

![](shots/exit-01.png)

## Conclusions

Held to target, did not move the stop.
```

That is the whole storage format. No database, no schema migrations, no export
button: the export is `cp -r`.

The rest of the layout:

```
journal/
  accounts/<id>.md        start balance, currency, archived
  trades/<id>/            one trade = one folder
  cards/YYYY-MM-DD.md     the daily card
  adjustments/<id>.md     deposit, withdrawal, fee, reconciliation
  reports/2026-08.md      monthly and quarterly reports
.trash/                   deleted records, kept just in case
.drafts/                  screenshots of unsubmitted forms, swept daily
```

**Put it under git.** The journal is text, so `git log` gives you the history of
your own thinking, and a way back if you fix a number you should not have.

**Keep the records apart from the program** once the code itself is under git:

```bash
PLAINBOOK_ROOT=~/plainbook-data python3 -m plainbook.server
```

Then the program can live in a public repository while the records sit in a
private one that is never pushed anywhere.

## How the numbers work

**Balance** = start balance + Σ PnL of closed trades + Σ adjustments. It is
never written to a file. Nothing can go stale, because there is no stored copy
to go stale.

**R** = PnL / (risk% × the account balance **at the moment of entry**). The
balance is taken as of the entry day: a trade closed today does not change
today's entry. Measured this way, 1% of risk stops looking like the same amount
of money forever.

**Win rate** = wins / (wins + losses). Break-even trades stay out of the
denominator: such a trade ended neither way, and diluting the hit rate with it
would be dishonest. What they do cost (commission, the spread, the opportunity
spent) is fully visible in the sum and the average R, where they count like
everything else.

**Total R rather than a total in dollars.** With more than one account, a dollar
on a prop account and a dollar on your own are different kinds of money. The
front page refuses to add them up.

**A balance that does not match the broker** is not fixed by editing history: it
is written down as an adjustment (`reconciliation`, `fee`, `deposit` or
`withdrawal`) with a comment saying where the difference came from.

## Privacy

The server binds `127.0.0.1` and refuses requests whose `Origin` is not itself.
There is not a single outbound URL in the code: no CDN, no fonts, no analytics,
no update check. Styles and scripts are inlined into the pages, so the interface
works with the network cable pulled out.

This is a single-user program with no authentication. It is meant for your own
machine; do not put it behind a public address.

## Speed and footprint

Measured on a journal of 159 trades with 363 screenshots:

| | |
|---|---|
| front page, 159 trades | **8 ms**, 68 KB |
| a trade page | **2 ms**, 14 KB |
| statistics with charts | **7 ms**, 37 KB |
| server memory | **25 MB** |
| the whole program | **~4 000 lines of Python** |

Pages are plain HTML rendered by one Python process: no framework, no bundler,
no build step. The charts are SVG generated on the server. There is nothing to
wait for.

## Desktop integration

`desktop/` holds working samples for Linux: a user systemd unit, a window toggle
for a hotkey, and a bar widget for [Omarchy](https://omarchy.org/) that carries
the number of open positions on its icon. Windows and macOS autostart are
described in [INSTALL.md](INSTALL.md).

## What it is not

Stated plainly, so nobody waits for it:

- **No cloud, no sync, no multi-user.** One person, one machine, one folder.
- **No broker or exchange API.** Trades are entered by hand, on purpose: typing
  the idea in is the part that makes a journal worth keeping.
- **No dependencies, ever.** The Python standard library is the whole of it.
  That is a design constraint, not an accident: a journal you may still need in
  five years should not rot because a package did.
- **No mobile app.** It is a page on localhost.
- **Not a backtester and not an analytics platform.** It records what you did
  and tells you honestly how it went.

## FAQ

**Forex only?** No. A pair is free text, so stocks, futures and crypto tickers
all work. The vocabulary of trade styles is the one place with fixed values, and it
lives in `plainbook/model.py`.

**Can I edit the files by hand?** Yes, that is the point. Keep the header keys
intact; everything else is ordinary markdown.

**How do I back it up?** Copy the `journal/` folder, or keep it under git and
push it to a private repository of your own.

**Why not a database?** Because a database is a wall between you and your
records. Text files outlive the program that wrote them.

**Can I run it on a server and reach it from anywhere?** Please do not. There is
no authentication, and adding some would not make it a safe thing to expose.

**Where does the name come from?** Plain text, plainly kept: a book of trades in
files that you, an editor, a script or an agent can read without asking
permission.

## Contributing

Bug reports and small, focused pull requests are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) for people and [AGENTS.md](AGENTS.md) for
agents. The short version: keep it dependency-free,
run `python3 -m unittest discover -s tests`, and remember that somebody's
trading history is on the other end of this code.

## Licence

MIT. See [LICENSE](LICENSE).
