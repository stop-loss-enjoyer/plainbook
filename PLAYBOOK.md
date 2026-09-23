# Writing a playbook

What each part of a playbook is for, how the journal uses it, and what it is
tied to. The form is on the **Playbooks** tab, **+ Playbook**; the file it
writes is `journal/playbooks/<id>/playbook.md`, readable by eye.

A playbook is one way of trading written down as rules: what has to be true
before a trade is opened, and how the position is held after. Where a plan
covers a day and a note covers a lesson, the playbook is the trading system
itself, and it changes by version. A journal can hold several, one per way of
trading, each with its own sample and its own figures.

## The header

**Name.** How the playbook is called in the trade form, in the tables and on
its page. The folder is named from it once and does not change with it
later, because trades point at the folder.

**Status.** *Experiment* while the sample is being built and the rules are
on trial; a new playbook starts here. *Active* once the rules are trusted. *Retired* when the playbook
is not offered any more: it leaves the trade form and drops to the end of
the list, but its page, its trades and its figures stay, and a trade opened
under it keeps its link.

**Version.** The number of the rules as they stand; a new playbook starts
at 1.0. Until the first trade is ticked against a version, the rules are a
draft and change freely. Once a trade has been through the checklist under
the number, a change of the rules asks for a new number. The rules as they
were are kept under *Earlier versions* on the page, and a trade keeps
showing the rules it was ticked against, whatever the playbook says later.
Only the rules and the names of the setups are held to this; the intro, the
notes, the limits and the status change freely.

**Counts from.** The day the tool that ties old trades to the playbook
starts from (written as `since` in the file): trades of the playbook's
styles opened before it belong to the time before the rules and are left
alone on purpose. It starts at today; move it back if older trades are to
be tied. The figures and the block count every trade opened under the
playbook, whatever its date.

**Block.** How many trades make one review. The page shows how far the
current block has come; when a block is complete and has no review yet,
the tab turns amber and the page says so. Leave it empty if the rules are
not reviewed by blocks.

**Styles.** The styles of the trade form this playbook is for. Picking the
playbook in the form sets the style to the first of them; the tool that
ties old trades to a playbook takes trades of these styles.

## What the playbook is

A few lines on the idea behind the rules and when they were written, shown
at the top of the page. This part is never ticked; it is the place for what
the rules are trying to do.

## Setups

A setup is one way of entering, with the rules that have to be true for it.
A playbook with one way of entering has one setup and leaves its name
empty; a playbook with several names each one, and the trade form asks
which setup the trade is taken under. Setups get their own figures on the
page and under the playbook in the statistics, which is how a way of
entering that loses is told apart from one that earns.

Each setup has a line on what it is, and its rules.

**A rule** has two parts. The few words are what the checklist shows in the
trade form, short enough to be read at the moment of opening. The whole rule is the explanation behind them, shown on the page
and behind the question mark in the checklist. A rule is a statement that
is either true or not at the moment of the entry; a rule that cannot be
answered yes or no at that moment belongs elsewhere, in the management
rules or in the notes.

Rules are numbered through the whole playbook, setups first, then the
filters, then the management. The number is what a trade records when a
rule was not met, and what the cost of a rule is counted by.

## Filters

Rules checked before every trade, whatever the setup: the news, the
session, the pair, what happened to the same pair a day ago. The same two
parts as a setup rule. They come after the setup's rules in the checklist.

A limit the journal can count belongs under *Limits* rather than here: the
count of trades this week, the loss of the week, the positions open at once
are shown by the journal itself above the checklist, so they need no box.

## Management

The rules of holding the position: the stop not moved, the position held to
its target, closed by Friday, added to only by the rule. They are ticked when
the trade is closed, in the form that closes it and in the form of a closed
trade. While the trade is open they stand on its page as a plain list, to be
kept in mind. A list of three to five rules gets ticked; a list of ten gets
skipped.

## Limits

Figures the playbook caps. A value is a plain number; the unit stands in
the label, and the loss per week is written as a positive number. The first
five kinds in the list are counted by the journal: risk per trade, trades
per week, trades per month, loss per week in R, positions open at once. The
longest hold and the least RR are shown on the page and left for the
review. *Other* takes a name of its own and is shown as written.

The counted ones make the frame, a line above the checklist of a new trade
that holds them against the playbook's own trades at that moment: trades
this week and this month against the caps, the R of the week against the
loss limit, positions open against the cap, the risk typed in the form
against its cap. A figure turns red where this trade would go past the
limit. The trade still opens; the figure is there to be seen before the
boxes are ticked.

## Notes

Anything else: the markets, the math, what is still being decided, the
rules of the prop account. A line starting with `## ` begins a section of
its own on the page; text with no heading lands under *Notes*. Nothing here
is ticked or counted.

## Review

The review lives on the page of the playbook rather than in the form, near
the end,
under the trades and before the earlier versions, one field and a dated entry
each time, with screenshots pasted under it. That is where a
block is taken apart when its count is reached: what the trades said, what
leaked, what the next version changes. One dated entry per completed
block settles the amber tab, two blocks without a review need two; then the
rules are revised in the form under a new number.

## How it comes together

**In the form of a trade.** Next to *plan* stands *playbook*. Picking one
sets the style and opens the checklist: the setups to choose from, the rules
of the chosen setup, then the filters, a box each. The trade opens with any
number of boxes ticked. The rules left unticked are recorded with the trade,
and under every empty box stands a line for why, which asks for the fact and
leaves the verdict to the review. Leaving every box empty is recorded too, as
every rule not met.

**At the close.** The management rules, the same way, apart from the entry.

**On the page of a trade.** Both lists with a tick or a cross each, the
reason given under a cross, in the version the trade was ticked against.

**In the figures.** Statistics carries *By playbook*, a row per playbook
with its setups beneath it and the trades under none last. Two shares stand
in it: *clean*, the share of ticked trades that met every rule at the entry,
and *held*, the share of closed trades that ticked the management rules and
kept every one. The reports carry the same table. The page of a playbook
adds *By setup* and *What a rule costs*: for every rule not met, how many
trades broke it and what they brought in R, against the last row, the
trades that kept every rule. Under it, the reasons given for each rule, a
line per trade. That table and those reasons count the ticked trades of the
current version; after a revision they start over, and the earlier versions
keep their own pages. The table says what a rule is worth, in R.

**Trades taken before the playbook was written.** A playbook is usually
written for a way of trading that has been going on for a while. The tool
`tools/attach_playbook.py` ties the trades of the playbook's styles, opened
on or after *counts from*, to it: first it names how many would be tied, by
account and by style, then `--apply` writes it. Those trades get the playbook
and nothing else: no checklist and no version, because nobody ticked the
rules for them and they say nothing about any rule. A trade takes the version
on the day its rules are ticked. Open each one and tick the rules from memory
if it is worth it.
