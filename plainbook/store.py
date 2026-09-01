#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reading and writing the journal: files <-> objects from model.py.

Layout (the source of truth, all under git):

    journal/accounts/bybit.md
    journal/trades/2025-06-25-01-eurusd/trade.md
    journal/trades/2025-06-25-01-eurusd/shots/*.png
    journal/cards/2026-08-30.md
    journal/adjustments/2026-08-29-reconciliation-bybit.md
    journal/reports/2026-08.md

A trade body has three sections: "Idea" (sub-sections per timeframe, text and
screenshots), "Exit" (screenshots) and "Conclusions" (free markdown, kept as is).
"""
import os
import re
import shutil
from datetime import datetime

from . import mdfile
from .model import (Trade, Account, Adjustment, IdeaBlock, Card,
                    TRADE_KEYS, ACCOUNT_KEYS, ADJUSTMENT_KEYS, CARD_KEYS,
                    CARD_SECTIONS, PAIR_NOT_SET)

JOURNAL = "journal"
TRASH = ".trash"            # deleted records: outside git, but not gone
TRADES, ACCOUNTS, ADJUSTMENTS, REPORTS = "trades", "accounts", "adjustments", "reports"
CARDS = "cards"             # daily reviews, one file per day
TRADE_FILE = "trade.md"
SHOTS = "shots"

_IMAGE = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)\s*$")


# --- small conversions -----------------------------------------------------

def _date(s):
    """'2025-06-25' or '2025-06-25 14:30' -> (datetime, is the time known)."""
    if not s:
        return None, False
    s = str(s).strip().replace("T", " ")
    if " " in s:
        return datetime.strptime(s[:16], "%Y-%m-%d %H:%M"), True
    return datetime.strptime(s, "%Y-%m-%d"), False


def _date_to_text(dt, with_time=False):
    if dt is None:
        return ""
    if with_time:
        return dt.strftime("%Y-%m-%d %H:%M")
    return dt.strftime("%Y-%m-%d")


def _text(v):
    """A header value as a string.

    An empty key (`pnl $:` with nothing after it) parses into an empty LIST,
    that is how lists are written in a header. str() would turn it into "[]",
    which would show up in the interface and break number parsing."""
    if v is None or isinstance(v, (list, tuple)):
        return ""
    return str(v)


def _number(s):
    text = _text(s).replace(",", ".").replace("$", "").strip()
    if not text:
        return None
    return float(text)


def _number_to_text(x):
    """Whole numbers are written without a .0 tail, so the file reads better."""
    if x is None:
        return ""
    return str(int(x)) if float(x) == int(x) else repr(round(float(x), 4))


def _list(v):
    if not v:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


# --- trade: object <-> text ------------------------------------------------

def trade_to_text(t):
    head = {}
    head["id"] = t.id
    head["account"] = t.account
    head["pair"] = t.pair or PAIR_NOT_SET
    head["direction"] = t.direction
    head["style"] = t.style
    head["entry tf"] = t.entry_tf
    head["execution"] = _list(t.execution)
    head["risk %"] = _number_to_text(t.risk)
    head["entry"] = _date_to_text(t.opened, t.opened_time)
    if t.result is not None:
        head["result"] = t.result
        head["pnl $"] = _number_to_text(t.pnl)
        head["exit"] = _date_to_text(t.closed)
    if t.note:
        head["note"] = t.note
    if t.notion_id:
        head["notion id"] = t.notion_id
    head.update(t.extra)

    parts = []
    if t.idea:
        parts.append("## Idea")
        for block in t.idea:
            parts.append(f"### {block.tf}" if block.tf else "###")
            if block.text.strip():
                parts.append(block.text.strip())
            parts.extend(f"![]({src})" for src in block.images)
    if t.exit_images:
        parts.append("## Exit")
        parts.extend(f"![]({src})" for src in t.exit_images)
    if t.conclusions.strip():
        parts.append("## Conclusions")
        parts.append(t.conclusions.strip())
    return mdfile.dump(head, "\n\n".join(parts))


def text_to_trade(text):
    head, body = mdfile.parse(text)
    known = {key for _, key in TRADE_KEYS}
    opened, with_time = _date(head.get("entry"))
    closed, _ = _date(head.get("exit"))
    t = Trade(
        id=_text(head.get("id")),
        account=_text(head.get("account")),
        pair=_text(head.get("pair")) or PAIR_NOT_SET,
        direction=_text(head.get("direction")),
        style=_text(head.get("style")),
        entry_tf=_text(head.get("entry tf")),
        execution=_list(head.get("execution")),
        risk=_number(head.get("risk %")) or 0.0,
        opened=opened,
        opened_time=with_time,
        result=(_text(head.get("result")) or None),
        pnl=_number(head.get("pnl $")),
        closed=closed,
        note=_text(head.get("note")),
        notion_id=_text(head.get("notion id")),
        extra={k: v for k, v in head.items() if k not in known},
    )
    sections = _split_sections(body)
    t.idea = _parse_idea(sections.get("Idea", ""))
    _, t.exit_images = _text_and_images(sections.get("Exit", ""))
    t.conclusions = sections.get("Conclusions", "").strip()
    return t


def _split_sections(body):
    """Body -> {heading of '## X': the text under it}."""
    sections, name, buf = {}, None, []
    for line in body.split("\n"):
        if line.startswith("## "):
            if name is not None:
                sections[name] = "\n".join(buf).strip()
            name, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if name is not None:
        sections[name] = "\n".join(buf).strip()
    return sections


def _parse_idea(text):
    blocks, tf, buf = [], None, []

    def close():
        if tf is None and not "".join(buf).strip():
            return
        body, images = _text_and_images("\n".join(buf))
        blocks.append(IdeaBlock(tf=tf or "", text=body, images=images))

    for line in text.split("\n"):
        if line.startswith("### ") or line.strip() == "###":
            close()
            tf, buf = line[4:].strip(), []
        else:
            buf.append(line)
    close()
    return blocks


def _text_and_images(chunk):
    """Split image lines from the text, keeping the order of the images."""
    lines, images = [], []
    for line in chunk.split("\n"):
        m = _IMAGE.match(line.strip())
        if m:
            images.append(m.group("src"))
        else:
            lines.append(line)
    return "\n".join(lines).strip(), images


# --- account and adjustment: object <-> text -------------------------------

def account_to_text(a):
    head = {"id": a.id, "name": a.name,
            "start balance": _number_to_text(a.start_balance),
            "currency": a.currency, "archived": "yes" if a.archived else "no"}
    if a.notion_id:
        head["notion id"] = a.notion_id
    head.update(a.extra)
    return mdfile.dump(head, a.note)


def text_to_account(text):
    head, body = mdfile.parse(text)
    known = {key for _, key in ACCOUNT_KEYS}
    return Account(
        id=_text(head.get("id")),
        name=_text(head.get("name")),
        start_balance=_number(head.get("start balance")) or 0.0,
        currency=_text(head.get("currency")) or "USD",
        archived=_text(head.get("archived")).strip().lower() in ("yes", "true", "1"),
        notion_id=_text(head.get("notion id")),
        note=body.strip(),
        extra={k: v for k, v in head.items() if k not in known},
    )


def adjustment_to_text(c):
    head = {"id": c.id, "account": c.account, "kind": c.kind,
            "amount": _number_to_text(c.amount), "date": _date_to_text(c.day)}
    head.update(c.extra)
    return mdfile.dump(head, c.comment)


def text_to_adjustment(text):
    head, body = mdfile.parse(text)
    known = {key for _, key in ADJUSTMENT_KEYS}
    day, _ = _date(head.get("date"))
    return Adjustment(
        id=_text(head.get("id")),
        account=_text(head.get("account")),
        kind=_text(head.get("kind")),
        amount=_number(head.get("amount")) or 0.0,
        day=day,
        comment=body.strip(),
        extra={k: v for k, v in head.items() if k not in known},
    )


# --- daily card: object <-> text -------------------------------------------

def card_to_text(k):
    # Empty values are not written into the header: `pnl $:` with nothing after
    # it parses back as an empty LIST, not an empty string, and the file stops
    # being readable.
    head = {"date": _date_to_text(k.day)}
    if k.grade:
        head["process grade"] = k.grade
    if k.pnl is not None:
        head["pnl $"] = _number_to_text(k.pnl)
    if k.quality:
        head["opportunity quality"] = k.quality
    head.update(k.extra)
    parts = []
    for name, heading, _ in CARD_SECTIONS:
        text = getattr(k, name).strip()
        if text:
            parts += [f"## {heading}", text]
    return mdfile.dump(head, "\n\n".join(parts))


def text_to_card(text):
    head, body = mdfile.parse(text)
    known = {key for _, key in CARD_KEYS}
    day, _ = _date(head.get("date"))
    k = Card(
        day=day,
        grade=_text(head.get("process grade")),
        pnl=_number(head.get("pnl $")),
        quality=_text(head.get("opportunity quality")),
        extra={kk: v for kk, v in head.items() if kk not in known},
    )
    sections = _split_sections(body)
    for name, heading, _ in CARD_SECTIONS:
        setattr(k, name, sections.get(heading, "").strip())
    return k


# --- files -----------------------------------------------------------------

def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)          # atomic: the server never reads a half file


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


JOURNAL_DIRS = [TRADES, ACCOUNTS, ADJUSTMENTS, CARDS, REPORTS]


def make_layout(root):
    """Creates the empty journal directories if they are not there yet.

    Otherwise a section only appears when the first record is written, and you
    cannot see where your records will land. Returns the ones that were missing."""
    created = []
    for name in JOURNAL_DIRS:
        path = os.path.join(root, JOURNAL, name)
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            created.append(name)
        if not os.listdir(path):
            open(os.path.join(path, ".gitkeep"), "w").close()
    return created


def safe_dir_name(name):
    """A trade id becomes a directory name: no path separators, no climbing
    up, no hidden names. Everything that arrives from a URL is checked."""
    return bool(name) and not name.startswith(".") and \
        "/" not in name and "\\" not in name and "\0" not in name


def trade_dir(root, trade_id):
    return os.path.join(root, JOURNAL, TRADES, trade_id)


def shots_dir(root, trade_id):
    return os.path.join(trade_dir(root, trade_id), SHOTS)


def save_trade(root, t):
    t.check()
    _write(os.path.join(trade_dir(root, t.id), TRADE_FILE), trade_to_text(t))
    return t


def load_trade(root, trade_id):
    return text_to_trade(_read(os.path.join(trade_dir(root, trade_id), TRADE_FILE)))


def save_account(root, a):
    a.check()
    _write(os.path.join(root, JOURNAL, ACCOUNTS, a.id + ".md"), account_to_text(a))
    return a


def save_adjustment(root, c):
    c.check()
    _write(os.path.join(root, JOURNAL, ADJUSTMENTS, c.id + ".md"),
           adjustment_to_text(c))
    return c


def all_trades(root):
    """Every trade, sorted by entry date (then by id)."""
    base = os.path.join(root, JOURNAL, TRADES)
    trades = []
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        path = os.path.join(base, name, TRADE_FILE)
        if os.path.isfile(path):
            trades.append(text_to_trade(_read(path)))
    trades.sort(key=lambda t: (t.opened or datetime.max, t.id))
    return trades


def all_accounts(root):
    base = os.path.join(root, JOURNAL, ACCOUNTS)
    accounts = {}
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if name.endswith(".md"):
            a = text_to_account(_read(os.path.join(base, name)))
            accounts[a.id] = a
    return accounts


def all_adjustments(root):
    base = os.path.join(root, JOURNAL, ADJUSTMENTS)
    items = []
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if name.endswith(".md"):
            items.append(text_to_adjustment(_read(os.path.join(base, name))))
    items.sort(key=lambda c: (c.day or datetime.max, c.id))
    return items


def card_path(root, day):
    return os.path.join(root, JOURNAL, CARDS, f"{day:%Y-%m-%d}.md")


def save_card(root, k):
    k.check()
    _write(card_path(root, k.day), card_to_text(k))
    return k


def load_card(root, day):
    """The card of that day, or None if there is none yet."""
    path = card_path(root, day)
    if not os.path.isfile(path):
        return None
    return text_to_card(_read(path))


def all_cards(root):
    """Every card, newest first."""
    base = os.path.join(root, JOURNAL, CARDS)
    items = []
    for name in sorted(os.listdir(base), reverse=True) if os.path.isdir(base) else []:
        if name.endswith(".md"):
            items.append(text_to_card(_read(os.path.join(base, name))))
    return items


def delete_card(root, day):
    """The card goes to the trash; like a trade, there is nothing to shred."""
    path = card_path(root, day)
    if not os.path.isfile(path):
        return None
    target = os.path.join(root, TRASH,
                          f"card-{day:%Y-%m-%d}-{datetime.now():%Y%m%d-%H%M%S}.md")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.move(path, target)
    return target


def delete_trade(root, trade_id):
    """Moves the whole trade directory to the trash, screenshots and all.

    Not rm: the journal is kept by hand, and a mis-click should not cost a
    record. Returns the path in the trash, or None if there was no such trade.
    """
    path = trade_dir(root, trade_id)
    if not os.path.isdir(path):
        return None
    target = os.path.join(root, TRASH,
                          f"{trade_id}-{datetime.now():%Y%m%d-%H%M%S}")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.move(path, target)
    return target


def new_adjustment_id(root, day, kind, account):
    """An adjustment id: YYYY-MM-DD-kind-account, with a counter when taken.

    Same shape as a trade id, so the folder sorts by date on its own."""
    base = os.path.join(root, JOURNAL, ADJUSTMENTS)
    taken = {name[:-3] for name in (os.listdir(base) if os.path.isdir(base) else [])
             if name.endswith(".md")}
    stem = f"{day:%Y-%m-%d}-{kind}-{account}"
    if stem not in taken:
        return stem
    n = 2
    while f"{stem}-{n:02d}" in taken:
        n += 1
    return f"{stem}-{n:02d}"


def delete_adjustment(root, adjustment_id):
    """To the trash, like everything else: money moves are records too."""
    path = os.path.join(root, JOURNAL, ADJUSTMENTS, adjustment_id + ".md")
    if not os.path.isfile(path):
        return None
    target = os.path.join(root, TRASH,
                          f"adjustment-{adjustment_id}-{datetime.now():%Y%m%d-%H%M%S}.md")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.move(path, target)
    return target


def new_id(root, day, pair):
    """A trade id: YYYY-MM-DD-NN-pair, where NN counts trades within the day."""
    slug = re.sub(r"[^\w-]+", "-", (pair or PAIR_NOT_SET).lower().replace(" ", "-"))
    prefix = day.strftime("%Y-%m-%d")
    base = os.path.join(root, JOURNAL, TRADES)
    taken = [name for name in (os.listdir(base) if os.path.isdir(base) else [])
             if name.startswith(prefix + "-")]
    n = len(taken) + 1
    while f"{prefix}-{n:02d}-{slug}" in taken or any(
            name.startswith(f"{prefix}-{n:02d}-") for name in taken):
        n += 1
    return f"{prefix}-{n:02d}-{slug}"


# --- pair list -------------------------------------------------------------
# Pairs the owner added by hand. In the form's suggestions they are merged with
# the pairs of the trades already recorded, so old pairs never disappear.
PAIRS_FILE = "pairs.md"


def pairs_file(root):
    return os.path.join(root, JOURNAL, PAIRS_FILE)


def all_pairs(root):
    path = pairs_file(root)
    if not os.path.isfile(path):
        return []
    head, _ = mdfile.parse(_read(path))
    return [str(p) for p in _list(head.get("pairs"))]


def save_pairs(root, pairs):
    clean = sorted({str(p).strip().upper() for p in pairs if str(p).strip()})
    _write(pairs_file(root), mdfile.dump({"pairs": clean},
           "Pairs suggested in the trade form. Edited in the interface."))
    return clean


def delete_account(root, account_id):
    """Removes the account file. Checking for trades is the caller's job."""
    path = os.path.join(root, JOURNAL, ACCOUNTS, account_id + ".md")
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False
