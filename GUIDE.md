# Keeping the journal

A guide for the person using it. How it is built and what the files look like:
[README.md](README.md). How to install it: [INSTALL.md](INSTALL.md).

The journal opens in a browser at **http://localhost:8778**. On Linux with
Omarchy there is also a button in the top bar and a hotkey. The server runs on
its own and survives a reboot; there is nothing to "start" by hand.

## The daily round

1. **Before the market**, a plan if the week or the day needs one: the
   **+ Plan** button.
2. **Opened a position?** Write it down at once, with the **+ Trade** button,
   pick the plan it follows and the playbook, and tick its rules.
3. **Closed it?** Close the trade too: the **Close** button in the open
   positions block or on the trade page.
4. **At the end of the day**, a card: the **+ DRC** button.
5. **At the end of the week**, a card for the week: the **+ WRC** button.
6. **At the end of a month or a quarter**, a report: the **Reports** tab.

The point of the first step: the idea is written down before the market shows
who was right. In hindsight an idea always looks tidier than it was.

## A new trade

**+ Trade** in the header. The fields:

- **account**: archived accounts are not offered.
- **pair**: the list under the field carries the same flags the journal does,
  and it opens and shuts on a click on the field. Typing filters it; a pair
  that is not in the list is simply typed in and saved with the trade, in
  capitals whatever way it was typed, so `eurusd` and `EURUSD` are one pair.
- **direction**, **style**, **entry TF**: the styles and the timeframes come
  from your own lists, edited on the Accounts tab.
- **risk, %**: the risk as a percent of the current computed balance of the
  account. What that is in money shows on the trade page once it is saved. The field starts at the risk of your last
  trade on that account and follows the account until you type a figure
  yourself; a duplicate's risk starts at the last trade of its own account.
- **entry**: date and time of entry; clicking the field opens a calendar.
- **plan**: the trading plan this trade follows, picked from the plans you have
  written. Left at "-" if the trade belongs to none.
- **playbook**: the playbook the trade is opened under, if any. Picking one
  sets the style and opens its checklist under the form; see Playbooks above.
- **execution**: the checkboxes. They come from your list too, so the formats
  you actually trade are the ones offered.

Below is the idea block: timeframe, text and screenshots. **+ idea block** adds
another one when the idea rests on several timeframes.

**Screenshots**: click inside the dashed frame and press **Ctrl+V**. Whatever is
on the clipboard goes in: a shot from TradingView, a cut of the screen. To take
a screenshot out, press the cross in its top right corner.

**Duplicate on other accounts** is for the same position taken on several
accounts, for example on the exchange and on two prop accounts. Open the block:
every live account has a row, except the one the trade itself is on. Tick the
accounts and set the risk each carries, and **Open trade** writes the trade you
filled in and a copy of it on every ticked account. They carry the same pair,
direction, style, entry, idea text and screenshots, and differ only in the
account and the risk, so each is measured against its own balance. After that
they are ordinary trades: each is closed with its own result and PnL.

**Open trade** saves it. The position counts as open until it is closed.

## Playbooks

The **Playbooks** tab holds the standing rules of a way of trading: what has
to be true before a trade is opened. A plan is written for a day and a pair;
a playbook has no date and no pair, it is the system itself, and it changes
by version rather than by the week.

The tab is drawn amber while the journal has no playbook: the rules are what
the trade form will hold the trades against, and until they are written
nothing can be held.

**+ Playbook** on the tab writes one. The form is six cards: the header, the
setups, the filters, the management, the limits and the notes. What each part is for, and how the journal uses it, is
laid out in [PLAYBOOK.md](PLAYBOOK.md).

- **name, status, version, counts from, block, styles.** The status is
  `experiment` while the sample is being built, `active` once the rules are
  trusted, `retired` when they are not offered any more; a retired playbook
  stays for the trades that carry it. *Counts from* (`since` in the file) is
  the day the tool that ties old trades starts from; it starts at today. A
  new playbook starts as an experiment at version 1.0. *Block* is how many
  trades make one review, if the rules are reviewed by blocks; the page
  shows how far the current block has come.
- **setups.** One way of entering per setup: a name, a line on what it is,
  and its rules, a row each. A rule is a few words, which is what the
  checklist in the trade form will show, and then the whole rule, if the
  words need it; the page shows both. Enter in a row adds the next one under
  it, the cross takes one away, and an empty row is simply dropped.
  **+ setup** adds another setup. A playbook with one way of entering leaves
  the name empty.
