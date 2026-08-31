# Contributing

Thanks for looking. This is a small, deliberately plain program, and it stays
that way: the bar for adding things is high, the bar for fixing things is low.

## Before anything else

**Somebody's trading history is on the other end of this code.** Never write
sample records, screenshots or balances into the repository, and never add
anything that sends data anywhere. `python3 tools/check_public.py` refuses a
push that would leak records; do not work around it.

## Reporting a bug

Open an issue with:

- what you did, what you expected, what happened;
- the version (`git describe --tags`) and your Python version;
- the server log if it crashed. On Linux, `journalctl --user -u plainbook -n 50`.

Please do not paste real trades into an issue. A synthetic example that shows
the same problem is more useful anyway.

## Pull requests

- **Keep it dependency-free.** The Python standard library is the whole toolbox.
  A pull request that adds a package will be declined however good the package is.
- **One change per pull request**, with a message that says *why* rather than
  *what*, because the diff already says what.
- **Run the tests**: `python3 -m unittest discover -s tests`. Add one for the
  behaviour you changed; the suite is fast and has no fixtures to fight with.
- **Look at the page you changed.** About half of this code is markup and one
  form script, and the tests do not see any of it.
- Match the surrounding style: comments explain the reason for a decision, not
  the mechanics of the line below them.
- **No long dashes** in text, comments or the interface. Use a comma, a colon,
  a semicolon or a full stop; an empty value on a page is a plain hyphen.
  `tools/check_public.py` checks this along with everything else.

## Things that will be declined

Not because they are bad ideas, but because they are not this project:

- broker or exchange integrations, automatic trade import;
- cloud sync, accounts, multi-user, sharing;
- a front-end framework or a build step of any kind;
- storing anything that can be computed, such as a balance or an R in a file.

If you want those, forking is a perfectly friendly thing to do.

## The shape of the code

    plainbook/model.py      the records: trade, account, adjustment, card
    plainbook/mdfile.py     the markdown header format
    plainbook/store.py      files <-> objects
    plainbook/balances.py   balances and R, computed by replaying history
    plainbook/stats.py      summaries, the equity curve, the R distribution
    plainbook/reports.py    monthly and quarterly reports
    plainbook/html.py       the palette, the CSS and the SVG charts
    plainbook/server.py     the routes, the pages and the forms

Two traps worth knowing before you touch a form: a trade's `shots/` folder is
rewritten whole from what the form sent, so a form that edits a trade must send
back every screenshot zone it did not show; and a header key with no value parses
into an empty list, not an empty string. Both are spelled out in
[CLAUDE.md](CLAUDE.md), which is written for coding agents but reads fine for
people.
