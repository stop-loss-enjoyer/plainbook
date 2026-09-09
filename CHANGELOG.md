# Changelog

What changed and why. Newest first.

## v1.5.1, 09.09.2026

The licence changes. Nothing else does.

### Changed

- **The licence is PolyForm Noncommercial 1.0.0 from this version on.** The
  journal stays open and readable: you can run it, change it for yourself and
  pass it on, for any purpose that is not commercial. What you cannot do is
  sell it, sell it under another name, or build it into a product that is
  sold. Every version up to 1.5.0 was released under MIT, and MIT is not
  withdrawn from them.

## v1.5.0, 05.09.2026

Playbooks: the rules of a way of trading as a record, a checklist before
every trade and at its close, and the price of every rule in R. The
server starts on Python 3.10 again.

### Added

- **A Playbooks tab.** A playbook is one way of trading written down as
  rules: what has to be true before a trade is opened. **+ Playbook** writes
  one: the header, the setups with their rules a line each, the filters, the
  limits and notes. The page shows the rules numbered, the limits and how far
  the current block has come. Until a trade is ticked against a version its
  rules are a draft and change freely; after that, rules revised under a new
  number keep the old ones under *Earlier versions*, and the form refuses
  rules rewritten under the same number. The tab is drawn amber while the journal has no
  playbook. The page lists the trades opened under the playbook
  and counts them against the block. `tools/attach_playbook.py` ties the
  trades a playbook was already being traded by to it: the ones of its
  styles from its *counts from* date.
- **A trade is opened under a playbook.** The form has a *playbook* field
  next to *plan*; picking one sets the style and opens the checklist: the
  setup, its rules and the filters, a box each with the few words of the
  rule and the whole rule behind a question mark. The trade opens with any
  boxes ticked, and the rules left unticked are recorded with it. Its page
  shows the rules with a tick or a cross, in the version it was ticked
  against. The page of a playbook ends with *Review*: a dated entry each
  time, with screenshots, where a block is taken apart.
- **The figures of a playbook.** Statistics opens with *By playbook*, a
  row per playbook with its setups beneath it and a *clean* column, the
  share of ticked trades that met every rule; the reports carry the same
  table. The page of a playbook shows the figures by setup and *What a rule
  costs*: the trades that broke each rule and what they brought, against
  the trades that kept every rule, over the ticked trades of the current
  version.
- **Management rules, ticked at the close.** A playbook has a third list
  of rules, how the position is held: the stop not moved, held to the
  target, closed by Friday. The form that closes a trade shows them under
  the outcome, and the rules left unticked are recorded apart from the ones
  of the entry. The page of a trade shows both lists; the tables get a
  *held* column next to *clean*, and *What a rule costs* holds the
  management rules too.
- **A why under every rule not met.** A box left empty, at the entry or at
  the close, opens a line for the reason: the fact, not the verdict. It
  stands under the cross on the page of the trade, and the page of the
  playbook folds out the reasons given for each rule, a line per trade.
- **The frame.** Above the checklist of a new trade the limits of the
  playbook stand against the journal: trades this week and month, the R of
  the week against the loss limit, positions open, the risk typed against
  its cap, red where the trade would go past a limit. Nothing is refused.
- **A block asks for its review.** When a playbook's trades make a full
  block with no review written for it, the Playbooks tab turns amber and
  the page says which block is complete. A dated entry in *Review* settles
  it.

- **The Trash card on the Accounts tab is folded.** It grows with every
  deleted record and is wanted rarely; the card shows the count and
  opens on a click.

### Fixed

- **The server did not start on Python 3.10 and 3.11.** Three f-strings
  held a backslash inside their expression part, which those versions
  refuse; 1.4.8 had the same three. The README promises 3.10, and the suite
  now runs on it.
- **The CSV export had six empty-headed columns** and its figures shifted
  under the wrong headings once a trade carried a playbook. The rows carry
  the playbook columns now, in line with the header.
- **A deleted playbook could not be put back where it came from:** the
  Trash card took it for a trade. It is restored to the playbooks.

## v1.4.8, 04.09.2026

A sign for the journal, an equity curve that says which side of its start it
is on, a trade duplicated on any number of accounts, and old trades brought in
from a table.

### Changed

- **The journal has a sign**: a sheet of plain text with one candle on it,
  in the header and on the browser tab. The name next to it is set in the
  same monospaced face as the figures, in lower case. The tab you are on is
  underlined in the accent instead of sitting in a grey box.