- **filters**: rules checked before every trade, whatever the setup, in the
  same fields.
- **management**: the rules of holding the position, in the same fields.
  They are ticked when the trade is closed, not when it is opened: the stop
  not moved, the position held to its target, closed by Friday. Three to
  five is a list that gets ticked.
- **limits**: a row each, **+ limit** adds one and the cross takes one
  away. A value is a plain number, the unit stands in the label, and the
  loss per week is written as a positive number. The first five kinds are
  counted above the checklist of a new trade: risk per trade, trades per
  week and per month, loss per week in R, positions open at once. The
  longest hold and the least RR are shown on the page and left for the
  review. *Other* takes a name of your own and is shown as written.
- **notes**: anything else. A line starting with `## ` begins a section of
  its own on the page: the markets, the math, what is still being decided;
  text with no heading lands under *Notes*.

The rules are numbered through the whole playbook, setups first, then the
filters, then the management. That number is what a trade will record when a rule was not met.

**Revising the rules.** Until the first trade is ticked against a version,
the rules are a draft: edit them as often as you like. Once a trade has been
through the checklist under the number, a change of the rules asks for a new
number, and the rules as they
were are kept under *Earlier versions* on the page: a trade opened under the
old number keeps the rules it was ticked against. Only the rules and the names of
the setups are held to this; the intro, the notes, the limits and the status
change freely.

The file it writes, `journal/playbooks/<id>/playbook.md`, reads by eye like
every other record:

    ---
    id: pullback
    name: Pullback
    styles:
      - swing
    status: experiment
    version: 1.0
    since: 2026-08-15
    block: 40
    ---

    What the playbook is, in a few lines.

    ## Setups

    ### A: reaction at a higher level
    A line or two on what the setup is.
    - [ ] **Level on W or D** A fractal level of the weekly or the daily chart
    - [ ] The target is at least 2R away

    ## Filters

    - [ ] More than an hour to the next high-impact release

    ## Management

    - [ ] **Stop never moved against** The stop stays where the idea dies

    ## Limits

    - risk: 1
    - max per week: 3

    ## Math

    Anything else, under any heading.

A rule is a line with a box in front, `- [ ]`; the few words go in bold and
the whole rule follows them. A playbook with one way of
entering writes its rules under `## Conditions` instead of `## Setups`. Any
other heading is kept and shown as text. Earlier versions sit next to it in
`versions/<number>.md`.

**In the form of a trade.** Next to *plan* there is *playbook*. Picking one
sets the style to the playbook's and opens its checklist under the form: the
setups to choose from, the rules of the chosen setup and the filters, a box
each with the few words of the rule; the question mark shows the whole rule.
Tick what holds. The trade opens with any number of boxes ticked, nothing is
refused, but the rules left unticked are recorded with it, and the line under
the list says how many. Under every box left empty stands a line for why,
and ticking the box folds it away: the fact, not the verdict. "Target 1.6R, took it anyway" is enough; whether it
was a good reason is a question for the review, where the reasons given
for every rule stand together. Leaving every box empty is recorded too: every rule
not met. The page of the trade then shows the rules with a tick or a cross,
and the rules of the version it was ticked against, whatever the playbook
says later.

Editing a trade shows its checklist as it was ticked. A trade tied to a
playbook later, with no checklist, says so on its page; tick the rules in
its form to record them, or leave them alone and it stays as it is.

**At the close.** The form that closes a trade shows the management rules
of its playbook under the outcome, a box each. Tick what was held; the rules
left unticked are recorded with the trade, apart from the ones of the entry,
each with its why, the same way.
The page of the trade then shows both lists, the entry and the management,
with a tick or a cross each; while the trade is open the management rules
stand there as a plain list, to be kept in mind. A closed trade edited later
keeps its ticks unless the list is touched.

**The frame.** When the playbook has limits, a line above its checklist
holds them against the playbook's own trades at that moment: trades this week and this
month against the caps, the R of the week against the loss limit, positions
open against the cap, and the risk typed in the form against its cap. A
figure turns red where this trade would go past the limit. Nothing is
refused; the figure is there to be seen before the box is ticked.

