# What is already here

A map of everything the journal does, written for the agent that is about to
be asked to add something. Read it before writing code, and read it again when
the request uses the words of a trader rather than the words of this program.
Almost every such request names a thing that already exists here under a name
of its own. The one that has been built twice already is the trading system:
a person asked their agent for a "trading system" tab, the agent did not find
the words on any tab and built a new one, and the journal ended up with two
places holding the same rules, one of which nothing checks a trade against.
The trading system is the **Playbooks** tab. Everything else has a home too,
and this file names it.

The full manual is [GUIDE.md](GUIDE.md); the playbook, part by part, is
[PLAYBOOK.md](PLAYBOOK.md). This file does not repeat them. It says what
exists, where it stands, and which requests it answers, so that the answer to
"can you add..." is usually "it is on this tab".

## Before adding anything

1. **Find the request in the table below.** The words on the left are how
   traders ask; the right names where the thing lives. If it is there, show
   the owner the tab and stop.
2. **If it is nearly there,** extend the record that holds it: a new heading
   in a playbook's notes, a new word in a vocabulary, a new limit kind, a
   new field on an existing form. The recipes in [AGENTS.md](AGENTS.md)
   cover every one of these, and none of them is a new tab.
3. **A new tab is nearly always a duplicate.** The navigation is nine tabs
   and each holds one kind of record: trades, playbooks, plans, notes,
   cards, statistics, reports, accounts, search. A tenth kind of record is
   a rare thing; a tenth view of an existing kind belongs on the tab of that
   kind.
4. **Text the journal cannot count goes into notes, not into a form.** A
   playbook takes any `## heading` in its notes and shows it as a section
   of its own; a note takes any text with screenshots. Neither needs code.

## If you are asked for...

