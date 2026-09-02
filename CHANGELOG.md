# Changelog

What changed and why. Newest first.

## v1.4.1, 02.09.2026

- **The result of a trade is picked, not defaulted.** The menu in the closing
  form had no empty option, so the browser kept Win selected on its own and a
  trade closed without a glance at the field was recorded as a win whatever the
  PnL said. The menu now starts on "pick one" and the trade does not close until
  Win, Lose or BE is chosen.

- **The result, the PnL and the exit date are edited like any other field.** They
  sit in the Edit form of a closed trade, above the exit screenshots and the
  conclusions. Before, a result entered wrong stayed wrong: the only form that
  asked for it was the one that closed the trade.

## v1.4, 01.09.2026

The plan a trade came from, a trade written once for two accounts, three lists
that belong to you, and reports that say more than the numbers of the period.

### Trading plans

- **A plan is a record of its own.** The **Plans** tab and the **+ Plan** button
  in the header write what stood before the trade: the analysis by timeframe
  with its screenshots, what you will do and what you will not, the dates the
  plan covers and the narrative you expect. A plan that covers today is marked
  current.

- **A trade is tied to its plan** by a menu in the trade form, and the plan page
  then lists every trade that came out of it with its result, PnL and R, and
  sums them up. A plan in a document cannot say whether following it was worth
  anything; this one can.

- **Updates are added from the plan page** in one line, stamped with the date,
  so the plan stays as it was written and the week is written under it. The
  review is written later in the form, with screenshots of its own.

### Entering a trade

- **A trade can be opened on two accounts at once.** The new trade form has a
  **Duplicate on another account** block: pick the second account and the risk
  it takes there, and opening the trade writes two, with the same pair,
  direction, style, entry, idea and screenshots. The same position taken on the
  exchange and on a prop account used to mean filling the form twice and pasting
  every screenshot again.

### Your own words

- **The trading styles, the timeframes and the execution formats are your own
  lists.** They used to be written into the program: three styles, four
  timeframes, four formats, and a change meant editing the code. The Accounts
  tab now has a **The trade form** card where each list takes a new word and
  gives one back. A new word goes to the end of its list, so the timeframes stay
  in the order you trade them.

- **Removing a word only stops it being offered.** The trades that carry it keep
  it: it stays in the filters, the statistics and the reports, it is still drawn
  in the form of such a trade, and the list shows it below the others with the
  number of trades holding it and an **Add** button, so a style you retired can
  come back. That is how a legacy style is put aside without touching a record.
  The lists live in `journal/vocabulary.md`, next to the pairs.

- **A winrate tile per style.** The journal page used to have a tile for EMT and
  one for EMT prop, because those were written into the program. Now every style
  in your list gets one as soon as it has trades, and **winrate overall** counts
  the styles the list holds.

### Statistics

- **The losses are cut where a stop actually lands.** The ring used to end with
  "-1R and worse", which put the stop you designed and a position twice too big
  in the same slice. A trade taken to the stop comes back a little worse than
  -1R, because commission and swap are paid on top of it, so **-1…-1.2** is now
  one bucket: the stop as it was meant to be. Everything past -1.2R stands
  apart, and that slice is the answer to whether the risk was overrun. Exactly
  -1R counts as the stop, not as a loss that stopped short of it. The reports
  draw the same rings, so they are cut the same way.

### Reports

- **Building a report moved to the Reports tab.** The header button is gone; the
  form that builds one has always been on the tab, and the header is for what is
  written before the market rather than after it. Its place is taken by
  **+ Plan**.

- **The rings are in the report.** A monthly or quarterly report draws the R
  distribution, the same rings the Statistics tab has, counted on that period
  alone. They stand right under the summary, where the first figures of the
  period are, and before the tables.

- **The period before it, in a second column.** A winrate or a Σ R is seen
  moving rather than standing alone.

- **The deepest fall from a high**, in R: how far the period went below its own
  best point. A month can end in plus and still have been survived rather than
  traded.

- **Three more slices**: by direction, by entry timeframe and by execution
  format, which says which setups paid. A trade counts in every execution format
  it carries, so that table holds more trades than the period has.

- **The best and the worst trade** of the period by R, each a link to the trade
  itself.

- **The process**: how many daily cards were written for the days that had
  trades, and what grades they carry. A report is about the result; the cards
  are about how it was traded.

## v1.3, 01.09.2026

Money that moves outside trades, and charts that can be read.

### Money in and out

- **Deposits, withdrawals and fees are written down in a form**, on the Accounts
  tab, where before it meant writing a file by hand. The amount is typed as a
  plain positive number and the sign belongs to what you picked, so a payout
  cannot be entered as a plus by accident. Every record can be deleted, and goes
  to `.trash` like everything else.

- **Cashouts are counted.** The money taken off an account has a column of its
  own in the accounts table, and the front page tile names it. Without that
  figure a payout reads as a loss: the tile used to show the balance minus the
  start balance, which counts your own money leaving the account against you.
  The tile now shows what the account earned, and says separately what was added
  and what was cashed out. The line adds up: start + earned + added - cashed out
  is the balance.