**Reviewing a block.** The page of the playbook ends with *Review*: one
field, a dated entry each time, and screenshots pasted with it stay under
that entry, the way an update is added to a plan. That is where a block is
taken apart when its count is reached: what the trades said, what leaked,
what the next version changes. Then the rules are revised in the form under
a new number. When a block has run its course and has no review yet, the
Playbooks tab turns amber, the list says *review due* and the page of the
playbook says which block is complete; a dated entry per completed block
settles it.

**Changing the status.** A playbook set to *retired* leaves the form of a
trade and drops to the end of the list, grey; its page, its trades and its
figures stay. Set it back to *active* and it is offered again. **Delete**
on the page moves the folder to `.trash`, versions and screenshots
included, and the Trash card on the Accounts tab puts it back; the trades
opened under it keep its name and their checklists either way.

**Trades already taken this way.** A playbook is usually written for a way
of trading that has been going on for a while. To count those trades under
it, run

    python3 tools/attach_playbook.py <journal root> <playbook id>

It names how many trades would be tied, by account and by style: the ones of
the playbook's styles opened on or after its *counts from* date that carry
no playbook yet. Add `--apply` to write it. These trades get the playbook
and its version, no setup and no checklist: nobody ticked the rules for
them, and they do not hold the version, so the rules stay a draft. Open each
one and fill that in if you remember.

**The figures.** The Statistics tab opens with *By playbook*: a row per
playbook with its setups beneath it, the trades taken under none last, and
a *clean* column, the share of ticked trades that met every rule. The
monthly and quarterly reports carry the same table. Next to *clean* stands
*held*, the share of closed trades that ticked the management rules and kept
every one. The page
of a playbook adds *By setup* and *What a rule costs*: for every rule that
was not met, at the entry or to the close, how many trades broke it and what
those trades brought in R, against the last row, the trades that kept every
rule. Only ticked trades of the current version take part in that table.
Under it, *Reasons given* folds out what stood behind each rule not met, in
the trader's own words, a line per trade.

## Trading plans

**+ Plan** in the header, or the **Plans** tab. A plan is written before the
market opens and holds what a trade cannot: what was supposed to happen.

- **title, pair, narrative**: a name of your own, the instrument, and what you
  expect: bullish, bearish, neutral or no trade. A decision not to trade is a
  plan as well.
- **from** and **until**: the days the plan covers. Until is left empty for a
  plan that lives one day; a plan that covers today is marked **current** in the
  list and its card is outlined on the page.
- **analysis blocks**: timeframe, text and screenshots, the same blocks as the
  idea of a trade. **+ analysis block** adds another timeframe.
- **plan**: what you will do, and what you will not. This is the part you read
  back when a trade tempts you mid-week. Under it there is a drop zone of its
  own: the levels you marked, the position you set up, Ctrl+V and they sit with
  the plan itself.

**Updates** are added from the plan page, not from the form: one line, and the
journal stamps it with the date. The plan stays as it was written and the week
is written under it. An update takes screenshots too: paste into the zone under
the field before pressing **Add**, and the pictures stay under that line, so a
week of a plan reads as it happened. Nothing else in the plan is touched when
an update is added.

**Review** is written later, in the plan form: how it went, with screenshots.

**What came of the plan.** Every trade you tied to it is listed on its page with
its result, PnL and R, and the line under the table says how many trades, the
winrate, the Σ R and the money. That is the answer a plan in a document cannot
give: whether following it was worth anything.

**Plan against fact.** For a bullish or a bearish plan the page also says how
many of its trades went with the narrative (a long under a bullish plan) and
how many against it, with the R of each pile. A plan that said "no trade"
counts every trade taken under it as against it.

## Closing a trade

The **Close trade** button. You fill in the result (Win / Lose / BE), the PnL in
dollars and the moment of the exit; below that go the screenshots of the exit and
the conclusions with their own screenshots.

The result starts on **pick one** and the form will not be sent until you choose,
so a trade cannot be closed with a result nobody picked.

The exit holds the hour as well as the date, and it matters: a trade opened later
the same day is measured against the balance this close left behind. Leave the
time at midnight and the journal takes the hour as unknown, as it does for an
entry. An exit dated before the entry is refused. A Win with a negative PnL,
or a Lose with a positive one, is saved but pointed out on the trade page:
nearly always one of the two is a slip, and Edit puts it right.

R is worked out by itself: `PnL / (risk% × the balance at the moment of entry)`.
There is nothing to recompute by hand.

