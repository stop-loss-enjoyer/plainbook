#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bring old trades in from a table: the CSV that Notion exports, or any other
spreadsheet saved as CSV. Every row becomes one trade, written the way the
interface writes it, so afterwards they are ordinary trades.

    python3 tools/import_csv.py trades.csv --root ~/plainbook-data \\
        --account broker --pair Pair --direction Direction --style Style \\
        --entry "Entry date" --exit "Exit date" --result Result --pnl PnL \\
        --risk "Risk %" --idea Idea --id "Notion id" --dry-run

Each option after the file names the column of the table that holds the field.
Only --account, --pair, --direction, --style and --entry have to be there; the
rest are optional. --account takes a fixed account id, or with --account-column
the column that names the account and --accounts to translate its words:
"Bybit=broker,FTMO 100k=prop-100k". Every account must already exist in the
journal (the Accounts tab), with the balance it had before the first trade
being imported, and NOT its balance today: the journal replays the trades from
that figure, and the difference to today's real balance is written afterwards
as a reconciliation on the Accounts tab.

Nothing is written until every row has been read and checked: a row that does
not read is named with its number and the reason, and the run stops with the
journal untouched. --dry-run does the same reading and prints the summary
without writing. The run is safe to repeat: a row whose id (the --id column)
is already in the journal is skipped, and without an id column a row is
skipped when a trade with the same account, entry date, pair and PnL exists.

Pictures: --pictures names a column with file names, one or several separated
by commas (Notion writes "name.png (https://...)", the address is dropped), and
--pictures-dir the folder to look for them in, any depth. Every picture found
is copied into the trade's shots folder and shown under its idea; the names
not found are counted and named in the summary.