- **A balance is corrected by typing the real one.** You put in the number the
  broker shows and the journal writes the difference down as a correction with
  your comment. The start balance and the trades are never touched, which is the
  rule this journal has always kept; up to now it just had no button.

- **Both forms are folded away** behind a line you click, and corrections keep a
  list of their own. A correction is a difference you found, not money you
  moved, and the two lists had no business being one.

### The charts

- **The R distribution is two rings**, losses on the left and wins on the right,
  each cut by the size of R, with the count, the share and the R of every bucket
  written out beside the ring. The buckets are coarse at the tails on purpose: a
  ring reads at a glance only up to about six slices, and the difference between
  +3R and +4R matters less than the one between a small win and a big one.
  Break-even trades are in neither ring and are counted above them. A slice and
  its line in the list light each other up when pointed at, and the rest dims:
  five steps of one colour are not meant to be told apart by eye. The histogram
  the rings replace is gone.

- **The equity line is drawn softly.** Straight segments between every close made
  the curve read as a saw, sharper than the data was. It is bent through the
  points now, with a wash underneath instead of a second line. The bend is
  monotone, the one kind that cannot overshoot a point, so no peak is invented.
  There is a test that holds it to that.

- **Closes of one day no longer stack on one point.** A journal records the date
  of a close, not the hour, so several trades closed on the same day stood on the
  same x and the line between them was a vertical wall no curve could be bent
  through. They are laid out across their day now, in the order they were closed.
  The balances and the day are untouched; only the hour, which was never
  recorded, is made up, and a day on the chart is a few pixels wide.

- **Archived accounts are off the statistics charts**, as they are off the front
  page: the account is done with, there is nothing left to watch on its curve.
  Their trades stay in every figure underneath, and picking one by hand in the
  filter still draws it.

### Reports

- **A row of a report opens the trades behind it.** A pair, an account or a style
  in the report tables is a link into the journal, filtered to that value over the
  months of the report. A figure you do not believe is now two clicks from the
  trades it was counted from. The tables also grew a proper head row, which is
  what stopped "account" from being read as the name of an account.

- **The conclusions field opens empty.** A freshly built report used to put
  "(empty, write it in the browser)" into the file, and the form loaded it as text
  you had to delete before writing your own. The section is left empty now, the
  field carries a placeholder instead, and a report built earlier with that line
  inside opens empty as well.

### Entering a trade

- **The pair field has a list of its own**, with the same flags the rest of the
  journal draws. The list the browser drew could not carry them, and it would not
  close on a second click on the field. This one filters as you type, walks on
  the arrow keys, and closes when the field is clicked again. A pair that is not
  in the list is still just typed in.

## v1.2.1, 01.09.2026

- **A trade opens from anywhere on its row.** In the list of trades and in the
  open positions block the whole row is now a link to the trade: its fields, the
  idea written before the entry with its screenshots, the exit moment and the
  conclusions. Before, only the date carried the link, which did not look like
  one, so the page that holds the reasoning was hard to reach.

## v1.2, 31.08.2026

- **Trading pairs carry their flags.** EURUSD is now drawn the way a terminal
  draws it: two round flags, the base currency behind the quote one. They are in
  the journal table, among the open positions, on the trade page, in the
  statistics by pair, in the built reports and in the pair list on the Accounts
  tab. Metals and coins, which have no country, get a lettered face instead (Au,
  Ag, ₿); an index gets the flag of its market; a symbol the journal does not
  know still gets a coin, with its first letters on a colour of its own. The
  flags are drawn in the code rather than downloaded, so the journal stays
  offline.

- **No long dashes anywhere.** Every text in the project now uses a comma, a
  colon or a full stop where a long dash used to stand, and an empty value on a
  page is a plain hyphen. `tools/check_public.py` fires on the character, so the
  rule holds for whatever is written next.

- **An invented journal for screenshots**, `tools/demo_journal.py`: made-up
  accounts, trades and a card, filled into a scratch folder so the pictures in
  README.md can be retaken from the real interface without anyone's records
  going near a screenshot. The three in `docs/` were retaken with it.

## v1.1, 30.08.2026

**The project is named Plainbook.** Plain text, plainly kept: the name says what
the storage is, and the storage is the reason the journal is private, fast and
workable by an agent. The package is `plainbook`, the server runs as
`python3 -m plainbook.server`, and the environment variables are
`PLAINBOOK_PORT` and `PLAINBOOK_ROOT`.

- **A guide for agents**, `AGENTS.md`: the map of the code, the invariants that
  must not be broken and why, recipes for the usual tasks, how to verify a
  change, and the traps that have already bitten this project. `CLAUDE.md`
  points at it.
- **`tools/check_public.py`** refuses to let records, private paths or foreign
  ids into the repository. It runs as a pre-push hook and in CI.

Everything is in English now: the interface, the code, the comments and the
files themselves. The journal used to keep its records under header keys and
folder names in the author's own language; they read `trades/`, `account:` and
`## Idea` now. Two languages in one project were one too many.

