# Keeping the journal

A guide for the person using it. How it is built and what the files look like:
[README.md](README.md). How to install it: [INSTALL.md](INSTALL.md).

The journal opens in a browser at **http://localhost:8778**. Installed with
the autostart of [INSTALL.md](INSTALL.md), the server comes up with the
machine and there is nothing to start by hand; the downloaded file and the
`plainbook` command of a pipx install open the browser themselves. On Linux
with Omarchy there is also a button in the top bar and a hotkey.

## The daily round

1. **Before the market**, a plan if the week or the day needs one: the
   **+ Plan** button.
2. **Opened a position?** Write it down at once, with the **+ Trade** button,
   pick the plan it follows and the playbook, and tick its rules.
3. **Closed it?** Close the trade too: the **Close** button on its row of the
   open positions block, or **Close trade** on the trade page.
4. **At the end of the day**, a daily card: the **+ DRC** button, after the
   paper Daily Report Card the card follows.
5. **At the end of the week**, a weekly card: the **+ WRC** button.
6. **At the end of a month or a quarter**, a report: the **Reports** tab.

The first step matters because the idea is written down before the market
shows who was right, and an idea read back afterwards always looks tidier
than it was.

## A new trade

**+ Trade** in the header. The fields:

- **account**: archived accounts are not offered.
- **pair**: the list under the field carries the same flags the journal does,
  and it opens and shuts on a click on the field. Typing filters it; a pair
  that is not in the list is simply typed in and saved with the trade, in
  capitals whatever way it was typed, so `eurusd` and `EURUSD` are one pair.
- **direction**, **style**, **entry TF**: the styles and the timeframes come
  from your own lists, edited on the Accounts tab.
- **risk, % or money**: the risk as a percent of the computed balance of
  the account at the entry, or as a sum of money with a currency sign or code
  beside it: `150$`, `$150`, `150 usd`. The line under the field says what
  the other one is, `= 150 $ of 10 000 $` for a percent and `= 1.5% of
  10 000 $` for a sum, against the balance of the account picked above on
  the entry date typed below. A trade written in days after it was taken is
  measured against the balance of its own day, so the trades closed since
  do not change its R. A
  sum is saved as the percent it makes, to two decimals, since the percent
  is what R is measured by, and the trade page shows both. The field starts at the risk
  of your last trade on that account and follows the account until you type
  a figure yourself; a duplicate's risk starts at the last trade of its own
  account and takes money the same way, against its own balance.
- **entry**: date and time of entry; clicking the field opens a calendar.
  The time counts as known, midnight included. When you do not know the
  hour, tick **hour not known** under the field: the journal then keeps the
  date alone, and orders the trade within its day by the date only.
- **plan**: the trading plan this trade follows, picked from the plans you have
  written. Left at "-" if the trade belongs to none.