| the words of the request | where it already lives |
|---|---|
| trading system, strategy, my rules, the edge, the method, the approach | **Playbooks.** A playbook is the trading system written as rules the journal holds every trade against. Name, status, version, the idea behind it, setups, filters, management, limits, notes in any sections, review by blocks. See below and PLAYBOOK.md. |
| setup, entry conditions, entry model, entry types, pattern, signal, trigger | **Playbooks, setups.** One setup per way of entering, with its rules; several setups with names when there are several ways in. Entry formats as words (market, limit, stop) are a vocabulary list on **Accounts** and a field of the trade. |
| checklist, pre-trade checklist, confirmation list | **Playbooks, in the trade form.** Picking a playbook opens the rules of the chosen setup and the filters, a box each. Unticked rules are recorded with the trade with a line for why. |
| filters, conditions for every trade, news filter, session, trading hours, day of the week | **Playbooks, filters.** Rules checked before every trade whatever the setup. Anything that is a yes or no at the moment of entry is a filter; anything that is a figure the journal can count is a limit. |
| trade management, position management, exit rules, stop rules, trailing, partials, holding rules | **Playbooks, management.** Rules of holding the position, ticked at the close of the trade; the page of an open trade lists them to be kept in mind. |
| risk management, risk per trade, max trades, max loss, max positions, exposure, sizing | **Playbooks, limits** (risk per trade, trades per week and per month, loss per week in R, positions open at once, the longest hold, the least RR, any other of your own), counted above the checklist of a new trade and turned red when this trade would go past them. **Accounts, daily loss limit** for a prop account, counted on the tile of the account. The sizing formula in words is a section of the playbook's notes. |
| drawdown, max drawdown, losing streak | **Statistics, Deepest fall from a high**: how far the selection went under its own high in R, between which dates, whether it was made back, the longest run of losses. The reports carry the figure against the period before. |
| instruments, markets, pairs, watchlist | **Accounts, Pairs**: the list the trade form offers. Which markets a playbook is for is a section of its notes; its **styles** are the styles of the trade form it applies to. |
| timeframes, higher timeframe, entry timeframe, top down | **Accounts, vocabularies** (the entry timeframes the form offers); the trade's **entry tf** and the timeframes of its idea; a plan's analysis by timeframe; a playbook rule such as "level on W or D". |
| analysis method, narrative, context, market model, theory, fundamentals, the why behind the rules | **Playbooks, the intro** (what the playbook is) and **the notes**, where any `## heading` becomes a section of the page: the markets, the math, the model, what is still being decided. Knowledge wider than one system is a **Note**. |
| performance, edge analysis, what works, optimization, which setup earns, what a rule costs | **Statistics, By playbook** (a row per playbook with its setups, the clean and held shares); **the page of a playbook**: By setup, What a rule costs (trades that broke a rule and what they brought in R against the trades that kept every rule), Reasons given. The whole **Statistics** tab for any cut of the history. |
| review of the system, block review, revision, versioning of rules | **Playbooks, Review** (dated entries with screenshots, one per completed block, the tab turns amber when a block is due) and **versions**: rules change under a new number once trades were ticked against the old one, and a trade keeps the rules it was ticked against. |
| status of a system: testing, live, dropped | **Playbooks, status**: experiment, active, retired. A retired playbook leaves the form and keeps its trades and figures. |
| plan for the day, plan for the week, pre-market, scenarios, what I will and will not do | **Plans.** A plan is a record of its own: pair, narrative, analysis by timeframe with screenshots, the plan, dated updates, a review after. A trade points at the plan it followed; the plan page counts its trades and says how many went with the narrative. A plan the market went against is voided, with the reason kept. |
| notes, lessons, patterns, levels, observations, a knowledge base, a wiki | **Notes.** Text and screenshots, with the trades of the journal tied to a note as examples. |
| daily review, end of day, journal grade, process grade, report card | **Cards, + DRC**: the day on the pattern of a paper Daily Report Card, with the trades of the day graded. |
| weekly review | **Cards, + WRC**: the same for a trading week. |
| monthly review, quarterly review, period report | **Reports.** A shelf of every month and quarter since the first closed trade; a report opens on its figures against the period before, the mistakes, the rules not met, the errors from the cards, your conclusions, kept through every rebuild. |
| statistics, analytics, dashboard, equity curve, win rate, expectancy, R multiples, distribution | **Statistics.** Any cut of the history: the strip (EV, winrate against the break-even winrate, payoff, deepest fall, mistakes, best and worst trade), the bars per trade or per period, the R rings, the equity per account, the tables by pair, style, account, direction, playbook. The front page holds the current period, the account tiles and the list. |
| trade commentary while open, updates, journaling during the trade | **The page of an open trade, Update**: a dated line with a screenshot, kept after the close. |
| breakeven, stop moved to entry, risk-free | **Breakeven** on an open position: frees its risk in the daily loss limit, and Statistics says what moving the stop was worth. |
| stop overrun, slippage, losses past the stop, what a stop costs | **Statistics, Past the stop** with the stop edge slider, and the rings of losses cut where a stop lands. |
| several accounts, prop firm and broker, the same trade on two accounts | **Accounts**: any number, each in its own currency, archive for the closed ones; the trade form has Duplicate on other accounts, a copy per ticked account with a risk of its own. |
| deposits, withdrawals, payouts, fees, balance does not match the broker | **Accounts, money**: deposits, withdrawals and fees written apart from trading, withdrawals with a running total; a correction records the difference to the broker without editing history. |
| custom fields, my own words in the form, styles, entry formats | **Accounts, vocabularies**: styles, entry timeframes, execution formats are lists you edit; a word taken out stops being offered and stays on the trades that carry it. |
| screenshots, charts, pictures | Paste with Ctrl+V into any drop zone: the idea and the exit of a trade, its updates, a plan and its updates, a note, a playbook review. |
| export, spreadsheet, CSV, backup | **CSV** next to the filters of the list; the records themselves are markdown and PNG files in `journal/`, a copy of that folder is the backup. |
| share with a mentor, send a trade, print a report, PDF | **Share** on a trade, on the filtered list and on a report: one HTML file with the screenshots inside and no money in it, opens offline, prints to PDF. |
| search | **Search**: every idea, conclusion, note, plan, update, review and card. |
| delete, undo, restore | Nothing is shredded: a deleted record goes to `.trash` and the **Trash** card on Accounts restores it. |
| import old trades, history from Notion or a spreadsheet | `tools/import_csv.py` writes trades the way the interface does. |
| count the trades I already took under this system | `tools/attach_playbook.py` ties the trades of the playbook's styles opened from its *counts from* date. |
| the app, a window, a hotkey, autostart, install without Python | The file per system on the releases page (opens the journal as a window of its own, records in `~/Plainbook`), the `plainbook` command of a pipx install, [INSTALL.md](INSTALL.md) and the `desktop/` folder: the service, the toggle script, the launcher. |

