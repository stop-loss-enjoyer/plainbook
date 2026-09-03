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
   and pick the plan it follows.
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
  account. What that is in money shows on the trade page once it is saved.
- **entry**: date and time of entry; clicking the field opens a calendar.
- **plan**: the trading plan this trade follows, picked from the plans you have
  written. Left at "-" if the trade belongs to none.
- **execution**: the checkboxes. They come from your list too, so the formats
  you actually trade are the ones offered.

Below is the idea block: timeframe, text and screenshots. **+ idea block** adds
another one when the idea rests on several timeframes.

**Screenshots**: click inside the dashed frame and press **Ctrl+V**. Whatever is
on the clipboard goes in: a shot from TradingView, a cut of the screen. To take
a screenshot out, press the cross in its top right corner.

**Duplicate on another account** is for the same position taken twice, for
example on the exchange and on a prop account. Open the block, pick the second
account and the risk it carries there, and **Open trade** writes two trades: the
one you filled in, and a copy of it on that account. They carry the same pair,
direction, style, entry, idea text and screenshots, and differ only in the
account and the risk, so each is measured against its own balance. After that
they are two ordinary trades: each is closed with its own result and PnL.

**Open trade** saves it. The position counts as open until it is closed.

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
entry. An exit dated before the entry is refused.

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
- Then: focus, process, what went well, errors, best trade, overview.

## The weekly card

**+ WRC** opens the card of the week that is running; if there already is one,
it opens that one. They are listed under the daily ones on the **Cards** tab,
and both kinds are stored side by side in `journal/cards`.

- **week**: the calendar week, Monday to Sunday, the same week the journal
  groups the trades by. Changing it moves the card, exactly as the date moves a
  daily one, and the journal refuses to write one week over another.
- **P&L** and **trades** are filled in from the trades that week closed. Both
  are editable: the count you review by is yours, not the journal's.
- **progress** under the focus is the 1 to 5 of the paper card: how far the
  thing you are working on has moved.
- **trades assessment**: five lines for the trades of the week and the mark each
  one earned. The field suggests the pairs you closed that week, and an empty
  line is not saved.
- Then, as on paper: the weekly process, what went well, errors, the best trade,
  what you missed, and the key lesson of the week.

## The front page

- **Account tiles**: the computed balance, the start balance and the difference
  in colour, in the currency of the account. The difference is what the account
  earned, so money you put in or took out is named separately and is never
  mistaken for a win or a loss. Archived accounts do not appear here. An
  account with a **daily loss limit** (see Accounts) carries one more line:
  what today has already cost, what the open trades still put at risk, and the
  limit; the tile turns amber at four fifths of it and red when it is reached.
- **Open positions**: what is in the market right now, with the risk in money
  and a Close button.
- **Summary tiles**: the current period, the size of the selection, the
  winrates, the total R and the **streak**: the run the selection is on now,
  with the longest runs of wins and of losses under it. Runs are counted in
  the order the trades closed; a break-even neither extends one nor breaks it.
- **The list of trades** is split into periods. The **Weeks / Months /
  Quarters** switch sits above the table on the right. The total row of a period
  holds the number of trades, WR, Σ PnL and Σ R. **A click anywhere on a row
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
spread, the opportunity spent) is visible in the sum and the average R, where
break-evens count like everything else. Under the winrate stand three numbers:
wins in green, losses in red, break-evens in yellow.

**Total R** is more honest than a total in money when there is more than one
account: a dollar on a prop account and a dollar on your own are different kinds
of money, which is why the front page carries no grand total in dollars.

**Money is shown in the currency of its account.** A sum that spans accounts,
the PnL column of the list, the total of a week, carries the currency they all
share; when they do not share one, the number stands without a sign, because a
sum of two currencies has no name.

## The Statistics tab

**Equity by account.** One picture per account, each on its own scale, because
the small moves of a small account would vanish next to a 100k prop. The switch
above picks a single account and applies to the tables below as well. Archived
accounts are not drawn: the account is done with and there is nothing left to
watch. Their trades stay in every figure underneath.

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

The **Reports** tab: pick a month or a quarter and press **Build**. The header
has no button for it; building a report belongs on the tab that shows them. A report is
an ordinary file in `journal/reports/`. Building it again recomputes the figures
and **never overwrites your conclusions**, so you can write them right in the
report.

**What is in a report.** The summary, with the same figures for the period
before it in the next column, so every number is read against something. Under
it the period cut by style, by pair, by account, by direction, by entry
timeframe and by execution format; the balance of each account before and after;
the best and the worst trade by R; and the process, meaning how many daily cards
you wrote for the days you traded and what grades you gave them. In the summary
there is one figure the tabs do not show: **deepest fall from a high**, how far
the period went below its own best point, in R. A month can end in plus and
still have been survived rather than traded.

**The rings** stand right under the summary, before the tables: the R
distribution, the same as on the Statistics tab but counted on this period
alone. The tables are the numbers frozen when the report was last built; the
rings are drawn from the journal as it is now, so if you edited a trade of that
period, press **Recalculate**.

**Every row leads to its trades.** Click a pair, an account, a style or a
direction in the report tables and the journal opens filtered to it, over the
months of that report. That is how a row like "XAU, 5 trades, -4.56 R" turns
back into the five trades it was counted from, with the idea you wrote before
each entry. The best and the worst trade lead straight to the trade itself.

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