- **The streak tile is gone from the front page.** It stood alone on a
  second row of the summary, with a grey strip beside it, and it said what
  the first rows of the list already show. The Statistics tab keeps the
  streaks card as it was.
- **A place in the summary grid with no tile in it is plain surface**, not a
  grey block: the grid used to show its own background through the gaps.
- **The equity curve says which side of the start it is on.** A dashed line
  marks the balance the curve starts from, and the wash under the curve is
  green above that line and red below it. The scale is in round numbers
  (10 000, 10 500) instead of the edges of the data, the dates are Mondays or
  the first of the month instead of four arbitrary days, and the end of the
  line carries the balance and its distance from the start instead of the
  name that already stands above the picture.
- **Money that moved outside a trade is marked on the curve** with a hollow
  dot, and the dashed line steps with it, so a deposit is not read as a big
  win and a withdrawal does not paint the account red; the tip says what it
  was.
- **The curve can be read by trade.** A switch above the picture puts one
  step per closed trade instead of the calendar, so a quiet month no longer
  stretches the line and a busy day no longer squeezes it.
- **A trade is duplicated on as many accounts as you like.** The block on
  the new trade form used to offer one other account; it lists every live
  account now, each with a tick and a risk of its own, and the risk starts
  at that of your last trade on the account. The account the trade itself
  is on is not offered.
- **Old trades can be brought in from a table.** `tools/import_csv.py`
  reads the CSV that Notion or a spreadsheet exports, takes the names of the
  columns as options, checks every row before writing anything and writes
  the trades the way the interface would, with their screenshots when the
  table names the files. A second run skips what is already there. The
  summary prints counts and sums only, and a column can go into the
  conclusions of a trade. INSTALL.md gained the step where the person is
  asked whether there is a history to bring in, and the order of an import
  through a Notion connection, which brings the page texts and the pictures
  tied to the right trade.
- **The page says which version this is**, in small print beside the name
  in the header.

## v1.4.7, 03.09.2026

The trash reads the same on every disk, and two tests that failed on some
computers and not on others.

### Fixed

- **Two records deleted within one second stood in the trash in the order the
  disk gave them.** The stamp on a deleted record counts seconds, and two
  records with the same stamp were listed the way the file system happened to
  list the folder: one way on one computer, the other way on the next. Within
  one second the trash now lists by name. A record deleted, written again and
  deleted within the same second used to land on its earlier copy; it takes
  the stamp of the next second instead.
- **Two tests of the trash failed on some computers.** They took the first
  record of their kind in the trash and expected their own, which held only
  where the folder is listed newest first. On another file system the record
  of an earlier test came first, and `test_58` or `test_66` failed with a
  record that was not theirs. Reported from an installation where the tests
  failed three runs in a row. The tests look their record up by its id now.

## v1.4.6, 03.09.2026

The third column of the paper's trades assessment, filled in by the journal,
periods counted by the exit, and a round of fixes from a reading of the whole
code.

### Fixed

- **A trade with a risk off the 0.05 step could not be saved again.** The risk
  field accepted 0.05, 0.10 and so on, and a trade recorded at 0.81% was
  refused by the browser the moment its form was opened for any other change.
  The field takes any figure now and refuses only an empty one, with a word
  instead of a traceback.
- **A refused edit no longer renames the folder first.** The folder of a trade
  follows its day and its pair, and it was renamed before the record was
  checked: an entry moved past the exit was refused, but the folder had already
  moved, leaving a file that named one id inside a folder named by another. The
  check comes first now; nothing on the disk moves for a record that is not
  saved.
- **A trade closed within the minute it was opened counted its own result in
  the balance it was opened on.** Only possible with both hours recorded and
  equal, but the R of such a trade was wrong. A trade's own close is left out
  of its own balance now.
- **The tip over an equity curve said $ whatever the account's currency.** It
  names the currency of the account.
- **A day or a week that netted exactly zero opened its card with an empty
  P&L.** Zero is a figure too, and it is offered like any other.
- The form refuses a trade on an account the journal does not have, which the
  interface never sends but a hand-made request could.

### Changed

- **A period is the trades that closed in it.** A monthly or quarterly report
  and the current-period tile on the front page used to count the trades by
  their entry, while the cards, the equity curve and the balance change of the
  same report counted by the exit. In one report the result in money and the
  balance change disagreed by every trade that ran across the edge of the
  month. Both now count by the exit, the way a broker states a month; the
  Reports tab offers the months and quarters trades closed in, and the tile
  says how many closed. The list of trades still groups by entry, because a
  journal is read by the decisions in it, and a row of a report opens that
  list, so the two can differ by a trade that ran across the boundary.

