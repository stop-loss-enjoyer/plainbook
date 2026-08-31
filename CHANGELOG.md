# Changelog

What changed and why. Newest first.

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