## Editing and deleting

- **Edit** on the trade page changes any field, screenshots included. For a
  closed trade the result, the PnL, the moment of the exit, the exit shots and
  the conclusions are edited there as well, so a result entered wrong is fixed
  without touching the file. The folder of the trade is named after its day and
  its pair, so changing either moves the folder under a new name; a link to
  the old one stops working, the record itself is untouched.
- **Delete** sends the trade to `.trash` next to the `journal` folder. It is not
  shredded: the **Trash** card on the Accounts tab lists everything deleted,
  and **Restore** puts it back, screenshots and all. A record written again
  under the same id in the meantime is never overwritten: the one in the trash
  stays there until you sort it out by hand.

## The daily card

**+ DRC** opens today's card; if there already is one for that day, it opens
that one. The **Cards** tab lists them, the daily ones in the upper table.

- **date**: you can change it when reviewing yesterday. Changing the date moves
  the card, it does not create a second one; if the new day already has a card,
  the journal refuses rather than overwrite it, and says so.
- **process grade** and **opportunity quality**: the suggestion offers
  A / B / C / D / F, but the field is free, so write in whatever scale you use.
- **P&L** is filled in from the trades closed that day. The field is editable:
  a day can have a tally of its own that differs from the journal's sum.
- **trades assessment**: numbered lines for the trades of the day, the mark
  each one earned and how it ended, the three columns of the paper, the same
  table as the weekly card below. The trade field suggests the trades you
  closed that day; pick one, or type its pair, and the result fills in with
  what the journal knows, `Win +1.20 R`, and stays yours to change. An empty
  line is not saved.
- **A position still in the market can be graded too.** The list offers what
  the day held and did not close, as `USDJPY long, open since 01.09`. Its
  result says `open`, and it does not have to be corrected later: a line you
  picked from the list remembers which trade it is, so when the trade closes,
  in a fortnight if that is how long the swing runs, the line says what it
  made and the day it closed on, `Win +2.40 R, 18.09`. The money of the card
  is untouched by it: a period counts the trades it closed, and the R of that
  swing belongs to the week it closed in. Type your own words into the result
  and they are kept as typed, exactly as before.
- Then, laid out as on paper: focus, process, what went well, errors, then the
  best trade beside the assessment, and the overview under them.
- **best trade** is your text, and over it stands **pick a trade**, a
  drop-down of the day's trades: choose one and its name is put into the text
  where the cursor stands, spelled as the assessment spells it. The list goes
  back to empty and saves nothing of its own; the words after the name are
  yours. It offers what the assessment offers, the open positions among them,
  and is not shown on a day the journal held no trade at all.

## The weekly card

**+ WRC** opens the card of the week that is running; if there already is one,
it opens that one. They are listed under the daily ones on the **Cards** tab,
and both kinds are stored side by side in `journal/cards`.

- **week**: the calendar week, Monday to Sunday, the same week the journal
  groups the trades by. Changing it moves the card, exactly as the date moves a
  daily one, and the journal refuses to write one week over another.
- **P&L** and **trades** are filled in from the trades that week closed. Both
  are editable: the count you review by is yours, not the journal's. Under the
  count stand the week's trades in figures and colour, no words: green won,
  red lost, amber break-even, blue still in the market when the week ended.
  That is why the field can say 3 while the colours say `2 / 1 / 1`: the field
  counts what the week closed, the colours count everything it held.
- **progress** under the focus says how far the thing you are working on has
  moved this week, out of 10, and every number carries the word for what it
  means, from `1 · not moved` to `10 · done, take a new focus`. A 10 is a focus
  worked through: retire it and write the next one. The words are there so that
  the same number means the same week in January and in June. A card written
  when the scale ran to 5 keeps its number and reads as it did, but that number
  was a fifth of the way, not a tenth: change it by hand if you want the old
  weeks on the new scale.
- **trades assessment**: the same table as the daily card, for the trades of
  the week, the mark each one earned and how each ended. The trade field
  suggests the trades you closed that week, and the result fills in from the
  journal as on the daily card; an empty line is not saved. The swings the
  week held and did not close are offered here as well, with the same `open`
  and the same answer once they close: the week you carried a position is the
  week to grade how you carried it.
- Then, as on paper: the weekly process, what went well, errors, the best trade,
  what you missed, and the key lesson of the week. The **best trade** has the
  same **pick a trade** drop-down as the daily card, offering the trades of the
  week, the ones still open among them.

