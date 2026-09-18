# Plainbook

**A plain-text trading journal that lives on your machine.** Local, private,
fast, and built to be kept by an agent. Your trades are markdown files and
screenshots in a folder you own: no account, no cloud, no network calls.

[![tests](https://github.com/stop-loss-enjoyer/plainbook/actions/workflows/tests.yml/badge.svg)](https://github.com/stop-loss-enjoyer/plainbook/actions/workflows/tests.yml)
[![license: PolyForm Noncommercial](https://img.shields.io/badge/license-PolyForm%20Noncommercial-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#what-it-is-not)

![The journal](docs/journal.png)

<p align="center">
  <img src="docs/card.png" width="49%" alt="The daily card">
  <img src="docs/statistics.png" width="49%" alt="Statistics">
</p>

![A playbook: the figures by setup and what each rule cost](docs/playbook.png)

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
neither won nor lost, and counted in the EV, because it still paid its
commission.

## What it does

**Trades, written in two steps.** You open a position (account, pair, direction,
style, timeframes, risk, screenshots of the idea) and close it later with the
result, the PnL, the exit screenshot and your conclusions. The idea
gets written down before the market says who was right. The same position taken
on two accounts is filled in once: a duplicate goes to the second account with a
risk of its own.

**A stop moved to breakeven frees its risk.** One button on an open
position says the stop is at the entry: the trade can no longer lose what it
was sized for, so the daily loss limit stops counting it, and the statistics
later say what moving the stop was worth.

**The words in the form are yours.** The trading styles, the entry timeframes
and the execution formats are lists you edit on the Accounts tab. A word taken
out of a list only stops being offered; the trades that carry it keep it.

**Notes about the market.** A note is for what is not one trade: a level a
pair keeps respecting, a pattern that comes back, a lesson wider than a day.
Text, screenshots, and the trades of the journal tied to it as examples, so
the note is read with the trades that show it a click away.

**A plan before the trade.** A trading plan is a record of its own: the analysis
by timeframe with its screenshots, what you will do and what you will not, the
updates added while it runs and the review after. A trade points at the plan it
followed, so the plan page can show every trade that came out of it with its R,
say how many went with the narrative and how many against it, and answer the
only question worth asking of a plan.

**A playbook, and a checklist before every trade.** The rules of a way of
trading, written down once: the setups with their rules, the filters, the
rules of holding the position, the limits. A trade is opened under a
playbook and its rules are ticked in the form, a box each with a few words;
nothing is refused, but every rule left unticked is recorded with the
trade, with a line for why. The management rules are ticked at the close.
The statistics then say what each rule is worth: the trades that broke it
and what they brought in R, against the trades that kept every rule. Rules
change by version, and a trade keeps the rules it was ticked against.
[PLAYBOOK.md](PLAYBOOK.md) takes the form apart.

**A daily card.** The day reviewed on the pattern of a paper Daily Report Card:
process grade, opportunity quality, focus, what went well, errors, best trade,
overview, and a trades assessment where the day's trades get their marks and
their results, the result offered by the journal. The day's PnL is filled in
from the trades you closed, and stays editable.

**A weekly card.** The same on the pattern of a paper Weekly Report Card, one
per trading week: process grade, opportunity quality, progress on the focus,
the weekly process, what went well, errors, the best trade and the ones you
missed, the key lesson, and the same trades assessment as the daily card. The
PnL and the number of trades come from the week you traded, and stay editable.

**Statistics that answer honest questions.** Cut the whole history any way you
like and the page opens on what that cut did: the EV per trade, the winrate
beside the winrate it would need to break even, the payoff, the deepest fall
from a high, the mistakes and the best and worst trade, each read against the
trades the filter left out. Then the trades one bar each, or the weeks, months
or quarters once there are too many to tell apart, the distribution of R as
two rings, losses and wins cut by size, an equity curve per account, by date
or by trade, coloured against the balance it started from, and the tables,
dealt into two columns that end together; a row narrows the page to itself.

**A report read in a second.** A month or a quarter opens on its figures, one
tile each: the result, the winrate with the EV and the deepest fall from a
high, each with the period before in grey under it, then the mistakes, the
cards written against the days traded, the best and the worst trade. Under
them every closed trade of the period stands as one bar against the line of
the stop, the rings of the period beside it; then which rules were not met and
what they cost, the errors you wrote on your cards, your conclusions, kept
through every rebuild, and only then the tables. The Reports tab is a shelf of
every month and quarter since the first closed trade, with its figures whether
a report was built for it or not. A pair, a style, an account or a direction
in the tables leads back to the trades it was counted from.

**Pairs you recognise before you read them.** EURUSD carries two round flags,
GER40 the German one, gold and the coins a lettered face. The flags are drawn in
the code, so nothing is fetched from anywhere.

**A list you can actually read.** Trades are grouped by trading weeks, with the
count, win rate, EV, Σ PnL and Σ R in the total row; one switch turns it into months
or quarters. Filters hide behind a funnel button that says how many of them are on.

**Screenshots by Ctrl+V.** Click the drop zone, paste, done. From TradingView,
from a screen capture, from anywhere. A cross on the thumbnail takes it back
out. There is a zone in the idea of a trade, in its conclusions, in the analysis
and the plan of a trading plan, and in the update of one, so a picture lands
under the line it belongs to.

**Money in and out, counted apart from trading.** Deposits, withdrawals and
fees are written down on the Accounts tab, and the money taken off an account
has a running total of its own. A payout is not a loss, and an account that pays
out should not look worse than it was. When the broker shows a different
balance, you type the real number and the journal records the difference as a
correction: history is never edited to make a figure agree.

**Nothing is shredded.** Deleting a trade, a plan, a card, an account or a money
record moves it to `.trash`, and the Accounts tab lists what is there with a
Restore button. A mis-click should not cost a record.

**Nothing is fatal.** A file that does not read, a date typed the wrong way
round, a letter in a number, is named at the top of every page with the reason,
and everything else loads and counts without it. `tools/check_journal.py` runs
the same check from the terminal.

**Search across everything written.** A word or a phrase is looked for in every
idea, conclusion, note, plan, update, review and card, and every hit is a link
to the record with the matching words shown around it.

**A limit for the day on a prop account.** Set it once, and the tile of the
account adds up what today has already cost and what the open trades still put
at risk, turns amber at four fifths of the limit and red when it is reached.

**The deepest fall from a high.** How far a selection went under its own high,
in R. On the Statistics tab it also says between which dates, whether it has
been made back and the longest run of losses of the selection; a report carries the
figure against the period before.

**The selection as CSV.** One button next to the filters writes the filtered
list into a file for a spreadsheet, with every stored field and the computed
ones: R, the balance at entry, the risk in money.

**Something to show another trader.** Share, on a trade, over the filtered
list, or on a report, writes one HTML file with the screenshots carried inside
it: it opens on any machine, offline, with no journal running, and prints to a
PDF that reads like the journal. Money never travels in it, not the PnL, the
risk in money, a balance or the size of an account, only R and the percent the
risk was written as. You see the document, and what it will weigh, before you
send it.

**Every account in its own currency.** The sign follows the account; a figure
that spans accounts carries the currency they share, or none when they differ.

## Built to be kept by an agent

Most software tolerates a coding agent. This one is arranged for it, and the
arrangement is the same one that makes the journal private and durable in the
first place: plain files, no dependencies, a small surface.

- **Nothing to resolve, nothing to build.** No package manager, no lockfile, no
  bundler. An agent that can run `python3` can run the whole project.
- **The tests finish in a few seconds.** 273 of them, no fixtures, no network.
  A change can be verified in the same breath it was written.
- **The rules are written down, not remembered.** [AGENTS.md](AGENTS.md) holds
  the map of the code, the invariants that must not be broken, recipes for the
  usual tasks, and the traps that have already bitten this project, each one
  with the reason it exists.
- **A guard stands between an agent and your records.** `tools/check_public.py`
  refuses a push that would carry trade records, private paths or anything
  else it recognises as yours; it runs as a pre-push hook and in CI.
- **The whole program is ~13 100 lines** of straightforward Python, and the
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
Writing a playbook, part by part: **[PLAYBOOK.md](PLAYBOOK.md)**.
What is already here, tab by tab, and which requests it answers:
**[FEATURES.md](FEATURES.md)**.

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

A playbook is a folder too: `journal/playbooks/<id>/playbook.md` with the
rules as a checklist, `versions/` for the rules as they were before each
revision, `shots/` for the screenshots of the reviews. A trade opened under
one carries `playbook`, `playbook version`, `setup`, `deviations`, `exit
deviations` and `reasons` in its header. An empty `deviations:` key means
the rules were ticked and every one was met; a missing key means they were
never ticked. Keep that difference if you edit a file by hand.

That is the whole storage format. No database, no schema migrations, no export
button: the export is `cp -r`.

The rest of the layout:

```
journal/
  accounts/<id>.md        start balance, currency, archived
  trades/<id>/            one trade = one folder
  cards/YYYY-MM-DD.md     the daily card
  cards/YYYY-Www.md       the weekly card, in the same folder
  plans/<id>/             one plan = one folder, screenshots and all
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

**R** = PnL / (risk% × the account balance **at the moment of entry**). The exit
of a trade carries its hour, so a position closed earlier the same day is already
in that balance; an exit written without an hour counts from the next day, since
nothing then says which of the two came first. Measured this way, 1% of risk
stops looking like the same amount of money forever.

**Win rate** = wins / (wins + losses). Break-even trades stay out of the
denominator: such a trade ended neither way, and diluting the hit rate with it
would be dishonest. What they do cost (commission, the spread, the opportunity
spent) is fully visible in the sum and in the EV, where they count like
everything else.

**EV** = Σ R / closed trades: what a trade brought on average, in R. It stands
to the right of every win rate on the front page, and is a column of every
table on the Statistics tab and in the reports. A win rate worked out from
fewer than five decided trades stands in grey, because a percentage of two
trades is not a rate. Unlike the win rate, it counts
the break-evens: a trade closed at zero still paid its commission and never
comes back at exactly zero R.

**A period is what closed in it.** A report, the current-period tile on the
front page and the cards count the trades that closed in the period, the way a
broker states a month. The list of trades groups by entry, because a journal is
read by the decisions in it.

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
| the whole program | **~13 100 lines of Python** |

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
all work. The trading styles, the entry timeframes and the execution formats are
lists you edit on the Accounts tab, so the words in the form are your own.

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

PolyForm Noncommercial 1.0.0, from version 1.5.1 on. See [LICENSE](LICENSE).

You can run the journal, change it for yourself and pass it on, for any
purpose that is not commercial. Selling it, selling it under another name, or
building it into a product that is sold is not allowed. Every version up to
1.5.0 was released under MIT, and that is not withdrawn from them.

Required Notice: Copyright 2026 stop-loss-enjoyer