- **Records and program live apart.** `PLAINBOOK_ROOT` points the journal at a data
  folder of its own, so the code can go into a public repository while the
  records stay private in a repository that is never pushed anywhere.
- **A one-off migration** converted the journal that was written in the old
  format: folder and file names, header keys, the closed vocabularies (style,
  adjustment kind) and section headings. Everything written by hand (idea
  texts, conclusions, notes, card sections) was left untouched. The script was
  run on a copy first and every computed figure compared before and after; it
  lives with the records it converted, not here.
- Style values are now the words the interface shows: `swing`, `EMT`,
  `EMT prop`, `intraday`. The display-name mapping went away with them.

## v1.0, 30.08.2026

The first whole version. The journal closes the daily round: write the trade
down at entry → close it with a result and conclusions → review the day on a
card → look at the statistics → build a report for the month or the quarter.

### Added

- **The daily card.** The **+ Card** button in the header opens today's card,
  the **Cards** tab lists the earlier ones. The fields and their order follow
  the paper Daily Report Card: date, process grade, P&L, opportunity quality,
  then focus, process, what went well, errors, best trade, overview. The P&L is
  filled in from the trades closed that day, but the field is editable.
- **The list is grouped by trading weeks.** The total row of a week holds the
  number of trades, WR, Σ PnL and Σ R; a plus in green, a minus in red. The
  **Weeks / Months / Quarters** switch changes the grouping without dropping the
  filters. The first tile above shows the total of the current period.
- **Filters behind a funnel button** in the head of the list: the list matters on
  the front page, not the form. The button is lit and carries the number of
  filters that are on, because with the form out of sight it would otherwise be a
  mystery why there are so few trades. It closes on a click away or on Escape,
  and the popover is as wide as the list, so it fits at any window width.
- **Removing screenshots.** A cross on every thumbnail in a form, on one just
  pasted and on one saved long ago.
- **Deleting trades and cards.** The `Delete` button; the trade folder (or the
  card file) moves to `.trash` rather than being shredded, because a mis-click should
  not cost a record.
- **A strict dark theme.** A near-black ground, one blue accent, muted green and
  red for money only, figures in a monospace with tabular digits, a sticky page
  header and table head. The browser's own date picker and drop-downs are dark
  as well.
- **Winrate counts without break-evens**: wins against wins and losses. A trade
  closed at zero was neither won nor lost, and diluting the hit rate with it is
  dishonest. What break-evens cost is visible in the sum and the average R,
  where they count like everything else. Under the winrate stand three numbers:
  wins in green, losses in red, break-evens in yellow.

### Fixed

- **A pasted screenshot went nowhere**: the paste handler read the form token at
  the top of the script, while the token was set by a script further down the
  page. The request carried `token=undefined`, the server answered 400 and the
  browser said "Screenshot was not saved". The token is now read when the
  request is sent.
- **Editing a closed trade wiped its exit screenshots.** The form did not show
  them, and saving rewrote the shots folder from the form, that is, from
  nothing. Editing a closed trade now shows the exit and the conclusions too.
- **Saving a card with an empty P&L crashed the server.** An empty key in the
  header (`pnl $:` with no value) parses into an empty LIST rather than an empty
  string: reading it died on `float('[]')` and the browser showed
  `ERR_EMPTY_RESPONSE`. Empty values are no longer written into a header, and
  reading tolerates them in files already saved. The same guard covers empty
  trade fields, which would have shown up as "[]".
- **The bar button opened a folder instead of the journal.** The toggle looked
  the window up by the title `^Plainbook` as well, and that is the title of
  a file manager window opened on the project folder and of a terminal sitting
  in that directory. The window is now found by the web app's class only.
- **The journal folders are created when the server starts**, not when the first
  record is written. Otherwise a section only appeared on first use and you
  could not see where your records would land.
- **The weekly total broke onto two lines** and stayed grey: the numeric columns
  had no wrapping guard, and the colour class on a cell lost to the group row rule.
- **Abandoned drafts piled up forever**: screenshots pasted into a form that was
  never submitted were never cleaned. Folders older than a day are swept when a
  new form is handed out.
- A size limit on a pasted image (32 MB), a check on the trade id in the `/shot`
  URL, unused imports removed.

### The base (29.08)

- A trade is a folder with `trade.md` and `shots/` beside it; all of it markdown
  with a header readable by eye, no database.
- Two steps: opening a position → closing it with a result, PnL and conclusions.
- Balances are computed: start + Σ PnL of closed trades + Σ adjustments.
  R = PnL / (risk% × the account balance **at the moment of entry**), not
  against a fixed number that made 1% look like the same money forever.
- Screenshots pasted into the form with Ctrl+V.
- Statistics: an equity curve per account, the R distribution, slices by style,
  pair and account.
- Monthly and quarterly reports: the figures are recomputed on a button, the
  owner's conclusions are never overwritten.
- Managing accounts and pairs, archived accounts.
- Desktop: a user systemd unit, a window toggle on a hotkey, a button in the top
  bar carrying the number of open positions.