## Both cards on the Cards tab

The **trades** column of both tables is the same row of figures: green won,
red lost, amber break-even, blue what was still in the market when the day or
the week ended. Hover for the words. A card brought in from before the journal
held those trades has nothing to count, and shows the number written on it.

## Two small things everywhere

- **The name in the top left corner is a link home**, to the journal with its
  trades, from wherever you are.
- **Every form answers.** Save a trade, a card, a plan or an update, and the
  journal says what it did in the middle of the screen for a second, then takes
  the message away. Nothing has to be clicked.

## The front page

- **Account tiles**: the computed balance, the start balance and the difference
  in colour, in the currency of the account. The difference is what the account
  earned, so money you put in or took out is named separately and is never
  mistaken for a win or a loss. Archived accounts do not appear here. An
  account with a **daily loss limit** (see Accounts) carries one more line:
  what today has already cost, what the open trades still put at risk, and the
  limit; the tile turns amber at four fifths of it and red when it is reached.
  **The name of an account is a link**: it opens Statistics with that account
  chosen, its own equity curve and its own figures.
- **Open positions**: what is in the market right now, with the risk in money
  and a Close button.
- **Summary tiles**: the current period, the size of the selection, the
  winrates with the **EV** to the right of each, and the total R.
- **The current period** counts the trades that closed in it, the way a broker
  states a week and the cards count a day. The list under it groups by entry,
  so a trade held over a weekend stands in last week's group and in this
  week's tile.
- **The list of trades** is split into periods. The **Weeks / Months /
  Quarters** switch sits above the table on the right. The total row of a period
  holds the number of trades, WR with its EV, Σ PnL and Σ R. **A click anywhere on a row
  opens that trade**: its fields, the idea you wrote before the entry with its
  screenshots, the exit moment and the conclusions. The same goes for a row in
  the open positions block.
- **Filters** sit behind the funnel button to the left of the switch: account, pair,
  style, direction, result, a range of months. They apply both to the list and
  to the summary tiles. While a filter is on, the funnel is lit and shows how
  many fields are set; **Reset** clears them. To close the form: click away or
  press Escape.
- **CSV** next to the switch writes the list as it is filtered into a file for
  a spreadsheet: every stored field and the computed ones, R, the balance at
  entry, the risk in money, one trade per line.

## How the figures are worked out

**Account balance** = start balance + the PnL of every closed trade +
adjustments (deposits, withdrawals, fees, reconciliations). It is stored
nowhere: it is worked out afresh every time, so it cannot fall behind reality.

**R** = PnL / (risk in percent × the account balance at the moment of entry).
A trade closed earlier the same day is already in that balance, because the exit
carries its hour. If the exit was left at midnight, that is an exit whose hour is
unknown, and its PnL counts from the next day.

**Winrate** = wins / (wins + losses). Break-even trades stay out of the
denominator: such a trade ended neither way. What they cost (commission, the
spread, the opportunity spent) is visible in the sum and in the EV, where
break-evens count like everything else. Under the winrate stand three numbers:
wins in green, losses in red, break-evens in yellow.

**EV** = Σ R / the number of closed trades: what a trade brought on average,
in R. It stands to the right of every winrate. Unlike the winrate, it counts the
break-evens: a trade closed at zero still paid its commission and swap and never
comes back at exactly zero R, so leaving it out would flatter the figure. Hover
over it in a tile to see how the sum splits between wins, losses and
break-evens. The total R tile carries the same figure under the sum, and every
table of the Statistics tab and of a report has an EV column: by style, by pair,
by account, and in a report also by direction, entry timeframe and execution. A
pair gets its row, and its EV, from its first closed trade; nothing has to be
added anywhere for a new one.

**Total R** is more honest than a total in money when there is more than one
account: a dollar on a prop account and a dollar on your own are different kinds
of money, which is why the front page carries no grand total in dollars.

**Money is shown in the currency of its account.** A sum that spans accounts,
the PnL column of the list, the total of a week, carries the currency they all
share; when they do not share one, the number stands without a sign, because a
sum of two currencies has no name.

## The Statistics tab

**By playbook.** First on the tab, when any trade names a playbook: a row per
playbook with its setups beneath it, the trades under none last, with
trades, WR, Σ R, EV, money, and the *clean* and *held* shares. A row leads to
the playbook's page. The Playbooks section above says what the shares mean.

