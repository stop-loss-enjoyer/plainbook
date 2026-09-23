# Contributing

Thanks for looking. This is a small program that stays small on purpose, so
the bar for adding things is high and the bar for fixing things is low.

## Before anything else

**Somebody's trading history is on the other end of this code.** Never write
sample records, screenshots or balances into the repository, and never add
anything that sends data anywhere. `python3 tools/check_public.py` refuses a
push that would leak records; do not work around it.

## Reporting a bug

Open an issue with:

- what you did, what you expected, what happened;
- the version, which stands next to the name on every page, and your Python
  version if you run from the source;
- the server log if it crashed. On Linux, `journalctl --user -u plainbook -n 50`.

Please do not paste real trades into an issue. A synthetic example that shows
the same problem is more useful anyway.

## Pull requests

- **Keep it dependency-free.** The Python standard library is the whole toolbox.
  A pull request that adds a package will be declined however good the package is.
- **One change per pull request**, with a message that says *why*, because
  the diff already says what.
- **Run the tests**: `python3 -m unittest discover -s tests`. Add one for the
  behaviour you changed; the suite is fast and has no fixtures to fight with.
  `git config core.hooksPath .githooks` turns on the pre-push hook that runs
  the record guard before every push, the same check CI runs.
- **Look at the page you changed.** About half of this code is markup and one
  form script, and the tests do not see any of it.
- Match the surrounding style. A comment explains the reason for a decision;
  the line below it already shows the mechanics.
- **No long dashes** in text, comments or the interface. Use a comma, a colon,
  a semicolon or a full stop; an empty value on a page is a plain hyphen.
  `tools/check_public.py` checks this along with everything else.

## Things that will be declined

These may be good ideas, and they belong to another project:

- broker or exchange integrations, automatic trade import;
- cloud sync, logins, multi-user, a shared server;
- a front-end framework or a build step of any kind;
- storing anything that can be computed, such as a balance or an R in a file.

A fork is welcome for any of them.

## The shape of the code

    plainbook/model.py        the records: trade, account, adjustment, card, week, plan, playbook, note
    plainbook/mdfile.py       the markdown header format
    plainbook/store.py        files <-> objects, the folder layout, the trash
    plainbook/balances.py     balances and R, computed by replaying history
    plainbook/stats.py        summaries, the equity curve, the R distribution
    plainbook/reports.py      monthly and quarterly reports
    plainbook/html.py         the palette, the CSS, the page shell and the SVG charts
    plainbook/flags.py        the round flag icons of a trading symbol
    plainbook/share.py        the document a record leaves in, with no money in it
    plainbook/server.py       the routes, the pages and the forms
    plainbook/__main__.py     python3 -m plainbook
    tools/check_public.py     the guard that keeps records out of the repository
    tools/check_journal.py    does every record in a journal read
    tools/demo_journal.py     an invented journal for screenshots and for looking at a change
    tools/attach_playbook.py  ties the trades a playbook was already traded by to it
    tools/import_csv.py       old trades brought in from a CSV table
    tools/app_entry.py        the entry of the downloaded file
    tools/browser_check.mjs   the form scripts driven in a headless Chromium

The full map, with what each file owns, is section 3 of [AGENTS.md](AGENTS.md).

Two traps are worth knowing before you touch a form. A trade's `shots/`
folder is rewritten whole from what the form sent, so a form that edits a
trade must send back every screenshot zone it did not show. And a header key
with no value parses into an empty list rather than an empty string. Both are
spelled out in [AGENTS.md](AGENTS.md), which is written for coding agents and
reads fine for people.
