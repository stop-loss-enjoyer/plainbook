# Keeping the journal

A guide for the person using it. How it is built and what the files look like:
[README.md](README.md). How to install it: [INSTALL.md](INSTALL.md).

The journal opens in a browser at **http://localhost:8778**. On Linux with
Omarchy there is also a button in the top bar and a hotkey. The server runs on
its own and survives a reboot; there is nothing to "start" by hand.

## The daily round

1. **Opened a position?** Write it down at once, with the **+ Trade** button.
2. **Closed it?** Close the trade too: the **Close** button in the open
   positions block or on the trade page.
3. **At the end of the day**, a card: the **+ Card** button.
4. **At the end of a month or a quarter**, a report: the **Reports** tab.

The point of the first step: the idea is written down before the market shows
who was right. In hindsight an idea always looks tidier than it was.

## A new trade

**+ Trade** in the header. The fields:

- **account**: archived accounts are not offered.
- **pair**: pick one from the suggestions or type a new one.
- **direction**, **style**, **entry TF**.
- **risk, %**: the risk as a percent of the current computed balance of the
  account. What that is in money shows on the trade page once it is saved.
- **entry**: date and time of entry; clicking the field opens a calendar.
- **execution**: the checkboxes: Market Entry, IDM, SNR, FVG.

Below is the idea block: timeframe, text and screenshots. **+ idea block** adds
another one when the idea rests on several timeframes.

**Screenshots**: click inside the dashed frame and press **Ctrl+V**. Whatever is
on the clipboard goes in: a shot from TradingView, a cut of the screen. To take
a screenshot out, press the cross in its top right corner.

**Open trade** saves it. The position counts as open until it is closed.

## Closing a trade

The **Close trade** button. You fill in the result (Win / Lose / BE), the PnL in
dollars and the exit date; below that go the screenshots of the exit and the
conclusions with their own screenshots.

R is worked out by itself: `PnL / (risk% × the balance at the moment of entry)`.
There is nothing to recompute by hand.

## Editing and deleting

- **Edit** on the trade page changes any field, screenshots included. For a
  closed trade the exit and the conclusions are edited there as well.
- **Delete** sends the trade to `.trash` next to the `journal` folder. It is not
  shredded: if you deleted the wrong one, move the folder back into
  `journal/trades/` with a file manager.

## The daily card

**+ Card** opens today's card; if there already is one for that day, it opens
that one. The **Cards** tab lists them all.

- **date**: you can change it when reviewing yesterday. Changing the date moves
  the card, it does not create a second one.
- **process grade** and **opportunity quality**: the suggestion offers
  A / B / C / D / F, but the field is free, so write in whatever scale you use.
- **P&L** is filled in from the trades closed that day. The field is editable:
  a day can have a tally of its own that differs from the journal's sum.
- Then: focus, process, what went well, errors, best trade, overview.

## The front page

- **Account tiles**: the computed balance, the start balance and the difference
  in colour. Archived accounts do not appear here.
- **Open positions**: what is in the market right now, with the risk in money
  and a Close button.
- **Summary tiles**: the current period, the size of the selection, the
  winrates and the total R.
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

## How the figures are worked out

**Account balance** = start balance + the PnL of every closed trade +
adjustments (deposits, withdrawals, fees, reconciliations). It is stored
nowhere: it is worked out afresh every time, so it cannot fall behind reality.

**R** = PnL / (risk in percent × the account balance at the moment of entry).
The balance is taken as of the entry day: a trade closed today does not affect
today's entry.

**Winrate** = wins / (wins + losses). Break-even trades stay out of the
denominator: such a trade ended neither way. What they cost (commission, the
spread, the opportunity spent) is visible in the sum and the average R, where
break-evens count like everything else. Under the winrate stand three numbers:
wins in green, losses in red, break-evens in yellow.

**Total R** is more honest than a total in money when there is more than one
account: a dollar on a prop account and a dollar on your own are different kinds
of money, which is why the front page carries no grand total in dollars.

## Accounts and pairs

The **Accounts** tab.

- **Start balance** is not "what it once was" but the point the journal counts
  from. Opening an account today, put in today's real balance.
- **Archive** keeps the account in the history and the statistics but stops
  offering it when a trade is opened. An account with trades cannot be deleted,
  only archived.
- **Pairs** are the suggestions for the form. Taking a pair out of the list does
  not touch the trades already recorded with it. Every pair is shown with its
  flags: two round ones for a currency pair, one for an index, a lettered coin
  for gold, silver or a crypto coin. A symbol the journal does not recognise
  gets a plain coin with its first letters, and is written out in full as
  before, so nothing depends on the icon.

**The balance does not match the real one?** Do not change the start balance and
do not edit old trades. The gap is written down as an adjustment: a file in
`journal/adjustments/` with the kind `reconciliation`, `fee`, `deposit` or
`withdrawal` and a comment saying where the difference came from. That way the
history stays honest.

## Reports

The **Reports** tab: pick a month or a quarter and press **Build**. A report is
an ordinary file in `journal/reports/`. Building it again recomputes the figures
and **never overwrites your conclusions**, so you can write them right in the
report.

## Where the data lives

Everything is in the `journal/` folder: ordinary text files and pictures.

    journal/trades/2026-08-30-01-eurusd/trade.md
    journal/trades/2026-08-30-01-eurusd/shots/*.png
    journal/cards/2026-08-30.md
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
- **Deleted the wrong thing.** Look in `.trash`.
- **Port 8778 is taken.** Set another one through `PLAINBOOK_PORT`.
