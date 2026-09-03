# Agent guide

This project is meant to be kept by a coding agent. Not tolerated by one, but
built for it: no dependencies to resolve, no build step to wait for, a test
suite that finishes in under a second, and every rule that matters written down
here instead of living in someone's head.

Read this before you touch anything. It is short on purpose.

If you are working through Claude Code, `CLAUDE.md` points here. Other tools
read this file directly.

---

## 1. Whose data this is

The owner's trading history sits behind this code: every position, its size and
the thinking behind it. Treat it the way you would treat someone's medical
records.

- **Never send records anywhere.** Not to a cloud, not to a paste service, not
  into a chat, not into an issue. Summary figures answer nearly every question;
  quote a trade only when the owner asked about that trade.
- **Never commit records.** `python3 tools/check_public.py` refuses a push that
  would leak them, and it runs as a pre-push hook and in CI. Do not work around
  it. If it fires, it is right and you are wrong.
- **Never delete outright.** Removing a trade or a card means moving it to
  `.trash`. If you delete something yourself, do the same.
- **Never rewrite history to fix a number.** A balance that disagrees with the
  broker is recorded as an adjustment in `journal/adjustments/` with a comment,
  not by editing old trades.
- **Screenshots are records too.** They are chart captures the owner took; the
  same rules apply.

## 2. Running it

```bash
python3 -m unittest discover -s tests    # the whole suite, ~1 s
python3 tools/check_public.py            # nothing private in the tree
python3 tools/check_journal.py [root]    # does every record read
python3 -m plainbook.server              # http://localhost:8778
```

After changing the code, restart the server. On Linux with the unit installed:

```bash
systemctl --user restart plainbook
journalctl --user -u plainbook -n 50     # the traceback when a page 500s
```

To try something without touching the owner's records, point the journal at a
scratch folder:

```bash
PLAINBOOK_ROOT=/tmp/pb-test PLAINBOOK_PORT=8899 python3 -m plainbook.server
```

## 3. The map

| file | owns |
|---|---|
| `plainbook/model.py` | the records: `Trade`, `Account`, `Adjustment`, `Card`, `Week`, `Plan`; the vocabularies a journal starts with; the checks |
| `plainbook/mdfile.py` | the markdown header format, and only that |
| `plainbook/store.py` | files ↔ objects, the folder layout, ids, the trash, the owner's lists of pairs and words |
| `plainbook/balances.py` | balances and R, computed by replaying history |
| `plainbook/stats.py` | summaries, the equity curve, the R distribution |
| `plainbook/reports.py` | monthly and quarterly reports |
| `plainbook/html.py` | the palette, the CSS, the page shell, the SVG charts |
| `plainbook/flags.py` | the round flag icons of a trading symbol, and what a symbol is taken apart into |
| `plainbook/server.py` | routes, pages, forms: everything HTTP |
| `tools/check_public.py` | the guard that keeps records out of the repository |
| `tools/check_journal.py` | loads every record the way the server does and names the ones that do not read |
| `tools/demo_journal.py` | an invented journal for screenshots and for looking at a change |

The dependency direction is one way: `server → html → flags`, `server → stats,
reports, balances, store → model → mdfile`. Nothing points back up. If you find
yourself importing `server` from anywhere, the design has gone wrong.

Routes live in `Handler.do_GET` and `Handler.do_POST` at the bottom of
`server.py`, and they are a flat list of `if` statements on purpose, so that the
whole routing table fits on one screen and needs no framework to read.

## 4. Invariants

Break one of these and something breaks quietly, days later, in the owner's
data. Each one is followed by what it prevents.

1. **Nothing computable is stored.** Balance and R are worked out on every load.
   *Prevents:* a stored number drifting away from the history that produced it.
2. **A trade's `shots/` folder is rewritten whole** from what the form sent
   (`apply_shots`). Every form that edits a trade must therefore send back
   **all** of its screenshot zones, including the ones it does not display.
   *Prevents:* screenshots vanishing off the disk when an unrelated field is
   edited. This has already happened once, to the exit shots.
3. **A header key with no value parses into an empty list, not an empty
   string**, which is how lists are written in the format. Read header strings
   through `store._text`, and never write an empty value into a header.
   *Prevents:* `float('[]')` killing the page, and `"[]"` showing up in the
   interface.
4. **Win rate = wins / (wins + losses)**, break-evens excluded; "trades" and
   average R count every closed trade. It is defined in `stats.Summary` and
   repeated in the reports and in the captions.
   *Prevents:* two numbers on the same screen disagreeing about the same trades.
5. **The server binds 127.0.0.1 and has no authentication.** Keep it that way,
   and keep the `Origin` check in `_same_origin`.
   *Prevents:* a journal with no login ending up reachable from a network.
6. **No dependencies.** The standard library is the whole toolbox. A package
   that looks harmless today is an install failure in five years.
7. **Everything is offline.** No CDN, no web fonts, no analytics, no update
   check. Styles and scripts are inlined into the page.
8. **Ids are file names.** Anything arriving from a URL and used as a path goes
   through `store.safe_dir_name` first.
9. **The lists in `journal/vocabulary.md` are what the form offers, not what a
   trade is allowed to hold.** Styles, timeframes and execution formats are the
   owner's, so a word taken out of a list must still load, still show in the
   statistics, and still be drawn in the form of a trade that carries it
   (`server.offered`). Nothing validates a trade against these lists.
   *Prevents:* retiring a style quietly deleting it from the trades that have
   it, since a form deletes what it does not draw.