**Equity by account.** One picture per account, each on its own scale, because
the small moves of a small account would vanish next to a 100k prop. The switch
above picks a single account and applies to the tables below as well. Archived
accounts are not drawn: the account is done with and there is nothing left to
watch. Their trades stay in every figure underneath.

The dashed line across the picture is the balance the curve starts from: the
opening balance of the account, or the balance it entered the first month of
the filter with. The wash under the curve is green above that line and red
below it, so which side of the start the account is on is read before a single
number is. A hollow dot on the curve is money that moved outside a trade: a
deposit, a withdrawal, a fee. The dashed line steps with it, up at a deposit
and down at a withdrawal, so the wash stays what the trading did and taking
money out does not paint the account red. The numbers at the end of the line
are the balance now and how far it is from that line. The switch on the right
reads the curve **by date** or **by trade**, one step per closed trade, which is
how an equity curve is usually looked at: the calendar stretches a quiet month
and squeezes a busy day, and by trade every trade takes the same room.

The line is drawn softly, but it never invents a high or a low: the curve is
bent only between the points it has. A peak on the picture is a peak that
happened. Trades closed on the same day are laid out across that day in the
order they were closed, because a journal records the date of a close and not
the hour, and stacking them on one x would make a vertical wall out of an
ordinary day.

With a **from month** filter on, the curve starts at the balance the account
entered that month with: everything before it is folded into the first point.
With a filter by style, pair or direction, only the chosen trades move the line
from there, so the picture says what those trades alone did to the account.

**Streaks.** Under the rings: the longest run of wins, the longest run of
losses and the run the selection is on now, all in the order the trades closed.

**R distribution.** Two rings: the losses on the left, the wins on the right,
each cut by the size of R. Pointing at a slice, or at its line in the list
beside the ring, lights up both and dims the rest: five steps of one colour
cannot be told apart by eye, and they do not have to be. In the middle of a ring stands the number of trades
in it and their total R; beside it every slice is written out with its count,
its share and its R. The further a bucket is from zero, the brighter the slice.
Break-even trades are in neither ring, and their number is named above.

**The losses are cut where a stop lands.** A trade taken to the stop comes back
a little worse than -1R, because commission and swap are paid on top of it, so
the bucket **-1…-1.2** means the stop as designed. Anything past -1.2R is a
bucket of its own: that loss was not the stop but too much size, and it is the
one number that says the risk was overrun. The two buckets above them are losses
that never reached the stop: **0…-0.5** and **-0.5…-1**. A bucket reads from
zero outwards and its far edge belongs to the next one, so exactly -1R is the
stop, not the bucket that stops short of it.

Read together the two rings answer the question a trader actually asks: are the
losses one size, and do the wins reach far enough to pay for them. The rings in
a monthly or quarterly report are cut the same way, on the trades of that period.

**By style, by pair, by account.** Three tables under the rings, one row per
value: the number of trades, the WR, Σ R, the EV and the result in money. A row
appears as soon as a value has a closed trade in the selection, so a new pair
is counted from its first trade.

## Money in and out

Money moves for reasons other than trades: you top an account up, you take a
payout, the broker charges a fee. All of that lives on the **Accounts** tab, in
the **Money and corrections** card. Both forms are folded away behind a line you
click: they are needed rarely, and the balances above are what the page is for.

Deposits, withdrawals and fees are under **Money in and out**; a correction has
its own fold below, with its own list. They are apart because one is money you
moved and the other is a difference you found.

Pick the account, pick what happened (**deposit**, **withdrawal** or **fee**),
type the amount as a plain positive number, set the date and add a comment.
What the amount does to the balance is decided by what you picked, so a payout
cannot be typed in as a plus by accident.

**Withdrawals are counted separately.** The total taken off an account stands in
the **cashed out** column of the table above, and on the front page the tile
says it in words. That is the point of counting them: money you paid yourself is
not a loss, and without that figure an account that pays out looks worse than it
was. The line on the tile adds up exactly:

    start balance + what the account earned + added - cashed out = balance

Every movement is listed under the form, newest first, and **Delete** sends one
to `.trash` like any other record. Balances are recomputed from what is left.