### New

- **The risk of a new trade follows the account.** The field starts at the risk
  of your last trade on the account picked, and changes with the account until
  you type a figure yourself; the duplicate's risk follows its own account the
  same way. A prop account and your own are run at different sizes, and the
  form asked for the figure every time.
- **A result that disagrees with the money is pointed out.** A Win with a
  negative PnL, or a Lose with a positive one, is saved as written and marked
  on the trade page, right where the closing form lands: nearly always one of
  the two is a slip, and Edit puts it right. It is a word, not a refusal, since
  a win eaten by commission is a real thing.

- **The result column of the trades assessment.** The paper Daily Report Card
  grades a trade in three columns, trade, grade and result, and the journal had
  two. The third is there now, on the daily card and on the weekly one, and it
  fills itself in: pick a trade from the suggestions, or type its pair, and the
  result stands there as the journal knows it, `Win +1.20 R`, to be kept or
  overwritten. A card graded before this shows the results of the trades it
  named the next time it is opened, and keeps them when saved. Files written
  before still read; a line with two cells is a line with an empty result.
- **The daily card laid out as the paper is.** The best trade of the day stands
  beside the trades assessment, and the overview runs under both across the
  width, the order the paper has; on a narrow window the two columns become one.

## v1.4.5, 03.09.2026

The expectancy next to every winrate on the front page, and by that name in
the Statistics tab and in the reports.

### New

- **EV beside the winrate.** Every winrate on the journal page, in the overall
  tile, in the tile of each style, in the current period and in the total row
  of every week, month or quarter, now carries its EV to the right: what a
  trade brought on average, in R, Σ R over the closed trades. Unlike the
  winrate it counts the break-evens, because a trade closed at zero still paid
  its commission and swap and never comes back at exactly zero R. Hovering over
  it in a tile shows how the sum splits between wins, losses and break-evens.
  The line under the total R tile, which used to say average, says EV as well,
  since it is the same number.
- **EV in the Statistics tab and in the reports.** The column that stood there
  as "average R" is that same figure, and now carries the same name in every
  table: by style, by pair and by account on the Statistics tab, and by
  direction, entry timeframe and execution in a report too; the summary row of
  a report says so. A pair gets its row, and its EV, from its first closed
  trade, so there is nothing to add anywhere for a new one. A report built
  before this keeps the old heading until it is rebuilt.

## v1.4.4, 03.09.2026

A weekly report card next to the daily one, a table of trades graded on both,
screenshots that reach into a plan and its updates, and a word from the
journal after every form that saves something.

### Fixed

- **A trade suggested on one card no longer follows you to another.** The
  trade and grade fields of the assessment table share one name across five
  rows and both cards, and without a word against it a browser kept its own
  memory of what had been typed there and offered it back anywhere the field
  reappeared, a trade from last week turning up as a suggestion on today's
  card. The field now says not to remember, the way the pair field already did.

### New

- **The daily card carries a trades assessment too.** The same numbered table
  the weekly card has, on the daily one now: the trades of the day and the
  mark each one earned, the field suggesting the pairs closed that day. It is
  the same code and the same file section on both cards, so a search for a
  trade by name finds it whichever card it was graded on.
- **The weekly card.** The paper Weekly Report Card as it is, opened by the
  **+ WRC** button next to **+ DRC**: process grade, opportunity quality, the
  progress of the current focus from 1 to 5, the weekly process, what you
  learned, errors, the best trade of the week and the ones you missed, the key
  lesson, and the trades assessment where the week's trades get their marks on
  five numbered lines. The P&L and the number of trades are filled in from the
  week you traded and stay editable, the assessment field suggests the pairs
  you closed that week, and an empty line of it is not saved. A card belongs to
  the calendar week the journal already groups the trades by, is found by
  search along with everything else, and goes to the trash rather than away.
- **The Cards tab holds both.** The daily cards in the upper table, the weekly
  ones under them, and a click anywhere on a row opens that card for editing
  with its Delete button inside. Both kinds are one record kept in two rhythms,
  so both live in `journal/cards`: `2026-08-30.md` for a day, `2026-W36.md`
  for a week.
- **The buttons say which card they open.** **+ Card** in the header is now
  **+ DRC**, and **+ WRC** stands next to it.
- **The journal answers a form.** A trade opened or closed, a card saved, a
  plan written, an update added: the journal says so in the middle of the
  screen for about a second and takes the message away itself. Until now a form
  simply landed you on a page and left you to work out whether it had saved.