10. **A record that does not read is named, not fatal.** Every reader in
    `store.py` takes a `problems` list (`store._load`): a file that fails is
    written there as (path, reason) and skipped, `Journal.load` collects the
    list, and `server.page` shows it on every page. Without the list the error
    is raised, which is what the tests and the checking tool want.
    *Prevents:* one mistyped date leaving every page blank with the reason only
    in the log, which is what happened before 1.4.3.

## 5. Recipes

**Add a field to a trade.** `model.py`: the dataclass field and an entry in
`TRADE_KEYS` (the tuple is `(attribute, header key)`); a rule in `check()` if it
can be wrong. `store.py`: write it in `trade_to_text`, read it in
`text_to_trade`. `server.py`: the input in `trade_form`, the read in
`apply_fields`, a row in `trade_page`. Then a round-trip test in
`tests/test_store.py`. Old files without the key must still load, which is what
`extra` and the `.get` defaults are for.

**Touch the screenshots of a record.** A trade and a plan both keep pictures in
a `shots` folder inside their own directory, and both go through the same three
functions: `zone_sources` reads a zone of the form, `apply_shots` rewrites the
folder whole, `shot_in_zone` draws a thumbnail. They take the record's folder
and the address its pictures are served from, never a trade, so a third kind of
record with screenshots needs no new code here.

A form that shows **one** zone of a record must not call `apply_shots`: the
rewrite would take every picture the form does not draw (invariant 2). The
update form on the plan page is such a form, and it uses `add_shots`, which
copies the new pictures in under the first free numbers and touches nothing
else. A picture that lives inside a text is kept there as `![](shots/name.png)`;
`place_shots` puts the new names back where the old ones stood after a rewrite,
and `with_shots` draws them on the page.

**Add a page.** A function returning `H.page(title, body, tab, header_right)`,
one `if` in `do_GET`, and a tab in the `links` list in `html.page` if it belongs
in the navigation. Anything user-supplied goes through `esc()`.

**Change the look.** Everything visual is in `html.py`: the palette constants at
the top, then one `CSS` string. The one exception is `flags.py`, which draws the
coins of a trading symbol; `html.pair()` is what a page calls, and anything that
prints a pair should call it instead of `esc()`. Class names are English and
short (`card`, `tile`, `dropzone`, `shot`, `num`). The theme is deliberately
flat: no gradients, no shadows except the one on the filter popover, no
animation.

**Add a statistic.** `stats.py` computes, `server.py` displays. Keep the
computation free of HTML and the display free of arithmetic; that split is why
the numbers can be tested at all.

**Change the record format.** Write a migration script in `tools/` and run it on
a *copy* of the journal first. Then compare every computed figure before and
after: trade count, balances per account, Σ R, Σ PnL, screenshot counts, the
length of every text field. They must match exactly, or the migration is wrong.
Only then touch the real journal, and say so in `CHANGELOG.md`. Make the script
idempotent: running it twice must be a no-op, because it will be run twice.

## 6. Verifying a change

In this order, every time:

1. `python3 -m unittest discover -s tests`, all green.
2. `python3 tools/check_public.py`, clean.
3. **Look at the page.** About half of this code is markup and one form script,
   and the tests go around the browser entirely. A headless screenshot is enough:
   `chromium --headless --screenshot=/tmp/page.png --window-size=1400,1000 http://localhost:8778/`
4. If you touched the paste-a-screenshot path, drive it in a real browser. It is
   the one place where browser script does the work, and it is the one place
   that has broken twice.
5. Restart the server and load the page you changed.

## 7. Conventions

- **No long dashes.** Not in the documents, not in the comments, not in the
  interface. A comma, a colon, a semicolon or a full stop carries the same
  clause, and an empty value in the interface is a plain hyphen.
  `check_public.py` fires on the character, so the rule cannot quietly lapse.
- **Commit messages say why**, not what, because the diff already says what. A
  subject line, a blank line, then the reasoning. **In English**: a commit
  message is published text, sitting next to every file on the repository page.
- **`CHANGELOG.md` gets a line** for anything a user would notice, phrased as
  what changed for them.
- **`GUIDE.md` gets updated** when the interface changes. It is the owner's
  manual; an out-of-date manual is worse than none.
- **Comments explain the reason**, never the mechanics. `# closewindow does not
  work from a Lua config` earns its place; `# loop over trades` does not.
- Keep functions small enough to read whole. There is no linter here and no
  formatter; match the surrounding style.

## 8. Traps that have already bitten

Real bugs from this project's history. They are here because each one cost time
and none of them was obvious from the code.

- **A token read too early.** The paste handler took the form token at the top
  of the script; the token was set by a script further down the page. Every
  upload went out as `token=undefined`. *Lesson:* read from the DOM when you
  need the value, not when the script parses.
- **A form that hid a field deleted it.** See invariant 2.
- **A window matched by title.** The desktop toggle looked for a window whose
  title starts with the app name, which is also the title of a file manager
  opened on the project folder. It raised the folder instead of the journal.
  *Lesson:* match windows by class.
- **An empty header key.** See invariant 3.
- **Drafts that never expired.** Screenshots pasted into a form that was never
  submitted stayed forever. *Lesson:* anything written outside a record needs an
  owner and an expiry.
- **A test that looked for prose found it in the CSS.** A test asserted that a
  warning phrase was absent from a page, and the phrase sat in a stylesheet
  comment that every page carries. *Lesson:* assert on markup (`class="notice"`),
  not on words.
- **Two names for one thing.** A local variable named `page` shadowed the
  `page()` function in the same routine, and every route that had both died
  with an UnboundLocalError. *Lesson:* a wrapper takes the name of what it
  wraps only when nothing else in the file has it.