**Correcting a balance.** When the broker shows a different number, do not touch
the start balance and do not edit old trades. Use the **Correct a balance** card:
type the balance the broker really shows, and the journal writes the difference
down as a correction with your comment. The gap becomes a record with a date,
which is what keeps the history honest. If there is nothing to correct, the
journal says so and writes nothing.

## Accounts and pairs

The **Accounts** tab.

- **Start balance** is not "what it once was" but the point the journal counts
  from. Opening an account today, put in today's real balance.
- **Currency** is shown next to every sum of the account: a sign for the usual
  ones ($, €, £, ¥), the code for the rest.
- **Daily loss limit** is the prop rule: the most a day may lose before the firm
  closes the account. Type it in the row of the account and press **Set**;
  empty means the account has no such rule. With one set, the tile on the front
  page adds up what today has already cost in closed trades and what the open
  ones still put at risk at their stops, and changes colour as the limit comes
  near.
- **Archive** keeps the account in the history and the statistics but stops
  offering it when a trade is opened. An account with trades cannot be deleted,
  only archived; one without them is deleted into `.trash` like everything else.
- **Trash** lists everything deleted, newest first, with a **Restore** button.
  The card is folded, the count on it; a click opens the list.
- **Pairs** are the suggestions for the form. Taking a pair out of the list does
  not touch the trades already recorded with it. Every pair is shown with its
  flags: two round ones for a currency pair, one for an index, a lettered coin
  for gold, silver or a crypto coin. A symbol the journal does not recognise
  gets a plain coin with its first letters, and is written out in full as
  before, so nothing depends on the icon.

- **The trade form** holds the other three lists: the trading styles, the
  timeframes of the entry TF field and the execution checkboxes. Each opens on a
  click, takes a new word in the field and removes one with the button next to
  it. A new word goes to the end of its list, so the timeframes stay in the
  order you trade them rather than in the alphabet.

  Removing a word only stops the form offering it. The trades that carry it keep
  it: it stays in the filters, the statistics and the reports, it is still shown
  when that trade is edited, and the list on the Accounts tab shows it below the
  others, saying how many trades hold it, with an **Add** button to offer it
  again. That is how a style you stopped trading is retired without touching a
  single record.

  Every style you keep in the list gets a winrate tile of its own on the journal
  page, as soon as it has trades. **Winrate overall** counts every trade of the
  selection, whatever its style, retired or not.

**The balance does not match the real one?** Do not change the start balance and
do not edit old trades: use **Correct a balance** above. The gap is written down
as a record of its own in `journal/adjustments/`, with the kind
`reconciliation`, `fee`, `deposit` or `withdrawal` and a comment saying where
the difference came from. That way the history stays honest.

## Reports

The **Reports** tab is a shelf: every quarter and month since your first closed
trade, newest first, each with the figures the journal holds for it now, whether
a report was built for it or not. Trades, then won / lost / break-even and, on
the running period, the positions open now in blue, WR, Σ R, EV, money, and
the daily cards written against the days traded. A period with trades and no
report has a **Build** button in its row, blue on the one that is due, the
newest finished period with trades and no report. A period with a report is a
link to it, with the day its file was built and a blue dot once conclusions
are written; *rebuild* refreshes the file. The month and the quarter still
running are marked so.

**A report counts the trades that closed in the period**, the way a broker
states a month and the cards count a day. The list of trades groups by entry,
so a row of a report and the list it opens can differ by a trade that ran
across the boundary.

**What is in a report.** The header leads to the report of the period before
and the one after, and for a month to its quarter, when those reports exist.
The page opens on the figures a review asks for first, one tile each, the
period before in grey under the first three: the result in R with the money
under it; the winrate with the EV and the trades won, lost, break-even by
colour, the positions open now in blue while the period runs; the **deepest
fall from a high**, how far
the period went below its own best point, in R, because a month can end in
plus and still have been survived rather than traded; the **mistakes**; the
**process**, the daily cards written against the days traded and their
grades; and the best and the worst trade by R, each a link to the trade.

**Mistakes** are what the journal itself recorded as one: a rule ticked as not
met at the entry or at the close, or a loss of -1.2 R and worse, which is past
the stop and therefore size. A trade that did both counts once; a trade never
ticked counts neither way, and the tile says how many trades under a playbook
were never ticked. The
count is plain ink and only the R of those trades is coloured: a report does
not grade a month. The **Rules** card names every rule the trades ticked
against the current version of their playbook did not meet, how many trades
broke it and what they brought, the costliest first, against the
last row, the trades that kept every rule; the losses past the stop are listed
under it as **Past the stop**, each a link to the trade. The card stands
whenever a trade of the period names a playbook or a loss went past the stop.