The summary prints only figures: how many rows, how many written, per account
the count and the sum of PnL, and the first and the last entry date. Nothing
from the rows themselves is printed.
"""
import argparse
import csv
import os
import re
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import store
from plainbook.model import (PAIR_NOT_SET, IdeaBlock, RecordError, Trade)

RESULT_WORDS = {
    "win": "Win", "won": "Win", "profit": "Win", "tp": "Win", "w": "Win",
    "lose": "Lose", "loss": "Lose", "lost": "Lose", "sl": "Lose", "l": "Lose",
    "be": "BE", "b/e": "BE", "break even": "BE", "break-even": "BE",
    "breakeven": "BE", "0": "BE", "flat": "BE",
}
DIRECTION_WORDS = {"long": "long", "buy": "long", "l": "long",
                   "short": "short", "sell": "short", "s": "short"}
DATE_FORMATS = ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d",
                "%B %d, %Y %I:%M %p", "%B %d, %Y",
                "%d.%m.%Y %H:%M", "%d.%m.%Y", "%d/%m/%Y %H:%M", "%d/%m/%Y",
                "%m/%d/%Y %I:%M %p", "%m/%d/%Y"]
TIMED = {f for f in DATE_FORMATS if "%H" in f or "%I" in f}


class RowError(Exception):
    pass


def parse_date(text):
    """A date from the table, and whether it carried an hour.

    Notion writes a range as "start → end"; the start is taken, the end is
    read by the caller from the same cell when the exit column is this one."""
    text = (text or "").strip()
    if not text:
        return None, False
    if "→" in text:
        text = text.split("→")[0].strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt), fmt in TIMED
        except ValueError:
            continue
    raise RowError(f"cannot read the date {text!r}")


def parse_range_end(text):
    """The end of a Notion range "start → end", or None when there is none."""
    text = (text or "").strip()
    if "→" not in text:
        return None, False
    return parse_date(text.split("→", 1)[1])


def parse_money(text):
    """A number out of "1 234,50 $", "-$120", "+3.2" and the like."""
    text = (text or "").strip()
    if not text:
        return None
    clean = re.sub(r"[^\d,.\-+]", "", text)
    if clean.count(",") and not clean.count("."):
        clean = clean.replace(",", ".")
    clean = clean.replace(",", "")
    try:
        return float(clean)
    except ValueError:
        raise RowError(f"cannot read the number {text!r}")


def word(table, text, what):
    key = (text or "").strip().lower()
    if key not in table:
        raise RowError(f"cannot read the {what} {text!r}")
    return table[key]


def picture_names(text):
    """The file names in a Notion files cell: "a.png (https://...), b.png"."""
    names = []
    for part in (text or "").split(","):
        part = re.sub(r"\(https?://[^)]*\)", "", part).strip()
        if part:
            names.append(os.path.basename(part))
    return names


def find_file(folder, name):
    for base, _, files in os.walk(folder):
        if name in files:
            return os.path.join(base, name)
    return None


def read_rows(args):
    """Every row as a Trade that passed its checks, plus its pictures.

    Returns [(row number, Trade, [picture paths], [names not found])]."""
    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        for option in ("pair", "direction", "style", "entry", "exit", "result",
                       "pnl", "risk", "entry_tf", "idea", "conclusions", "note",
                       "id", "pictures", "account_column"):
            column = getattr(args, option)
            if column and column not in header:
                raise SystemExit(f"no column {column!r} in the table; "
                                 f"the columns are: {', '.join(header)}")
        rows = list(reader)

    accounts = {}
    for pair in (args.accounts or "").split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            accounts[k.strip().lower()] = v.strip()

    out, problems = [], []
    for n, row in enumerate(rows, 2):            # 1 is the header line
        try:
            out.append((n,) + build(row, args, accounts))
        except (RowError, RecordError, ValueError) as e:
            problems.append((n, str(e)))
    if problems:
        for n, why in problems:
            print(f"row {n}: {why}")
        raise SystemExit(f"{len(problems)} row(s) could not be read, "
                         f"nothing was written")
    return out


def build(row, args, accounts):
    if args.account_column:
        name = (row.get(args.account_column) or "").strip()
        account = accounts.get(name.lower(), name)
    else:
        account = args.account
    if not account:
        raise RowError("no account")
    opened, opened_time = parse_date(row.get(args.entry))
    if opened is None:
        raise RowError("no entry date")
    closed, closed_time = None, False
    if args.exit:
        if args.exit == args.entry:
            closed, closed_time = parse_range_end(row.get(args.entry))
        else:
            closed, closed_time = parse_date(row.get(args.exit))
    result = (word(RESULT_WORDS, row.get(args.result), "result")
              if args.result and (row.get(args.result) or "").strip() else None)
    pnl = parse_money(row.get(args.pnl)) if args.pnl else None
    if result is not None and pnl is None:
        pnl = 0.0 if result == "BE" else None
    if result is not None and closed is None:
        closed, closed_time = opened, opened_time
    risk = parse_money(row.get(args.risk)) if args.risk else None
    pair = (row.get(args.pair) or "").strip().upper().replace("/", "") or PAIR_NOT_SET
    t = Trade(
        id="pending", account=account, pair=pair,
        direction=word(DIRECTION_WORDS, row.get(args.direction), "direction"),
        style=(row.get(args.style) or "").strip(),
        entry_tf=(row.get(args.entry_tf) or "").strip() if args.entry_tf else "",
        risk=risk if risk else args.risk_default,
        opened=opened, opened_time=opened_time,
        result=result, pnl=pnl, closed=closed, closed_time=closed_time,
        note=(row.get(args.note) or "").strip() if args.note else "",
        conclusions=(row.get(args.conclusions) or "").strip() if args.conclusions else "",
        notion_id=(row.get(args.id) or "").strip() if args.id else "")
    idea = (row.get(args.idea) or "").strip() if args.idea else ""
    if idea:
        t.idea.append(IdeaBlock(tf=t.entry_tf, text=idea))
    t.check()
    pictures, missing = [], []
    if args.pictures:
        for name in picture_names(row.get(args.pictures)):
            path = find_file(args.pictures_dir, name) if args.pictures_dir else None
            (pictures if path else missing).append(path or name)
    return t, pictures, missing


def already_there(existing, t):
    if t.notion_id:
        return t.notion_id in existing["ids"]
    return (t.account, t.opened.date(), t.pair, t.pnl) in existing["keys"]


def write(root, t, pictures):
    """The trade as the interface would write it: an id of the day, the
    pictures under its first idea block."""
    t.id = store.new_id(root, t.opened, t.pair)
    if pictures:
        if not t.idea:
            t.idea.append(IdeaBlock(tf=t.entry_tf, text=""))
        folder = store.shots_dir(root, t.id)
        os.makedirs(folder, exist_ok=True)
        t.idea[0].images = []
        for i, src in enumerate(pictures, 1):
            ext = os.path.splitext(src)[1].lower() or ".png"
            name = f"idea-01-{i:02d}{ext}"
            shutil.copyfile(src, os.path.join(folder, name))
            t.idea[0].images.append(f"{store.SHOTS}/{name}")
    store.save_trade(root, t)
    return t


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", help="the table, a CSV file")
    p.add_argument("--root", default=os.environ.get("PLAINBOOK_ROOT") or ".",
                   help="the journal folder (PLAINBOOK_ROOT, or the current one)")
    p.add_argument("--account", help="the account id every row goes to")
    p.add_argument("--account-column", help="the column that names the account")
    p.add_argument("--accounts", help='words of that column to ids: "Bybit=broker,Prop=prop-100k"')
    for option, text in (("pair", "the pair"), ("direction", "long or short"),
                         ("style", "the style"), ("entry", "the entry date"),
                         ("exit", "the exit date (the entry column, for a Notion range)"),
                         ("result", "Win, Lose or BE"), ("pnl", "the PnL in money"),
                         ("risk", "the risk in percent"), ("entry-tf", "the entry timeframe"),
                         ("idea", "the idea text"),
                         ("conclusions", "the conclusions written after the exit"),
                         ("note", "a note"),
                         ("id", "an id of the row, kept as the notion id"),
                         ("pictures", "file names of the screenshots")):
        p.add_argument(f"--{option}", metavar="COLUMN", help=text)
    p.add_argument("--pictures-dir", help="where the screenshot files are")
    p.add_argument("--risk-default", type=float, default=1.0,
                   help="the risk of a row without one (default 1)")
    p.add_argument("--dry-run", action="store_true", help="read and report, write nothing")
    args = p.parse_args(argv)
    for must in ("pair", "direction", "style", "entry"):
        if not getattr(args, must):
            p.error(f"--{must} is required")
    if not args.account and not args.account_column:
        p.error("--account or --account-column is required")

    root = os.path.abspath(args.root)
    known = set(store.all_accounts(root))
    rows = read_rows(args)
    unknown = sorted({t.account for _, t, _, _ in rows} - known)
    if unknown:
        raise SystemExit(f"no such account in the journal: {', '.join(unknown)}; "
                         f"create it on the Accounts tab first")

    old = store.all_trades(root)
    existing = {"ids": {t.notion_id for t in old if t.notion_id},
                "keys": {(t.account, t.opened.date(), t.pair, t.pnl) for t in old}}
    rows.sort(key=lambda r: (r[1].opened, r[0]))
    written, skipped, pictures_in, missing = 0, 0, 0, []
    per_account = {}
    dates = []
    for n, t, pictures, lost in rows:
        if already_there(existing, t):
            skipped += 1
            continue
        if not args.dry_run:
            write(root, t, pictures)
        written += 1
        pictures_in += len(pictures)
        missing.extend(lost)
        count, total = per_account.get(t.account, (0, 0.0))
        per_account[t.account] = (count + 1, total + (t.pnl or 0.0))
        dates.append(t.opened)

    if not args.dry_run and written:
        styles = store.all_words(root, "styles")
        new_styles = [t.style for _, t, _, _ in rows if t.style not in styles]
        if new_styles:
            store.save_words(root, "styles", styles + sorted(set(new_styles)))
        pairs = set(store.all_pairs(root)) | {t.pair for _, t, _, _ in rows
                                              if t.pair != PAIR_NOT_SET}
        store.save_pairs(root, pairs)

    verb = "would write" if args.dry_run else "written"
    print(f"{len(rows)} rows read, {written} {verb}, {skipped} already in the journal")
    for account, (count, total) in sorted(per_account.items()):
        figure = f"{total:+,.2f}".replace(",", " ")
        print(f"  {account}: {count} trades, PnL {figure}")
    if dates:
        print(f"  from {min(dates):%d.%m.%Y} to {max(dates):%d.%m.%Y}")
    if args.pictures:
        print(f"  {pictures_in} pictures attached, {len(missing)} not found")
        for name in missing[:20]:
            print(f"    missing: {name}")
    if not args.dry_run and written:
        print("now: python3 tools/check_journal.py, then correct the balance on the "
              "Accounts tab if it differs from the real one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
