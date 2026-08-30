# TradingJournal

A local trading journal. The person using it is a trader, not a developer: talk
in their language, show the result rather than the code.

**If the journal is not installed on this machine yet, start with
[INSTALL.md](INSTALL.md).** How it is built and what the files look like:
[README.md](README.md). How the owner uses it day to day: [GUIDE.md](GUIDE.md) —
point at it when they ask "how do I…", and keep it current when something new
appears. What changed: [CHANGELOG.md](CHANGELOG.md).

## Working rules

- **The data in `journal/` is the source of truth.** Trades and cards are
  entered through the web interface (http://localhost:8778); do not edit the
  files by hand unless asked directly — and then run the tests and check that
  the server still renders the page.
- **The records never leave the machine.** No uploads to a cloud, to another
  service or into a chat without the owner asking for it. Do not quote the
  contents of trades without need — summary figures answer almost every question.
- **Nothing is shredded.** Deleting a trade or a card in the journal means
  moving it to `.trash`. If you delete something yourself, do the same.
- **Where the records live** is `TJ_ROOT`, the project folder by default. When
  the code is under git and the records are kept apart, the data folder has a
  repository of its own — it is private and is never pushed anywhere. Never
  commit records into the code repository.
- **After changing the code**: `python3 -m unittest discover -s tests`, then
  restart the server (Linux: `systemctl --user restart trading-journal`;
  otherwise restart the `tj.server` process). Check interface changes with your
  eyes, not only with tests: half the code is markup and the form script, and
  the tests do not see them.
- **The balance does not match the real one** — do not change the start balance
  and do not quietly edit trades: the gap is written down as an adjustment
  (`reconciliation`, `fee`, `deposit`, `withdrawal`) in `journal/adjustments/`,
  with a comment saying why.
- Port 8778 (`TJ_PORT` changes it). The server listens on 127.0.0.1 only — it
  has to stay that way.

## Things worth knowing about the build

- **Nothing computable is stored in the files.** Balance and R are worked out on
  every load (`tj/balances.py`). Do not add a "balance" or an "R" field to a
  record — that is the straight road to data that disagrees with reality.
- **A trade's shots folder is rewritten whole** from what the form sent
  (`apply_shots`). So every form that edits a trade must send back all of its
  screenshot zones — otherwise the ones it did not show disappear from the disk.
  That has already happened once with the exit screenshots.
- **Winrate** = wins / (wins + losses); break-evens are out of the denominator,
  while "trades" and the average R count every closed trade. If you change that,
  change it in `stats.Summary`, in the reports and in the captions at once, or
  the numbers start arguing with each other.
- **No dependencies.** The Python standard library only, everything offline: no
  CDN, no fonts, no analytics. Keep it that way.
- **A header key with no value** parses into an empty list, not an empty string
  (that is how lists are written). Read header strings through `store._text`,
  and do not write empty values into a header.