**Trade by trade** is every closed trade of the period as one bar, in the
order of the exits: a win stands up in green, a loss hangs down in red, a
break-even is an amber tick on the zero line, and a thin line marks where a new
week begins, or a new month in a quarter. The dashed line is the stop, -1 R. A
bar that reaches past it means the size was too large, and it shows without a
label.
Hover a bar for the trade, click it to open it. Beside it stand **the rings**,
the R distribution of the period, the same as on the Statistics tab.

Then **By playbook** with its setups beneath, when any trade names one;
**Process**, with the daily cards against the days traded, the weekly cards
of the period, the grades, the D and F days and the errors you wrote on the
cards, each a link to its card; and your **Conclusions**: an open field until they are
written, then your text with an **Edit** fold under it. Saving writes the
figures and the text into `journal/reports/<period>.md`, an ordinary markdown
file you can read anywhere. The text is never overwritten by a rebuild. The
page itself is always the journal as it is now, so there is nothing to
recalculate; the file catches up when you save or press *rebuild* on the shelf.

After the story come the tables: for a quarter its months, each a link to its
own report when one exists; then by pair, by style, the accounts with the
balance of each before and after the period, by direction, by entry timeframe
and by execution format, every row with its trades, WR, Σ R, EV and money, Σ R
the one coloured column.

**Every row leads to its trades.** Click a pair, an account, a style or a
direction in the report tables and the journal opens filtered to it, over the
months of that report. That is how a row like "XAU, 5 trades, -4.56 R" turns
back into the five trades it was counted from, with the idea you wrote before
each entry. The best and the worst trade lead straight to the trade itself, a
playbook row to the playbook's page, and a bar of the tape to its trade.

## Search

The **Search** tab. A word or a phrase is looked for in everything you have
written: the ideas and conclusions of trades, their notes, the analysis, plan,
updates and review of every plan, and every field of every card, daily and
weekly alike. Case does not
matter. Every hit is a link to the record, with the matching words shown in
the text around them. It is the way to find the trade where you wrote "moved
the stop too early" three months ago.

## Where the data lives

Everything is in the `journal/` folder: ordinary text files and pictures.

    journal/trades/2026-08-30-01-eurusd/trade.md
    journal/trades/2026-08-30-01-eurusd/shots/*.png
    journal/cards/2026-08-30.md
    journal/cards/2026-W36.md
    journal/plans/2026-08-31-eurusd/plan.md
    journal/plans/2026-08-31-eurusd/shots/*.png
    journal/playbooks/pullback/playbook.md
    journal/playbooks/pullback/versions/1.0.md
    journal/playbooks/pullback/shots/*.png
    journal/accounts/*.md
    journal/adjustments/*.md
    journal/reports/2026-08.md

If `PLAINBOOK_ROOT` is set, that folder is somewhere else. See INSTALL.md.

The files open in any text editor and read by eye. No database, no format of its
own: if the program breaks tomorrow, the records are still yours in the same
shape.

Two service folders sit next to the journal: `.trash` (what was deleted) and
`.drafts` (screenshots from forms that were never submitted, swept after a day).

**A backup** is a copy of the `journal/` folder. If it is under git the history
is already kept; a copy on an external drive is still not a waste.

## When something goes wrong

- **The page does not open.** The server is not running. On Linux:
  `systemctl --user restart plainbook`. Otherwise run `python3 -m plainbook.server`
  in the program folder.
- **A screenshot did not paste.** The journal says so outright. Check that the
  clipboard holds a picture and not a file or a link.
- **A yellow box at the top of every page says a record could not be read.**
  A file was edited by hand and something in it does not parse: a date written
  the wrong way round, a letter in a number, a header without its closing
  line. The box names the file and the reason; everything else keeps working
  and the figures simply leave that record out until it is fixed. From the
  terminal, `python3 tools/check_journal.py` (with the data folder as an
  argument if it is not `./journal`) prints the same list.
- **Deleted the wrong thing.** The Trash card on the Accounts tab, **Restore**.
- **Port 8778 is taken.** Set another one through `PLAINBOOK_PORT`.