## The tabs, one by one

**Journal**, the front page. Account tiles with the computed balance, the
daily loss limit where one is set, the open positions with Breakeven and
Close, the summary tiles of the current period, the list of trades grouped by
weeks, months or quarters with filters, CSV and Share. **+ Trade** opens a
position: account, pair, direction, style, timeframes, risk as a percent or as
money, the plan and the playbook it is taken under, the checklist, the idea
with screenshots by timeframe. A click on a row opens the trade: every field,
the idea, the updates, the exit, the conclusions, the rules with a tick or a
cross, and the buttons Edit, Update, Breakeven, Close, Share, Delete;
the same trade goes onto other accounts from its form, Duplicate on other
accounts, each copy with a risk of its own.

**Playbooks**, the trading systems. One record per way of trading, each with
its own sample and figures. The list shows every playbook with its status,
version and block progress; the page shows the intro, the numbered rules by
setup, the filters, the management rules, the limits, every section of the
notes, By setup, What a rule costs with the reasons given, Earlier versions,
and Review. **+ Playbook** is a form of six cards: header, setups, filters,
management, limits, notes. The tab is amber while the journal has no
playbook, and again when a block has run its course without a review.

**Plans**, what was supposed to happen. Written before the market, for a day
or a week and a pair: narrative, analysis by timeframe with screenshots, the
plan, updates while it runs, the review. The list marks the current plan,
the ones ahead and the voided ones. A trade names the plan it follows, and
the plan page shows its trades with their R.

**Notes**, what is not one trade. A level, a pattern, a lesson; text and
screenshots; the trades tied to the note as examples, so it is read next to
the trades that show it.

**Cards**, the reviews of a day and a week. The daily card follows a paper
Daily Report Card, the weekly card a Weekly Report Card: process grade,
opportunity quality, focus, what went well, errors, the best trade, the
trades assessment with the mark of every trade next to its result. The PnL
and the counts come from the trades and stay editable.

**Statistics**, the honest questions. Any cut of the history by account,
pair, style, direction, result, period, and the page opens on what
that cut did: the strip, the bars, the R rings, the losses cut at the stop
edge, the equity per account, By playbook, the stop at breakeven, the tables.
A bar or a row narrows the page to itself, Back steps out one click at a
time, the trades of the cut stand at the foot.

**Reports**, a month or a quarter in a second. The shelf of every period
since the first closed trade, with its figures whether a report was built
or not. A built report is a file, the archive of that month, and holds the
conclusions; its figures are read off the journal at every look.

**Accounts**, the things set once. Accounts with a start balance, a
currency, a daily loss limit, archive; money in and out; corrections; the
vocabularies of the trade form; the pairs; the trash.

**Search**, every word ever written into the journal.

## The records and where they live

Everything is a markdown file with a header and, where there are pictures,
a `shots/` folder next to it. `journal/` is the whole journal; a copy of it
is a backup; any editor reads it.

    journal/
      accounts/       one file per account
      adjustments/    deposits, withdrawals, fees, corrections
      trades/<id>/    trade.md and shots/
      playbooks/<id>/ playbook.md, versions/<number>.md, shots/ of the review
      plans/<id>/     plan.md and shots/
      notes/<id>/     note.md and shots/
      cards/          the daily and weekly cards
      reports/        the built reports
      vocabulary.md   the styles, timeframes and execution formats the form offers
      pairs.md        the pairs the form offers
      settings.md     the stop edge
      .trash/         what was deleted, restorable from Accounts

Nothing computable is stored: balances, R, the figures of every table are
worked out from the history on every load. A field a record does not have
yet is added to the form and the file, never to a separate store.

## What is deliberately not here

Not because nobody thought of it, but because it is not this program, and a
request for it is answered with a fork rather than a feature: broker and
exchange integrations, automatic trade import, cloud sync, accounts and
logins, multi-user, a front-end framework, a build step, a stored balance.
Likewise the journal refuses nothing at the moment of a trade: a rule left
unticked, a limit gone past, a plan not followed are recorded with the
reason and counted later, never blocked. Do not add a block.