- **The name in the corner leads home.** Plainbook in the top left is a link to
  the journal.
- **Screenshots in the plan and in its updates.** The **plan** field has a drop
  zone under it, so the position you set up stands with the plan you wrote, and
  the update form on the plan page has one as well: paste before pressing Add
  and the picture stays under that dated line. Adding an update leaves every
  other picture of the plan where it was.

## v1.4.3, 02.09.2026

A journal that survives a broken file, a search across everything written, the
selection as a spreadsheet, and a limit for the day on a prop account.

### Fixed

- **One broken file no longer takes the whole journal down.** A date typed the
  wrong way round or a letter in a number used to leave every page blank, with
  the reason only in the server log. The record that does not read is now named
  at the top of every page with the file and the reason, and everything else
  loads and counts without it. `tools/check_journal.py` runs the same check
  from the terminal.
- **Winrate overall counts every trade.** It used to count only the styles
  still in the list, so a retired style quietly left the overall figure while
  the selection tile next to it still counted its trades.
- **A pair is one pair whatever the case.** `eurusd` typed into the form used
  to become a second pair next to `EURUSD` in the filters, the tables and the
  reports. The form now writes the pair in capitals.
- **The exit cannot be before the entry.** A close dated earlier than the entry
  was accepted and counted into the balances of trades opened in between.
- **The money of an account is shown in its currency.** The currency field of
  an account was stored and never shown; every sum wore a dollar sign. The sign
  now follows the account ($, €, £ and the like, the code for the rest), and a
  figure that spans accounts carries the currency they share, or none when
  they differ.
- **Deleting an account moves it to the trash**, like every other record. It
  used to be the one thing that was removed outright.
- **The equity curve of a period starts at the balance of that period.** With a
  month filter on, the line used to start at the day the account was opened and
  add up only the chosen trades, so the axis said nothing true. It now begins at
  the balance the account entered the month with; with a filter by style or by
  pair, only the chosen trades move the line from there.
- **The folder of a trade follows its day and its pair.** Editing the entry
  date or the pair used to leave the folder named after the old ones. The trade
  is moved under an id that says what the record says, and the number in the
  day is kept when only the pair changed.
- **A card is not moved onto another.** Changing the date of a card to a day
  that already has one used to overwrite that card without a word. The journal
  now refuses and says which card is in the way.
- **Open positions show the hour only when it is known.** An entry without an
  hour used to read `00:00` in the open positions block.
- **The loss buckets read from zero outwards**, `0…-0.5`, `-0.5…-1`, `-1…-1.2`,
  the way the wins do. The old `-1…-0.5` promised a -1R that in fact belonged
  to the stop bucket next to it.
- Two small things a person would not notice: a screenshot path sent back by a
  form is checked to stay inside the record's own folder, and the origin check
  compares the host and the port exactly instead of by prefix.

### New

- **Search.** A tab of its own: a word or a phrase is looked for in every idea,
  conclusion, note, plan, update, review and card, and every hit is a link to
  the record with the matching words shown around it.
- **The selection as CSV.** A button next to the filters on the front page
  writes the filtered list into a file for a spreadsheet, with every stored
  field and the computed ones: R, the balance at entry, the risk in money.
- **Streaks.** The front page has a tile with the run the selection is on now,
  and the Statistics tab a card with the longest runs of wins and of losses,
  counted in the order the trades closed. A break-even neither extends a run
  nor breaks it.
- **A daily loss limit on an account.** Set on the Accounts tab, it is the prop
  rule of how much a day may lose. The tile of the account on the front page
  then adds up what today has already cost and what the open trades still put
  at risk, turns amber at four fifths of the limit and red when it is reached.
- **The trash is on the Accounts tab.** What was deleted is listed there with a
  Restore button, so a mis-click is undone without a file manager. A record
  written again under the same id is never overwritten by the restored one.
- **A plan against the fact.** The page of a plan says how many of its trades
  went with the narrative and how many against it, with the R of each pile; a
  plan that said "no trade" counts every trade taken under it as against it.

## v1.4.2, 02.09.2026

- **The exit of a trade carries its hour.** A close only had a date, so a trade
  closed at noon was not in the balance of a trade opened at three the same
  afternoon: the balance at entry, the risk in money and R were all measured
  against yesterday's account. The closing form now asks for the moment, and the
  balance counts a close that already happened. An exit left at midnight is an
  exit whose hour is unknown and behaves as before, which is what every trade
  closed so far keeps doing.

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