- **playbook**: the playbook the trade is opened under, if any. Picking one
  sets the style and opens its checklist under the header fields, above the
  idea blocks; see [Playbooks](#playbooks) below.
- **execution**: the checkboxes. They come from your list too, so the formats
  you actually trade are the ones offered.
- **Prices**, a fold under the fields, all optional: the **entry**, the
  **stop** and the **target** price as you planned them. The stop sets 1 R by
  price, so the line beside the fields says the RR of the target while you
  type, whatever the pair. A stop on the wrong side of the entry is refused.
  Under a playbook with a *least RR* limit, the frame of its checklist
  compares the RR typed to it and turns red below it.

Below is the idea block: timeframe, text and screenshots. **+ idea block** adds
another one when the idea rests on several timeframes.

**Screenshots**: click inside the dashed frame and press **Ctrl+V**. Whatever is
on the clipboard goes in, a screenshot from TradingView or a cut of the screen.
A picture file can be dragged in from a folder too, or picked with **Choose a
file**. To take a screenshot out, press the cross in its top right corner.
Pressing Save while a picture is still on its way waits for it.

**A form is not lost by accident.** Once you have typed in a form with text or
screenshots, leaving the page by a tab or a link asks first.

**Duplicate on other accounts** is for the same position taken on several
accounts, for example on the exchange and on two prop accounts. Open the block:
every live account has a row, except the one the trade itself is on. Tick the
accounts and set the risk each carries, and **Open trade** writes the trade you
filled in and a copy of it on every ticked account. They carry the same pair,
direction, style, entry, idea text and screenshots, and differ only in the
account and the risk, so each is measured against its own balance. After that
they are ordinary trades: each is closed with its own result and PnL.

**Open trade** saves it, and the position counts as open until it is closed.

## Playbooks

The **Playbooks** tab holds the standing rules of a way of trading, what has
to be true before a trade is opened. Where a plan is written for a day and a
pair, a playbook has no date and no pair. It is the trading system itself,
and it changes by version.

The tab is drawn amber while the journal has no playbook, because the rules
are what the trade form will hold the trades against, and until they are
written nothing can be held.

**+ Playbook** on the tab writes one. The form is six cards: the header, the
setups, the filters, the management, the limits and the notes. What each part is for, and how the journal uses it, is
laid out in [PLAYBOOK.md](PLAYBOOK.md).

- **name, status, version, counts from, block, styles, what the playbook
  is.** The last is a few lines on the idea behind the rules, shown above
  them on the page; it is not ticked and changes freely. The status is
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
  words need it; the page shows both. **+ rule** under the rows, or Enter in
  a row, adds the next one; the cross takes one away, and an empty row is
  dropped.
  **+ setup** adds another setup. A playbook with one way of entering leaves
  the name empty.
- **filters**: rules checked before every trade, whatever the setup, in the
  same fields.
- **management**: the rules of holding the position, in the same fields.
  They are ticked when the trade is closed rather than when it is opened:
  the stop kept where it was, the position held to its target, closed by
  Friday. A list of three to five rules gets ticked; a list of ten gets
  skipped.
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
filters, then the management. That number is what a trade records when a
rule was not met.

**Revising the rules.** Until the first trade is ticked against a version,
the rules are a draft, and you edit them as often as you like. Once a trade
has been through the checklist under the number, a change of the rules asks
for a new number. The rules as they were are kept under *Earlier versions* on
the page, and a trade opened under the old number keeps the rules it was
ticked against. Only the rules and the names of the setups are held to this;
the intro, the notes, the limits and the status change freely.

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
sets the style to the playbook's and opens its checklist under the header
fields, above the idea blocks: the setups to choose from, the rules of the chosen setup and the filters, a box
each with the few words of the rule; the question mark shows the whole rule.
Tick what holds. The trade opens with any number of boxes ticked; the rules
left unticked are recorded with it, and the line under the list says how
many. Under every box left empty stands a line for why, and ticking the box
folds it away. The line asks for the fact, and "Target 1.6R, took it anyway"
is enough; whether it was a good reason is a question for the review, where
the reasons given for every rule stand together. Leaving every box empty is
recorded too, as every rule not met. The page of the trade then shows the
rules with a tick or a cross, in the version it was ticked against, whatever
the playbook says later.

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
holds them against the playbook's own trades at that moment: trades this
week and this month against the caps, the R of the week against the loss
limit, positions open against the cap, and the risk typed in the form
against its cap. A figure turns red where this trade would go past the
limit. The trade still opens; the figure is there to be seen before the box
is ticked.

**Reviewing a block.** The page of the playbook carries a *Review* card near
its end, under the trades and before the earlier versions: one field, a
dated entry each time, and screenshots pasted with it stay under
that entry, the way an update is added to a plan. That is where a block is
taken apart when its count is reached, what the trades said, what leaked and
what the next version changes, before the rules are revised in the form
under a new number. When a block has run its course and has no review yet, the
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
and nothing else: no setup, no checklist and no version, because nobody
ticked the rules for them, so the rules stay a draft until a trade is ticked.
A trade takes the version on the day its rules are ticked. Open each one and
fill that in if you remember.

**The figures.** The Statistics tab carries *By playbook*: a row per
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
market opens and holds the one thing a trade cannot, what was supposed to
happen.

- **title, pair, narrative**: a name of your own, the instrument, and what you
  expect: bullish, bearish, neutral or no trade. A decision not to trade is a
  plan as well.
- **from** and **until**: the days the plan covers. Until is left empty for a
  plan that lives one day. The list marks the state of a plan with a pill:
  green **current** for one that covers today, blue **ahead** for one whose
  first day has not come, red **voided** for one called off. A plan that has
  run its course wears nothing. The card of a current plan carries an amber
  stripe on its left edge, like an open trade.
- **analysis blocks**: timeframe, text and screenshots, the same blocks as the
  idea of a trade. **+ analysis block** adds another timeframe.
- **plan**: what you will do, and what you will not. This is the part you read
  back when a trade tempts you mid-week. Under it there is a drop zone of its
  own: the levels you marked, the position you set up, Ctrl+V and they sit with
  the plan itself.

**Updates** are added from the plan page rather than from the form: one line,
and the journal stamps it with the date. The plan stays as it was written and the week
is written under it. An update takes screenshots too: paste into the zone under
the field before pressing **Add**, and the screenshots stay under that line, so a
week of a plan reads as it happened. Nothing else in the plan is touched when
an update is added. Editing the plan shows the updates as they were written,
text and screenshots, so a slip in one can be put right; a new one is still
added from the page.

**Review** is written later, in the plan form: how it went, with screenshots.

**Void.** A plan the market went against, the direction or the variables
wrong, is voided and kept. The **Void** button in the header of its page
leads to a short form at the bottom, one line for what went against it, and
the plan is called off. It stops being current, the list says
**voided** next to it, the stripe on its card turns red, and the reason stands
under **Updates** with the date. Everything else stays: the analysis, the
plan, the trades tied to it, so the mistake can be read back later. The
trade form still offers a voided plan, with the word in its name. **Restore**
undoes it, with a dated line of its own, when the market turns around after
all. **Delete** is for a plan written by mistake: that one goes to the trash.

**What came of the plan.** Every trade you tied to it is listed on its page with
its result, PnL and R, and the line under the table says how many trades, the
winrate, the Σ R and the money. That line answers what a plan in a document
cannot, whether following it was worth anything.

**Plan against fact.** For a bullish or a bearish plan the page also says how
many of its trades went with the narrative (a long under a bullish plan) and
how many against it, with the R of each pile. A plan that said "no trade"
counts every trade taken under it as against it.

## Market notes

**+ Note** on the **Notes** tab writes one. A note is about the market and
wider than one trade: a level a pair keeps respecting, a pattern that keeps
coming back, a lesson wider than a day.

- **title** and **date**: the name of the note and the day it was written.
  The date is yours to set, a note about last month can carry last month.
- **blocks**: a note is written in blocks, each a heading of its own, a text
  and a drop zone: click, Ctrl+V, and the screenshot sits under that text.
  The heading is optional, a note of one block needs none. **+ block** adds
  another, and a block left empty is dropped when the note is saved. A
  screenshot is taken out of the note with its cross in the form.
- **examples**: the trades that show what the note says. The card at the
  bottom of the form lists every trade of the journal, newest first, spelled
  as date, pair, side, style and result; pick one and it stands above the
  list with a **Remove** button, pick another and it stands under it.

On the note page the examples are rows with the figures of the trade: a row
opens the trade as it was written, and the trade page has a button back to
the note. Under the rows the same list ties one more trade without opening
the form, and **Remove** on a row takes the trade off the note and touches
nothing else: the trade stays in the journal. A trade page also says which
notes it is an example in, under the line of its playbook.

The list on the Notes tab shows every note with its date, the first line of
its text and how many examples it has. Notes are found by Search along with
everything else, and a deleted note goes to the trash on the Accounts tab
like a plan does.

## The stop at breakeven

The **Breakeven** button, on the trade beside Close trade and on its row of
the open positions block. It says that the stop now stands at the entry, and
the journal frees the risk of that trade, so the daily loss limit of the
account counts only the trades that can still lose. Two spellings stand for
two things in this journal: *breakeven* is the stop moved to the entry, and
*break-even* (BE in the lists) is a trade that ended at zero. The page of the trade says since
when, and the line stays on a closed trade as the history of its stop.
**Risk back** puts the risk where it was, for a stop moved by mistake. The
playbook limits are not touched: a trade at breakeven is still a position
open at once, and the loss of the week is counted from closed trades only.

## Updates while a trade runs

The **Update** button on the page of an open trade leads to the **Updates**
card at the bottom of it: a line about what changed since the entry (the
stop moved, a partial taken, what the market did at the level) and a
screenshot zone under it, then **Add**. Every update is written under the
trade with its date and time, in the order they came, and the screenshots
pasted with it stay under its line. The rest of the trade is not touched:
the idea and its screenshots stay as they were.

The updates stay on the trade after it is closed and go into the file that
**Share** makes; the search reads them. A closed trade takes no more of
them, because what is learned at the exit goes into the conclusions. Editing the
trade shows the updates as they were written, text and screenshots, in a card
of their own, so a slip in one can be put right.

## Closing a trade

The **Close trade** button. You fill in the result (Win / Lose / BE), the PnL
in the currency of the account (its sign stands in the label) and the moment
of the exit; below that go the screenshots of the exit and the conclusions
with their own screenshots. A trade closed once is not closed again: its
result and exit are changed with **Edit**, and the close address of a closed
trade opens the edit form.

The result starts on **pick one** and the form will not be sent until you choose,
so a trade cannot be closed with a result nobody picked.

The exit holds the hour as well as the date, and it matters: a trade opened later
the same day is measured against the balance this close left behind. When the
hour is not known, tick **hour not known** under the field, as for the entry. An exit dated before the entry is refused. A Win with a negative PnL,
or a Lose with a positive one, is saved but pointed out on the trade page:
nearly always one of the two is a slip, and Edit puts it right.

R is worked out by the journal, `PnL / (risk% × the balance at the moment of
entry)`, and there is nothing to recompute by hand.

**Prices at the close**, a fold of the closing form, all optional: the **exit**
price, and the **best** and the **worst** price the market reached while the
trade was open. With the entry and the stop written on the trade they read in
R: how far the trade went for you (MFE), how far against it (MAE), and what a
winner gave back from its best. The trade page says them under **in R by
price**, and marks the target, the best and the worst on the bar of its
result.

## The trade page

The fields of the trade stand on the left and its **passport** beside them:

- **Result against the risk**, for a closed trade: a bar from zero to its R
  on an axis of R, the risk it was sized for shaded from the stop to zero,
  the stretch from the stop to the stop edge a shade deeper, and a tick for
  every other closed trade of the account, so the result is read against the
  ones around it. The heading says where it stands among them by R.
- **In the market**: the entry, the moment the stop went to the entry, and
  the exit on one line, red while the trade was at risk and amber once the
  stop stood at the entry, with how long it ran and how much of it was at
  risk. An open trade runs to now. Without the hours on the entry and the
  exit the line is drawn by the day.
- **On the account**: the curve of the account drawn as on the Statistics
  tab, with the scale of the balance, the dates, the wash against the start
  and the balance under the pointer; the entry and the exit of this trade are
  marked on it, the exit with a dot where the trade moved the balance.

**A screenshot opens over the page** on a click: at the size of the window,
and at its own size on a second click, to read a level closely. The arrows go
to the next and the previous picture of the page, Esc or a click beside it
closes it.

## Editing and deleting

- **Edit** on the trade page changes any field, screenshots included. For a
  closed trade the result, the PnL, the moment of the exit, the exit shots and
  the conclusions are edited there as well, so a result entered wrong is fixed
  without touching the file. The updates of a trade that has any are in the
  form too, as they were written; a new one is added from the trade page,
  not here. The folder of the trade is named after its day and
  its pair, so changing either moves the folder under a new name; a link to
  the old one stops working, the record itself is untouched.
- **A copy forgotten at the entry** is written from the same form: while the
  trade is open, the **Duplicate on other accounts** block stands in its
  form as it does in the new trade form. Tick the account, set the risk,
  and **Save** writes the copy there with the idea and the screenshots as
  they are now. An account that already holds the position (the same pair,
  side and entry) says so instead of offering a box. A closed trade has no
  block: its result and PnL are its own.
- **Delete** sends the trade to `.trash` next to the `journal` folder, where
  the **Trash** card on the Accounts tab lists everything deleted and
  **Restore** puts it back, screenshots and all. A record written again
  under the same id in the meantime is never overwritten: the one in the trash
  stays there until you sort it out by hand.

## The daily card

**+ DRC** opens today's card; if there already is one for that day, it opens
that one. The **Cards** tab lists them, the daily ones in the upper table.

- **date**: you can change it when reviewing yesterday. Changing the date
  moves the card rather than creating a second one; if the new day already
  has a card, the journal refuses to overwrite it, and says so.
- **process grade**, **PnL**, **opportunity quality**, in the order of the
  form. The grades offer A / B / C / D / F, but the field is free, so write
  in whatever scale you use. The PnL is filled in from the trades closed that
  day, and the line under it says how many closed; the field is editable, so
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
- Then, laid out as on paper: *current focus (goal)*, *trading process*,
  *what I learned / did well today?*, *errors & improvement*, then the best
  trade beside the assessment, and the overview under them.
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
- **PnL** and **trades** are filled in from the trades that week closed. Both
  are editable, because the count you review by is yours. Under the
  count stand the week's trades in figures and colour, no words: green won,
  red lost, amber break-even, blue still in the market when the week ended.
  That is why the field can say 3 while the colours say `2 / 1 / 1`: the field
  counts what the week closed, the colours count everything it held.
- **progress** under the focus says how far the thing you are working on has
  moved this week, out of 10, and every number carries the word for what it
  means, from `1 · not moved` to `10 · done, take a new focus`. A 10 is a focus
  worked through: retire it and write the next one. The words are there so that
  the same number means the same week in January and in June. A card written
  when the scale ran to 5 keeps its number and reads as it did; that number
  was a fifth of the way rather than a tenth, so change it by hand if you want
  the old weeks on the new scale.
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
held those trades has nothing to count: the weekly table then shows the number
written on the card, the daily one a hyphen.

## On every page

- **The name in the top left corner is a link home**, to the journal with its
  trades, from wherever you are.
- **Every form answers.** Save a trade, a card, a plan or an update, and the
  journal says what it did in the middle of the screen for a second, then
  takes the message away without a click.
- **A page that cannot show its record says why.** An address that leads
  nowhere, a trade moved to the trash and reopened from the browser's
  history, gets a page with the navigation and a way back; a record whose
  file does not read gets the file and the reason on top of the page.

## The front page

- **Account tiles**: the computed balance, the start balance and the difference
  in colour, in the currency of the account. The difference is what the account
  earned, so money you put in or took out is named separately and is never
  mistaken for a win or a loss. Archived accounts do not appear here. The
  rules of a prop firm are not on the tile: where an account stands against
  them is on the Accounts tab.
  **The name of an account is a link**: it opens Statistics with that account
  chosen, its own equity curve and its own figures.
- **Open positions**: what is in the market right now, with the risk in money,
  a **Breakeven** button and a Close button. Press Breakeven when you have
  moved the stop of that trade to the entry: the trade can no longer lose what
  it was sized for, so its risk is freed. The money column shows a green
  **BE** chip in place of the sum, and the title of the block counts the
  trades held that way. The daily loss limit of the account stops counting
  them: with three trades at breakeven and two fresh ones the tile counts the
  risk of the two, in money, and says how many stand at breakeven. Pressed by
  mistake, **Risk back** on the page of the trade
  undoes it. The R of the trade is still measured against the risk it was
  opened with, whatever happened to the stop later.
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
- **Filters** sit behind the funnel button to the left of the switch: account,
  pair, style, direction, result, a range of months. They apply both to the
  list and to the summary tiles. While a filter is on, the funnel is lit and
  shows how many fields are set; **Reset** clears them. The form closes on a
  click away or on Escape. **A filter survives a trade being opened**: a trade opened
  from a filtered list carries the selection, its page has a **← Journal**
  button that names the filter, the Journal tab leads to the same list, and
  editing, closing or deleting the trade lands back on it.
- **CSV** next to the switch writes the list as it is filtered into a file for
  a spreadsheet: every stored field and the computed ones, R, the balance at
  entry, the risk in money and its currency, one trade per line.

## How the figures are worked out

**Account balance** = start balance + the PnL of every closed trade + the
money that moved outside trades (deposits, withdrawals, fees, corrections).
It is stored nowhere and worked out afresh every time, so it cannot fall
behind reality.

**R** = PnL / (risk in percent × the account balance at the moment of entry).
A trade closed earlier the same day is already in that balance when both
moments carry their hour, the exit of the one and the entry of the other. An
exit or an entry left at midnight is a moment whose hour is unknown, and the
PnL of that close then counts from the next day.

**Winrate** = wins / (wins + losses). Break-even trades stay out of the
denominator, because such a trade ended neither way. What they cost, the
commission, the spread and the opportunity spent, is visible in the sum and
in the EV, where break-evens count like everything else. Under the winrate stand three numbers:
wins in green, losses in red, break-evens in yellow.

**EV** = Σ R / the number of closed trades: what a trade brought on average,
in R. It stands to the right of every winrate. Unlike the winrate, it counts the
break-evens: a trade closed at zero still paid its commission and swap and never
comes back at exactly zero R, so leaving it out would flatter the figure. Hover
over it in a tile to see how the sum splits between wins, losses and
break-evens. The total R tile carries the same figure under the sum, and every
table of the Statistics tab and of a report has an EV column: by period, pair,
style, account, direction, entry timeframe, execution and time in the market,
and a report cuts the same way by its own months. A
pair gets its row, and its EV, from its first closed trade; nothing has to be
added anywhere for a new one.

**Total R** is the figure that spans accounts. A dollar on a prop account and
a dollar on your own are different kinds of money, which is why the front
page adds up R across accounts and leaves the money per account.

**Money is shown in the currency of its account.** A sum that spans accounts,
the PnL column of the list, the total of a week, carries the currency they all
share; when they do not share one, the number stands without a sign, because a
sum of two currencies has no name.

## The Statistics tab

**What the tab is for.** The front page says where you stand now, a report
says how one month went, a playbook page says whether one trading system
works. This tab is the one page with no period of its own and a free filter.
Cut the whole history any way you like, and see whether that cut has an edge
and whether there is enough of it to believe. It is laid out the way a report
is, in the same order: the cut as the title, a strip of figures, two charts,
the equity, then the playbooks with the rules and the tables. The cut, the
selection and the filter are one thing on this page, the trades the figures
are worked out on.

**Trades or ideas.** A position taken on two accounts at once, a prop
account and your own, is two trades in the journal and one decision. When
the selection holds such copies, a **Trades | Ideas** switch stands at the
top right. Trades counts every copy, the way the reports and the front page
do. Ideas counts each position once: its R is the mean R of its copies, its
money is the money of all of them, so the winrate, the EV, the streaks and
the deepest fall in R describe your decisions and not how many accounts you
ran them on. The equity curves stay in money and carry every copy in both
modes.

**The cut is written out at the top.** Under the word Statistics stands the
selection in words, `XAUUSD · swing · Broker · August 2026`, and every part of it
is a link that drops that one part. **← Back** to the right of it takes one
step back: the cut without the part added last, so a pair and then a month
is left one click at a time, the way it was built, and the last click lands
on every closed trade. The funnel opens the whole
form, **Reset** drops the cut whole and puts every closed trade back, **The
trades** shows the selection as a list, and **CSV** writes the same selection
into a file for a spreadsheet, a period cut included. Reset stands only while
there is something to drop, and it stands on a cut that matched nothing too,
which is where it is wanted most. Under any
cut the list stands at the foot of this page and the button jumps
down to it; with no cut it is the journal's own list that opens, since there
the two pages hold the same trades. The line under the title says how many
trades closed, how many are still open and therefore out of every figure, the
money the cut made when every trade sits on one account, between which dates
the trades closed, and how many closed trades the filter left out. Those left
out are what the grey figures in the strip are read against: a filtered page
has no month before it, but it always has a rest.

**The strip.** Six figures, one tile each.

- **EV per trade** leads, because it is the one figure that stays comparable
  when the filter changes: Σ R grows with the size of the cut and says nothing
  between two cuts, so it stands in the line under it with the number of
  trades.
- **Winrate**, and beside it, a size down, the winrate this selection would
  need to come out at zero, break-evens charged in. Over that figure the
  trades pay, under it they do not, which is what the EV says in one number.
  Under the tile the trades won, lost, break-even and still open, by colour.
- **Payoff**: how many R a win brings for every R a loss costs, the average
  win and the average loss under it, and the **profit factor**: the money the
  winners made for every unit of money the losers lost, fees and sizes
  included. A ratio carries no sign; whether it is enough is what the
  winrate needed beside it answers.
- **Deepest fall from a high**, the maximum drawdown: how far the selection
  went under its own high, between which dates, whether it has been made back or how far under it still
  stands, and the longest run of losses. With one account chosen, the tile
  also says the deepest fall of its balance in money and in percent of the
  high it fell from, money you took out not counted as a fall. The figure is
  never painted red, because a fall is negative by definition and a colour
  would say nothing.
- **Mistakes**, counted the way a report counts them: a rule ticked as not
  met, at the entry or at the close, or a loss past the stop, a trade that
  did both being one mistake. Under the count stand what the losses ran past
  the stop by, what those trades brought, and how many trades under a
  playbook were never ticked. The first two answer different questions: the
  overruns themselves cost the one, and the other is everything those trades
  did, wins included.
- **Best and worst trade** by R, each a link to the trade.

A winrate or a payoff worked out from fewer than five decided trades is grey,
because a percentage of two trades says little. An empty tile is a hyphen
with the reason under it.

**Trade by trade, or week by week.** The left chart under the strip, the
tape, is the selection over time. With thirty closed trades or fewer, and on
any cut to a week, every trade is one bar in the order of the exits against
the line of the stop, the way a report draws its month, and each bar opens
its trade. Past thirty the bars are weeks, months or quarters, the R of the
trades that closed in each, oldest on the left. Each bar is named while the
chart has room for a name, and the months or years are marked across it
either way. The page opens on whichever grain the span of the selection asks
for, and the switch in the corner reads it any other way. A period that
closed nothing keeps its place and draws no bar, because a week the account
stood still is part of the history. The same
figures as a table, newest first, stand among the tables at the foot of the
page; the newest twelve periods are open and the rest fold under one line.

**A bar or a row narrows the page to that period**, counted the same way it
was counted, by the exit. This is the one cut that goes around the months of
the filter, because those pick trades by the entry, the way the list of
trades does, and a period picks by the exit, the way a report does. Mixing
them would print a total that disagrees with the row you clicked on. The period
stands in the title like every other part of the cut, drops itself the same
way, and is shown in the filter form so that the count on the funnel adds up.
A trade belongs to the period it closed in, so one entered in July and closed
in August stands in August. Inside a month read by weeks, a week that straddles
the edge of the month is drawn without a link: its own page would count the
days outside the month too, and the figures would not be the bar's.

**The trades of a period stand at the foot of the page.** With a period cut,
under all the tables, is the list of what that period closed: the very set
every figure above was worked out on, newest exit first. It leads with two
dates, the exit it was counted by and the entry beside it, so a trade that ran
across the edge of the month is seen for what it is. The newest thirty stand
open and the rest fold under one line. A row opens its trade, and the trade
carries a button back to this cut, the whole cut and not only its period: the
statistics of August and the statistics of August on one pair are two pages
under one title.

This is why **The trades** keeps you on this page when a period is chosen.
The journal picks by the entry, so its August is a different set of trades:
one entered in July and closed in August is counted here and stands in July
there. A cut with no period in it, a pair or a style, lists its trades
at the foot of the page as well, as **Trades of this cut**: the closed ones,
newest exit first, so a pair and then a month reads down to the very trades
of that pair closed in that month. Only with no cut at all does the button
open the journal. The CSV file is written from the same selection the page
counted.

**R distribution.** Beside the tape, every closed trade is a dot on one
axis of R, the trades of the same R stacked into a column: a loss and a win
of the same size stand the same distance from zero, the stop is the dashed
line at -1, and a dot left of the stop edge lost more than the risk allowed.
Point at a dot for the pair, the date and the R; click it to open the trade.
Under the dots runs a strip of the buckets, and under the strip two tables,
**Losses** and **Wins**, count each bucket with its share and its R, in the
colours of the dots: the further a bucket is from zero, the brighter. The
break-evens are the amber dots near zero, counted in a line of their own.

**The losses are cut where a stop lands.** A trade taken to the stop comes back
a little worse than -1R, because commission and swap are paid on top of it, so
the bucket **-1…-1.2** means the stop as designed. Anything past -1.2R is a
bucket of its own: that loss was more than the risk allowed, and it is the
one number that says the risk was overrun. The two buckets above them are losses
that never reached the stop: **0…-0.5** and **-0.5…-1**. A bucket reads from
zero outwards and its far edge belongs to the next one, so exactly -1R is the
stop, not the bucket that stops short of it. The edge of 1.2 is the journal's
figure until you set your own: the slider on the **Past the stop** card,
below, moves it by a tenth between 1 and 2 R, and the buckets follow. At an edge
of exactly 1 the stop bucket is gone, and the last one reads **-1R and worse**.

Read together the two sides answer two questions: are the losses one size,
and do the wins reach far enough to pay for them. The R distribution of a
monthly or quarterly report is cut the same way, on the trades of that period.

**By weekday.** Among the tables: a tile for every day of the week with the
EV of the closed trades entered on it and how many there were, green above
zero and red under it, pale under three trades. Point at a tile for its
winrate and its R. Saturday and Sunday stand only when something was entered
on them.

**Equity.** Across the page under the charts: one curve per account, side
by side, each on its own scale, because the small moves of a small account
would vanish next to a 100k prop. The switch in the head picks a single
account, which is the account filter itself, so the whole page follows it.
The switch on the right reads the curve **by date** or **by trade**, one step
per closed trade. By date the calendar stretches a quiet month and squeezes a
busy day; by trade every trade takes the same room, which is how an equity
curve is usually looked at. Archived accounts are not drawn: the account is done
with and there is nothing left to watch. Their trades stay in every figure on
the page.

The dashed line across the chart is the balance the curve starts from: the
opening balance of the account, or the balance it entered the cut with. The
wash under the curve is green above that line and red below it, so which side
of the start the account is on is read before a single number is. A hollow dot
on the curve is money that moved outside a trade: a deposit, a withdrawal, a
fee. The dashed line steps with it, up at a deposit and down at a withdrawal,
so the wash stays what the trading did and taking money out does not paint the
account red. The numbers at the end of the line are the balance the curve ends
at, which is the balance now unless the page is cut to a period, and how far it
is from that line.

The line is drawn softly, and the curve is bent only between the points it
has, so a peak on the chart is a peak that happened. A close carries its hour
and is drawn at it. Exits written without
an hour on one day are laid out across that day in the order they were
closed, because stacking them on one x would make a vertical wall out of an
ordinary day.

With a **from month** filter on, or a cut to a period, the curve starts at the
balance the account entered it with: everything before is folded into the
first point, and a period also ends the curve where it ended. With a filter by
style, pair or direction, only the chosen trades move the line from there, so
the chart says what those trades alone did to the account.

**By playbook.** A row per playbook with its setups beneath it, the trades
under none last, with trades, WR, Σ R, EV, money, and the *clean* and *held*
shares. A row leads to the playbook's page. The Playbooks section above says
what the shares mean.

**What a rule costs.** Beside it, the report's table: every rule ticked as
not met in the selection with how many trades broke it and what they
brought, the dearest first, and under them the trades that kept every rule,
which is the measure.
Only trades that went through a checklist stand there, at the entry or at the
close; one tied to a playbook later and never ticked was never held against
its rules. When trades of more than one playbook are in the cut, the name of
the playbook stands before the number of the rule. **Past the stop**, a table
of its own: the losses that went deeper than the stop edge, worst first, ten
at most, each a way to its trade. Beside the R of each stands **over**, what
that loss cost past the edge, and the head of the card carries the total of
them. The stop itself is the attempt working as it was meant to, at -1R, and
commission and swap carry it to the edge, which the trade was still sized
for. What lies past that edge is the part discipline was there to keep, so
with the edge at 1.2 a loss back at -1.35R overran the risk by 0.15R rather
than by the whole of it.

**The stop edge is yours to set.** The slider in the head of the card runs
from 1 to 2 R by tenths and stands at 1.2 until you move it: how much a stop
with the fees on it may cost before the loss counts as an overrun. Release it
and the journal keeps the figure, in `journal/settings.md`, and every number
that hangs on it is worked out afresh on the next look: the buckets, this table
and its total, the mistakes of every report, the old months as much as the
new ones, since nothing computed is ever stored. A report built earlier keeps
the edge it was written with in its text; rebuild it to read it at the new one.

**Prices.** Among the tables, once closed trades carry an entry and a stop:
how many do, the RR planned on average, how often the market reached the
target whether it was taken or not, how far the trades went for you (MFE) and
against you (MAE) on average, and what a winner gave back on average from its
best to its exit. Every figure is in R by price, so pairs of any size stand
together.

**Stop at breakeven.** The trades whose stop you moved to the entry (the
Breakeven button, see The stop at breakeven) against the ones whose stop
stayed: the same figures as every table for each, so the two rows answer
whether moving the stop pays. Under them, how the moved trades ended, won, stopped at
the entry or lost after the move, and how soon after the entry the stop was
moved in the middle case, with the share of the hold that had passed. The
journal cannot tell whether a trade stopped at the entry would have gone on
to its target: that is read off the chart. A loss after the move means the
stop came back or the price gapped through it. The card stands only when the
cut holds a moved trade, and only trades moved since the button appeared
carry the mark.

**The tables.** By period, pair, style, account, direction, entry timeframe,
execution and time in the market, in two columns. A row of the period, pair,
style, account or direction table narrows the page to that value, and the
name of the cut at the top drops it again; the other three are cut by fields
the filter does not carry, so their rows carry no link. A table
whose value the page is already cut to is not drawn, since its one row would
only repeat the strip. Time in the market is counted in whole days between
the entry and the exit, because an exit is often written without an hour.

The cards from the playbooks down are dealt into the two columns by their
height, so that the columns end together whatever the journal put in them: a
long list of pairs, sixty weeks or ten losses past the stop changes which card
stands where; the shorter column is left with no empty ground under it.

**A selection with nothing closed in it says so.** Filter down to open
positions, or to a pair you have not traded in the months chosen, and the page
answers in one line instead of drawing a strip of hyphens and a curve made of
deposits.

## Money in and out

Money moves for reasons other than trades: you top an account up, you take a
payout, the broker charges a fee. All of that lives on the **Accounts** tab, in
the **Money and corrections** card. Both forms are folded away behind a line you
click: they are needed rarely, and the balances above are what the page is for.

Deposits, withdrawals and fees are under **Money in and out**; a correction has
its own fold below, with its own list. They are apart because one is money you
moved and the other is a difference you found.

Pick the account, pick what happened (**deposit**, **withdrawal** or **fee**),
type the amount as a plain positive number, set the date, the time if you know
it, and add a comment. With a time, the money counts from that moment: a
deposit made in the evening stays out of the risk of a trade opened that
morning. Without one it counts from the start of its day.
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

**Correcting a balance.** When the broker shows a different number, leave the
start balance and the old trades as they are. Open the **Correct a balance**
fold in the same card and type the balance the broker really shows; the
journal writes the difference down as a correction with your comment. The gap
becomes a record with a date, in `journal/adjustments/` with the kind
`reconciliation`, next to the deposits, withdrawals and fees. If there is
nothing to correct, the journal says so and writes nothing.

## Accounts and pairs

The **Accounts** tab.

- **Start balance** is the point the journal counts from. Opening an account
  today, put in today's real balance.
- **Currency** is shown next to every sum of the account: a sign for the usual
  ones ($, €, £, ¥), the code for the rest.
- **Kind**: a **broker** account holds your own money, a **prop** account is
  run under the rules of a firm. Pick it when you create the account; a prop
  account opens on its rules next. **Rules** in the row of any account opens
  them again.
- **The rules of a prop firm** differ from firm to firm, and between the
  challenge, the verification and the funded account of one firm, so the
  journal carries none of its own: copy them from your firm's page. A sum is
  money or a percent of the start balance, `5%` of 100 000 being 5 000, and a
  rule the firm does not have is left empty.
  - **daily loss limit**: the most one day of the firm may lose, counting the
    trades closed that day, the fees charged on it and what the open trades
    still put at risk at their stops;
  - **max loss** and how it is measured: *static* from the start balance, a
    floor that never moves; *trailing* under the highest balance the account
    has closed at; *trailing to start* the same until the floor reaches the
    start balance, where it stays;
  - **profit target**, what the account has to make, money moved in and out
    aside, and **min trading days**, the days a trade was entered on;
  - **the firm's day**: the hour it begins and on whose clock, since many firms
    count it from midnight in Prague or in New York. Empty is the journal's
    clock.

  Under the rules, the row of the account says where it stands against each,
  a line a rule: what the firm's day has already cost, fees included, with
  what the open trades still put at risk and the limit; the floor of the max
  loss and how far the balance stands above it, now and at the stops of the
  open trades; the target and how much of it is made; the trading days
  against the ones required; and when every rule is met, that the target is
  made. The lines turn amber at four fifths of a limit and red when one is
  reached.
- **The journal's clock** is the clock the times of your trades are written
  in. Empty is this computer's, which is right when you write the times you
  see on your own watch; a trader who copies them from a terminal running on
  another clock names that clock, so the day of a firm is cut in the right
  place. The downloaded file knows every clock. Run from the source on
  Windows, Python needs its `tzdata` package for the names
  (`py -m pip install tzdata`); without it the journal says the clock is
  unknown and counts on the computer's own.
- **Archive** keeps the account in the history and the statistics but stops
  offering it when a trade is opened. An account with trades or money
  movements cannot be deleted, only archived; one without them is deleted into
  `.trash` like everything else.
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
  order you trade them.

  Removing a word only stops the form offering it. The trades that carry it keep
  it: it stays in the filters, the statistics and the reports, it is still shown
  when that trade is edited, and the list on the Accounts tab shows it below the
  others, saying how many trades hold it, with an **Add** button to offer it
  again. That is how a style you stopped trading is retired without touching a
  single record.

  Every style you keep in the list gets a winrate tile of its own on the journal
  page, as soon as it has trades. **Winrate overall** counts every trade of the
  selection, whatever its style, retired or not.

## Reports

The **Reports** tab is a shelf: every quarter and month since your first closed
trade, newest first, each with the figures the journal holds for it now, whether
a report was built for it or not. Trades, then won / lost / break-even and, on
the running period, the positions open now in blue, WR, Σ R, EV, the **path
of R** (the running sum of R trade by trade, a small line from the first exit
of the period to the last, so a month that went up and gave half of it back
reads differently from one that climbed), money, and the daily cards written
against the days you took a trade on. A period with trades and no
report has a **Build** button in its row, blue on the one that is due, the
newest finished period with trades and no report. A period with a report is a
link to it, with the day its file was built and a blue dot once conclusions
are written; *rebuild* refreshes the file. The month and the quarter still
running are marked so.

Under the shelf stands every year **day by day**: a square a day, by the
exit, green for a day that made R, red for one that lost it, amber for one
that came out at zero, and the brighter the square the more. Point at a day
for its trades, its R and its money.

**A report counts the trades that closed in the period**, the way a broker
states a month and the cards count a day. The list of trades groups by entry,
so a row of a report and the list it opens can differ by a trade that ran
across the boundary.

**What is in a report.** The header leads to the report of the period before
and the one after, and for a month to its quarter, when those reports exist.
The page opens on the figures a review asks for first, one tile each, with
the period before in grey under the first three. The **result** in R, with
the money under it. The **winrate** with the EV, and the trades won, lost and
break-even by colour, with the positions open now in blue while the period
runs. The **deepest fall from a high**, how far the period went below its own
best point in R, because a month can end in plus and still have been a hard
one. The **mistakes**. The **process**, the daily cards written against the
days you took a trade on, with their grades; a day counts here by its
entries, so a position that closed by itself while you were away does not
turn that day into one owing a card. And the best and the worst trade by R,
each a link to the trade.

**Mistakes** are what the journal itself recorded as one: a rule ticked as
not met at the entry or at the close, or a loss at the stop edge and worse
(1.2 R until you set it on the Statistics tab), which means more was lost
than the risk written on the trade, whether by size, a moved stop or
slippage. A trade that did both counts once; a trade never ticked counts
neither way, and the tile says how many trades under a playbook were never
ticked. The count is plain ink and only the R of those trades is coloured,
because a report reports a month rather than grading it.

The **What a rule costs** card names every rule the trades did not meet,
among the trades ticked against the current version of their playbook: how
many trades broke it and what they brought, the costliest first, against the
last row, the trades that kept every rule. Under it, **Past the stop** lists
the losses that went deeper than the stop edge, each a link to the trade and
each with what it cost past the edge beside its R, and the total under the
table. The card stands whenever a trade of the period names a playbook or a
loss went past the stop.

**Process** counts the cards against the days traded and quotes the errors
written on them; when a stop was moved to breakeven in the period it adds one
sentence: on how many trades, how they ended, what they brought against the
trades whose stop stayed, and how soon the stop was moved. The sentence goes
into the saved file too.

**Trade by trade**, the tape, is every closed trade of the period as one bar,
in the order of the exits: a win stands up in green, a loss hangs down in
red, a break-even is an amber tick on the zero line, and a thin line marks
where a new week begins, or a new month in a quarter. The dashed line is the
stop, -1 R, and a bar that reaches past it lost more than the risk allowed.
Hover a bar for the trade, click it to open it. Beside the tape stands **the
R distribution** of the period, the same as on the Statistics tab.

**Day by day** lays the period out as a calendar on its back: a tile a day,
a column on every day that closed a trade, as tall as the R the day made or
lost, green for a day that made R and red for one that lost it. A quarter
shows its three months side by side on one scale, so a tall column in July
and one in September are the same size of day. Point at any day, the column
or the tile, for the trades it closed, the won and the lost, its R and its
money; a day with nothing closed says so. Days are counted by the exit, the
way the report counts its figures.

Then come **By playbook** with its setups beneath, when any trade names one,
and **Process**: the daily cards against the days you took a trade on, the
weekly cards of the period, the grades, the D and F days and the errors you
wrote on the cards, each a link to its card. Your **Conclusions** end the
story, an open field until they are written, then your text with an **Edit**
fold under it. Saving writes the figures and the text into
`journal/reports/<period>.md`, an ordinary markdown file you can read
anywhere, and a rebuild never overwrites the text. The page itself is always
the journal as it is now, so there is nothing to recalculate; the file
catches up when you save or press *rebuild* on the shelf.

After the story come the tables, dealt into two columns: the accounts with
the balance of each before and after the period, for a quarter its months,
each a link to its own report when one exists, and the cuts by pair, style,
direction, entry timeframe and execution format, every row with its trades,
WR, Σ R, EV and money, Σ R the one coloured column.

**Every row leads to its trades.** Click a pair, an account, a style or a
direction in the report tables and the journal opens filtered to it, over the
months of that report. That is how a row like "XAU, 5 trades, -4.56 R" turns
back into the five trades it was counted from, with the idea you wrote before
each entry. The best and the worst trade lead straight to the trade itself, a
playbook row to the playbook's page, and a bar of the tape to its trade. A
trade opened from a report has a button back to that report in its header,
and one opened from the Statistics tab, from a row of the list, a bar of the
tape or the best and worst tile, has a button back to the cut it came from.

**The trades of the month stand at the foot of the report**, the same card
the Statistics tab carries under a period cut: every trade the month closed,
newest exit first, with the exit and the entry side by side, thirty open and
the rest folded. The tape above says the shape of the month, and this list
says which trades made it. **The trades** in the header jumps down to it, and
a row opens its trade with the way back to this report. The list is worked
out from the journal on every look, like everything else on the page; the
file the report saves keeps the figures and your conclusions, since the
trades are already in the journal and a stored copy would be one more thing
to drift.

## Showing your journal to somebody

Sooner or later a trade has to be shown to another trader. **Share** makes
the one way out of this machine: a single file that holds the record and its
screenshots inside itself. It opens in any browser on
any computer, with no journal running and no network, and it can be sent the
way any file is sent.

**Share stands in four places.** On a trade, next to Edit: the trade whole,
the plan it followed and the setup it was taken under, the idea with its
screenshots by timeframe, the checklist with what was met and what was not and
why, the exit screenshot and your conclusions. On a plan, next to Edit as well: the
days and the pair, the narrative, the analysis with its screenshots, what was
to be done, the updates written while it ran, the review, and the trades tied
to the plan with their R, so that the reader sees what was expected and what
came of it. Over the list on the front page, next to CSV: whatever the
filters are showing right now, with the figures of that selection above it.
And on a report: the month or the quarter with its figures, your conclusions
and every trade it closed.

**You see what leaves before it leaves.** Share opens the document itself, with
one strip across the top: how much the file will weigh, whether the screenshots
go with it, and the **Download** button. The strip is not part of the file. On
a selection and a report you can drop the screenshots and send the figures
alone, which turns a file of forty megabytes into one of forty kilobytes; a
single trade or a plan always carries them, since they are the reason to show
it at all.
When the trades go in full, the file reads as pages: it opens on the report,
a line of the list opens its trade alone, and the head of the trade leads to
the list and to the trades before and after it. The browser's Back works
too. Printed, every page goes to paper, one trade a sheet.

**Download says what it is doing.** The file is put together the moment you
press it, and a big one takes a moment, so the button counts itself up
(*Building the file... 60%*) and says *Saved* when the browser has it. Pressing
it again while it works does nothing, and the whole journal with every
screenshot in it is the only case where the counting is worth watching.

**Money stays home.** The PnL of a trade, the risk in money, the balances
and the size of an account are left out of every document, and so is the
name of the account, since traders name accounts by their size. What travels
is R, the result measured against the risk you took, the percent the risk
was written as, and the words you wrote. This is how the document is built
rather than a switch: it carries only what it names, so a field added to a
trade tomorrow stays home as well.

**A PDF, when that is what is wanted.** Open the downloaded file and print
it, `Ctrl+P`, then save as PDF. The document has a print layout of its own:
white ground, dark text, and in a selection every trade starting its own
page. That is the way to a PDF that looks like the journal, and it needs
nothing installed.

**A document is a copy.** It holds the record as it was the moment you saved
it. Write another line into the trade and the file you already sent will not
know about it; make it again and send the new one.

## Search

The **Search** tab. A word or a phrase is looked for in everything you have
written: the ideas, conclusions and updates of trades, the analysis, plan,
updates and review of every plan, the text of every market note, the name,
intro, rules, setups, sections and review of every playbook, and every field
of every card, daily and weekly alike. Case does not
matter. Every hit is a link to the record, with the matching words shown in
the text around them, which is how the trade where you wrote "moved the stop
too early" three months ago is found again.

## Where the data lives

Everything is in the `journal/` folder: ordinary text files and PNG images. Run
from the source, that folder sits next to the code; the downloaded file and
the `plainbook` command of a pipx install keep it in `Plainbook` in your home
folder (`C:\Users\<you>\Plainbook`, `/Users/<you>/Plainbook`, `~/Plainbook`);
`PLAINBOOK_ROOT` points it anywhere else, see INSTALL.md.

    journal/trades/2026-08-30-01-eurusd/trade.md
    journal/trades/2026-08-30-01-eurusd/shots/*.png
    journal/cards/2026-08-30.md
    journal/cards/2026-W36.md
    journal/plans/2026-08-31-eurusd/plan.md
    journal/plans/2026-08-31-eurusd/shots/*.png
    journal/notes/2026-09-06-sweep-before-the-london-open/note.md
    journal/notes/2026-09-06-sweep-before-the-london-open/shots/*.png
    journal/playbooks/pullback/playbook.md
    journal/playbooks/pullback/versions/1.0.md
    journal/playbooks/pullback/shots/*.png
    journal/accounts/*.md
    journal/adjustments/*.md
    journal/reports/2026-08.md
    journal/reports/2026-Q3.md
    journal/vocabulary.md      the styles, timeframes and execution formats the form offers
    journal/pairs.md           the pairs the form offers
    journal/settings.md        the stop edge

The files open in any text editor and read by eye. There is no database and
no format of its own, so if the program breaks tomorrow, the records are
still yours in the same shape.

Two service folders sit next to the journal: `.trash` (what was deleted) and
`.drafts` (screenshots from forms that were never submitted, swept after a day).

**A backup** is a copy of the `journal/` folder. A git repository of its own
in the data folder keeps the history as well; the records are never part of
the program's repository. A copy on an external drive is worth having too.

## When something goes wrong

- **The page does not open.** The server is not running. Start it the way it
  was installed: the downloaded file by a double-click, `plainbook` after a
  pipx install, `python3 -m plainbook.server` in the program folder from the
  source; on Linux with the unit, `systemctl --user restart plainbook`.
- **A screenshot did not paste.** Nothing happens when the clipboard holds a
  file or a link instead of a picture; copy the picture itself and paste
  again. The journal speaks up only when a picture was taken and could not be
  saved.
- **A page says the record could not be read.** Its file was edited by hand
  and something in it does not parse; the page names the file and the reason
  and leads back to the list. The reports and the shelf name such a card the
  same way and leave it out of their figures.
- **A page says there is no such trade, plan or note.** The address leads
  nowhere: the record was moved to the trash, or its folder was renamed when
  its date or pair was edited. The list of its tab has the current address.
- **A yellow box at the top of every page says a record could not be read.**
  A file was edited by hand and something in it does not parse: a date written
  the wrong way round, a letter in a number, a header without its closing
  line. The box names the file and the reason; everything else keeps working
  and the figures simply leave that record out until it is fixed. From the
  terminal, `python3 tools/check_journal.py` prints the same list, for the
  folder that holds `journal/` given as an argument, or for `PLAINBOOK_ROOT`
  when none is given.
- **Deleted the wrong thing.** The Trash card on the Accounts tab, **Restore**.
- **Port 8778 is taken.** Set another one through `PLAINBOOK_PORT`.
