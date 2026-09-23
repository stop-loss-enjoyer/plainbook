#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reading and writing the journal: files <-> objects from model.py.

Layout, with `journal/` and its two service folders under the root the
server was given (PLAINBOOK_ROOT, or the project folder):

    journal/accounts/<id>.md
    journal/adjustments/<id>.md
    journal/trades/<id>/trade.md, shots/*.png
    journal/plans/<id>/plan.md, shots/*.png
    journal/playbooks/<id>/playbook.md, versions/<label>.md, shots/*.png
    journal/notes/<id>/note.md, shots/*.png
    journal/cards/YYYY-MM-DD.md, YYYY-Www.md
    journal/reports/<period>.md
    journal/vocabulary.md, pairs.md, settings.md
    .trash/                deleted records, restorable from the Accounts tab
    .drafts/               pictures pasted into forms not yet submitted

A trade body has four sections: "Idea" (sub-sections per timeframe, text and
screenshots), "Exit" (screenshots), "Conclusions" and "Updates" (free
markdown, kept as is).
"""
import os
import re
import shutil
from datetime import datetime, timedelta

from . import mdfile
from .model import (Trade, Account, Adjustment, IdeaBlock, Card, Week, Graded,
                    Playbook, Setup, Rule, PLAYBOOK_KEYS,
                    Plan, Note, TRADE_KEYS, ACCOUNT_KEYS, ADJUSTMENT_KEYS, CARD_KEYS,
                    WEEK_KEYS, PLAN_KEYS, NOTE_KEYS, CARD_SECTIONS, WEEK_SECTIONS,
                    PAIR_NOT_SET, STYLES, TIMEFRAMES, EXECUTION, RecordError)

JOURNAL = "journal"
TRASH = ".trash"            # deleted records: outside git, but not gone
TRADES, ACCOUNTS, ADJUSTMENTS, REPORTS = "trades", "accounts", "adjustments", "reports"
CARDS = "cards"             # the reviews: a file per day, a file per week
PLANS = "plans"             # trading plans, a folder each, like a trade
PLAYBOOKS = "playbooks"     # the standing rules, a folder each
NOTES = "notes"             # market notes, a folder each, with their shots
TRADE_FILE = "trade.md"
PLAN_FILE = "plan.md"
PLAYBOOK_FILE = "playbook.md"
NOTE_FILE = "note.md"
SHOTS = "shots"


def record_path(name):
    """The path of a picture as a record writes it: `shots/<name>`, with the
    slash of markdown and of a URL, whatever the system. os.path.join would
    put a backslash in on Windows, and a record with a backslash in it stops
    showing its pictures the day the folder is copied to another system."""
    return SHOTS + "/" + name

_IMAGE = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)\s*$")
# a day and a week share the cards folder, and the name of the file says which
# one a file is: 2026-08-30.md against 2026-W36.md
_WEEK_FILE = re.compile(r"^\d{4}-W\d{2}\.md$")


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


def _reasons(lines):
    """'6: closed at the news' lines -> {6: 'closed at the news'}."""
    out = {}
    for line in lines:
        number, _, why = str(line).partition(":")
        if number.strip().isdigit() and why.strip():
            out[int(number)] = why.strip()
    return out


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
    if t.entry_tf:                       # never an empty value in a header
        head["entry tf"] = t.entry_tf
    head["execution"] = _list(t.execution)
    head["risk %"] = _number_to_text(t.risk)
    head["entry"] = _date_to_text(t.opened, t.opened_time)
    if t.result is not None:
        head["result"] = t.result
        head["pnl $"] = _number_to_text(t.pnl)
        head["exit"] = _date_to_text(t.closed, t.closed_time)
    if t.breakeven is not None:
        head["stop at breakeven"] = _date_to_text(t.breakeven, True)
    if t.note:
        head["note"] = t.note
    if t.plan:
        head["plan"] = t.plan
    if t.playbook:
        head["playbook"] = t.playbook
        if t.playbook_version:
            head["playbook version"] = t.playbook_version
        if t.setup:
            head["setup"] = t.setup
        # the key stands, empty, for a trade ticked against every rule; a trade
        # tied to the playbook later, never ticked, does not carry it
        if t.deviations is not None:
            head["deviations"] = [str(n) for n in t.deviations]
        if t.exit_deviations is not None:
            head["exit deviations"] = [str(n) for n in t.exit_deviations]
        if t.reasons:
            head["reasons"] = [f"{n}: {why}" for n, why in sorted(t.reasons.items())]
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
    if t.updates.strip():
        parts.append("## Updates")
        parts.append(t.updates.strip())
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
    closed, closed_with_time = _date(head.get("exit"))
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
        closed_time=closed_with_time,
        breakeven=_date(head.get("stop at breakeven"))[0],
        note=_text(head.get("note")),
        plan=_text(head.get("plan")),
        playbook=_text(head.get("playbook")),
        playbook_version=_text(head.get("playbook version")),
        setup=_text(head.get("setup")),
        deviations=(None if "deviations" not in head else
                    [int(x) for x in _list(head.get("deviations")) if str(x).strip()]),
        exit_deviations=(None if "exit deviations" not in head else
                         [int(x) for x in _list(head.get("exit deviations"))
                          if str(x).strip()]),
        reasons=_reasons(_list(head.get("reasons"))),
        notion_id=_text(head.get("notion id")),
        extra={k: v for k, v in head.items() if k not in known},
    )
    sections = _split_sections(body)
    t.idea = _parse_idea(sections.get("Idea", ""))
    _, t.exit_images = _text_and_images(sections.get("Exit", ""))
    t.conclusions = sections.get("Conclusions", "").strip()
    t.updates = sections.get("Updates", "").strip()
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
            # records written on Windows before 1.7 carry a backslash;
            # read them as the same picture, and the next save writes them right
            images.append(m.group("src").replace("\\", "/"))
        else:
            lines.append(line)
    return "\n".join(lines).strip(), images


# --- account and adjustment: object <-> text -------------------------------

def account_to_text(a):
    head = {"id": a.id, "name": a.name or a.id,
            "start balance": _number_to_text(a.start_balance),
            "currency": a.currency, "archived": "yes" if a.archived else "no"}
    if a.daily_loss_limit is not None:
        head["daily loss limit"] = _number_to_text(a.daily_loss_limit)
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
        daily_loss_limit=_number(head.get("daily loss limit")),
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


# --- trading plan: object <-> text -----------------------------------------

def plan_to_text(k):
    head = {"id": k.id}
    if k.title:
        head["title"] = k.title
    head["pair"] = k.pair or PAIR_NOT_SET
    if k.narrative:
        head["narrative"] = k.narrative
    head["from"] = _date_to_text(k.day)
    if k.until and k.until != k.day:
        head["until"] = _date_to_text(k.until)
    if k.voided:
        head["voided"] = _date_to_text(k.voided)
    head.update(k.extra)

    parts = []
    if k.analysis:
        parts.append("## Analysis")
        for block in k.analysis:
            parts.append(f"### {block.tf}" if block.tf else "###")
            if block.text.strip():
                parts.append(block.text.strip())
            parts.extend(f"![]({src})" for src in block.images)
    for heading, text in (("Plan", k.plan), ("Updates", k.updates),
                          ("Review", k.review)):
        if text.strip():
            parts += [f"## {heading}", text.strip()]
    return mdfile.dump(head, "\n\n".join(parts))


def text_to_plan(text):
    head, body = mdfile.parse(text)
    known = {key for _, key in PLAN_KEYS}
    day, _ = _date(head.get("from"))
    until, _ = _date(head.get("until"))
    voided, _ = _date(head.get("voided"))
    k = Plan(
        id=_text(head.get("id")),
        title=_text(head.get("title")),
        pair=_text(head.get("pair")) or PAIR_NOT_SET,
        narrative=_text(head.get("narrative")),
        day=day,
        until=until,
        voided=voided,
        extra={kk: v for kk, v in head.items() if kk not in known},
    )
    sections = _split_sections(body)
    k.analysis = _parse_idea(sections.get("Analysis", ""))
    k.plan = sections.get("Plan", "").strip()
    k.updates = sections.get("Updates", "").strip()
    k.review = sections.get("Review", "").strip()
    return k


# --- market note: object <-> text ------------------------------------------
# The file is the note itself: a header with the title, the day and the ids
# of the example trades, then the blocks, a `###` heading each, the way the
# analysis of a plan is written. A first block with no heading is written
# without the `###` line, so a note of one block reads as plain text.

def note_to_text(n):
    head = {"id": n.id, "title": n.title, "date": _date_to_text(n.day)}
    if n.trades:
        head["trades"] = list(n.trades)
    head.update(n.extra)
    parts = []
    for i, block in enumerate(n.blocks):
        if block.tf or i:
            parts.append(f"### {block.tf}" if block.tf else "###")
        if block.text.strip():
            parts.append(block.text.strip())
        parts.extend(f"![]({src})" for src in block.images)
    return mdfile.dump(head, "\n\n".join(parts))


def text_to_note(text):
    head, body = mdfile.parse(text)
    known = {key for _, key in NOTE_KEYS}
    day, _ = _date(head.get("date"))
    trades = head.get("trades") or []
    if isinstance(trades, str):
        trades = [trades]
    return Note(
        id=_text(head.get("id")),
        title=_text(head.get("title")),
        day=day,
        blocks=_parse_idea(body),
        trades=[t for t in trades if t],
        extra={k: v for k, v in head.items() if k not in known},
    )


# --- playbook: object <-> text ---------------------------------------------
# The file reads as the rules would on paper: a heading per setup, a line per
# rule with a box in front of it. Only three headings mean anything to the
# code (Setups or Conditions, Filters, Limits); every other heading is kept as
# the owner wrote it and shown as text.

_RULE = re.compile(r"^\s*[-*]\s*\[[ xX]?\]\s*(.*)$")
_SHORT = re.compile(r"^\*\*(.+?)\*\*\s*(.*)$", re.S)
SETUPS, CONDITIONS, FILTERS, LIMITS = "Setups", "Conditions", "Filters", "Limits"
REVIEW = "Review"          # the block reviews, dated entries with screenshots
MANAGEMENT = "Management"  # the rules of holding a position, ticked at the close


def _rule(number, line):
    """`**the few words** the whole rule` -> Rule; a line with no bold part
    is the few words and nothing more."""
    m = _SHORT.match(line)
    if m:
        return Rule(number=number, text=m.group(1).strip(), detail=m.group(2).strip())
    return Rule(number=number, text=line, detail="")


def _rule_line(r):
    return f"- [ ] **{r.text}** {r.detail}" if r.detail else f"- [ ] {r.text}"


def _rules_and_text(chunk, start):
    """A section body -> (the prose above and between the rules, [Rule]).
    Numbering carries on from `start`, so a rule's number is unique in the
    whole playbook."""
    rules, prose = [], []
    for line in chunk.split("\n"):
        m = _RULE.match(line)
        if m and m.group(1).strip():
            rules.append(_rule(start + len(rules), m.group(1).strip()))
        elif not m:
            prose.append(line)
    return "\n".join(prose).strip(), rules


def _parse_setups(text, start):
    """The setups under `## Setups` -> ([Setup], the prose above the first
    `###`). That prose is nobody's setup: it goes back to the introduction."""
    setups, name, buf, lead = [], None, [], ""

    def close():
        nonlocal lead
        if name is None and not "".join(buf).strip():
            return
        prose, rules = _rules_and_text("\n".join(buf), start + sum(
            len(x.rules) for x in setups))
        if name is None and not rules:
            lead = prose
            return
        setups.append(Setup(name=name or "", text=prose, rules=rules))

    for line in text.split("\n"):
        if line.startswith("### "):
            close()
            name, buf = line[4:].strip(), []
        else:
            buf.append(line)
    close()
    return setups, lead


def playbook_to_text(p):
    head = {"id": p.id}
    if p.name:
        head["name"] = p.name
    if p.styles:
        head["styles"] = list(p.styles)
    head["status"] = p.status
    if p.version:
        head["version"] = p.version
    if p.since:
        head["since"] = _date_to_text(p.since)
    if p.block:
        head["block"] = str(int(p.block))
    head.update(p.extra)

    parts = []
    if p.intro.strip():
        parts.append(p.intro.strip())
    if p.setups:
        named = any(s.name for s in p.setups) or len(p.setups) > 1
        parts.append(f"## {SETUPS}" if named else f"## {CONDITIONS}")
        for s in p.setups:
            if named:
                parts.append(f"### {s.name}")
            if s.text.strip():
                parts.append(s.text.strip())
            parts.extend(_rule_line(r) for r in s.rules)
    if p.filters:
        parts.append(f"## {FILTERS}")
        parts.extend(_rule_line(r) for r in p.filters)
    if p.management:
        parts.append(f"## {MANAGEMENT}")
        parts.extend(_rule_line(r) for r in p.management)
    if p.limits:
        parts.append(f"## {LIMITS}")
        parts.extend(f"- {what}: {value}" for what, value in p.limits)
    for heading, text in p.sections:
        if text.strip():
            parts += [f"## {heading}", text.strip()]
    if p.review.strip():
        parts += [f"## {REVIEW}", p.review.strip()]
    return mdfile.dump(head, "\n\n".join(parts))


def text_to_playbook(text):
    head, body = mdfile.parse(text)
    known = {key for _, key in PLAYBOOK_KEYS}
    since, _ = _date(head.get("since"))
    block = _number(head.get("block"))
    p = Playbook(
        id=_text(head.get("id")),
        name=_text(head.get("name")),
        styles=_list(head.get("styles")),
        status=_text(head.get("status")) or "active",
        version=_text(head.get("version")),
        since=since,
        block=None if block is None else int(block),
        extra={kk: v for kk, v in head.items() if kk not in known},
    )
    # the text above the first heading is the introduction
    intro, _, rest = body.partition("\n## ")
    p.intro = intro.strip() if not body.startswith("## ") else ""
    sections = _split_sections(body if body.startswith("## ") else "## " + rest
                               if rest else "")
    setups = sections.pop(SETUPS, None)
    if setups is not None:
        p.setups, lead = _parse_setups(setups, 1)
        if lead:
            p.intro = (p.intro + "\n\n" + lead).strip()
    elif CONDITIONS in sections:
        prose, rules = _rules_and_text(sections.pop(CONDITIONS), 1)
        p.setups = [Setup(name="", text=prose, rules=rules)]
    if FILTERS in sections:
        _, p.filters = _rules_and_text(sections.pop(FILTERS),
                                       1 + sum(len(s.rules) for s in p.setups))
    if MANAGEMENT in sections:
        _, p.management = _rules_and_text(
            sections.pop(MANAGEMENT),
            1 + sum(len(s.rules) for s in p.setups) + len(p.filters))
    for line in sections.pop(LIMITS, "").split("\n"):
        line = line.strip().lstrip("-*").strip()
        if ":" in line:
            what, _, value = line.partition(":")
            p.limits.append((what.strip(), value.strip()))
    p.review = sections.pop(REVIEW, "").strip()
    p.sections = [(h, t) for h, t in sections.items() if t.strip()]
    return p


# --- the trades assessment: object <-> text ---------------------------------
# Written the way the paper numbers it: "1. what was traded | grade | result".
# Empty cells at the end of a line are not written, so a line that has only a
# trade is just the trade, as it was before the result column existed.

_ROW = re.compile(r"^\s*\d+[.)]\s*")


def assessment_to_text(rows):
    """The table of a card: number, trade, grade, result, and last the id of
    the trade the line names, when it was picked from the ones offered. A row
    written before the fourth cell existed has three, and reads as it did."""
    lines = []
    for n, row in enumerate(rows, 1):
        cells = [f"{n}. {row.trade}".rstrip(), row.grade, row.result, row.id]
        while len(cells) > 1 and not cells[-1]:
            cells.pop()
        lines.append(" | ".join(cells))
    return "\n".join(lines)


def text_to_assessment(text):
    rows = []
    for line in text.split("\n"):
        line = _ROW.sub("", line).strip()
        if not line:
            continue
        cells = [c.strip() for c in line.split("|")]
        trade, grade, result, tid = (cells + ["", "", ""])[:4]
        rows.append(Graded(trade=trade, grade=grade, result=result, id=tid))
    return rows


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
    if k.assessment:
        parts += ["## Trades", assessment_to_text(k.assessment)]
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
    k.assessment = text_to_assessment(sections.get("Trades", ""))
    return k


# --- weekly card: object <-> text ------------------------------------------

def week_to_text(k):
    head = {"week": k.week}
    if k.grade:
        head["process grade"] = k.grade
    if k.pnl is not None:
        head["pnl $"] = _number_to_text(k.pnl)
    if k.trades is not None:
        head["trades"] = str(k.trades)
    if k.quality:
        head["opportunity quality"] = k.quality
    if k.progress is not None:
        head["progress"] = str(k.progress)
    head.update(k.extra)
    parts = []
    for name, heading, _ in WEEK_SECTIONS:
        text = getattr(k, name).strip()
        if text:
            parts += [f"## {heading}", text]
    if k.assessment:
        parts += ["## Trades", assessment_to_text(k.assessment)]
    return mdfile.dump(head, "\n\n".join(parts))


def text_to_week(text):
    head, body = mdfile.parse(text)
    known = {key for _, key in WEEK_KEYS}
    trades = _number(head.get("trades"))
    progress = _number(head.get("progress"))
    k = Week(
        week=_text(head.get("week")),
        grade=_text(head.get("process grade")),
        pnl=_number(head.get("pnl $")),
        trades=None if trades is None else int(trades),
        quality=_text(head.get("opportunity quality")),
        progress=None if progress is None else int(progress),
        extra={kk: v for kk, v in head.items() if kk not in known},
    )
    sections = _split_sections(body)
    for name, heading, _ in WEEK_SECTIONS:
        setattr(k, name, sections.get(heading, "").strip())
    k.assessment = text_to_assessment(sections.get("Trades", ""))
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


# Reading a record can fail: a date typed the wrong way round, a number with a
# letter in it, a header without its closing line. The files are edited by
# hand, so that is not a rare event, and one such file must not take the whole
# journal down with it. Every reader below takes a `problems` list: a record
# that does not load is written there as (path, reason) and skipped, and the
# interface shows the list. Without the list the error is raised, which is what
# the tests and the checking tool want.
BROKEN = (ValueError, TypeError, KeyError, AttributeError, OSError)


def _load(problems, path, convert, root=None):
    try:
        record = convert(_read(path))
        return record.check()
    except BROKEN as e:
        if problems is None:
            raise
        shown = os.path.relpath(path, root).replace(os.sep, "/") if root else path
        problems.append((shown, str(e) or type(e).__name__))
        return None


JOURNAL_DIRS = [TRADES, ACCOUNTS, ADJUSTMENTS, CARDS, PLANS, PLAYBOOKS, NOTES,
                REPORTS]


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


def plan_dir(root, plan_id):
    return os.path.join(root, JOURNAL, PLANS, plan_id)


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


def all_trades(root, problems=None):
    """Every trade, sorted by entry date (then by id)."""
    base = os.path.join(root, JOURNAL, TRADES)
    trades = []
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        path = os.path.join(base, name, TRADE_FILE)
        if os.path.isfile(path):
            t = _load(problems, path, text_to_trade, root)
            if t is not None:
                trades.append(t)
    trades.sort(key=lambda t: (t.opened or datetime.max, t.id))
    return trades


_TRADE_ID = re.compile(r"^(\d{4}-\d{2}-\d{2})-\d{2}-(.+)$")


def pair_slug(pair):
    return re.sub(r"[^\w-]+", "-", (pair or PAIR_NOT_SET).lower().replace(" ", "-"))


def id_fits(trade):
    """Does the id still say the day and the pair of the trade?

    The id is the folder name, and the folder is what a person opens to find a
    trade; an id built from one day and pair while the record carries another
    is a folder that lies. An id of another shape, from a journal migrated in,
    is left alone: nothing about it can be checked."""
    m = _TRADE_ID.match(trade.id or "")
    if not m or trade.opened is None:
        return True
    return (m.group(1) == f"{trade.opened:%Y-%m-%d}"
            and m.group(2) == pair_slug(trade.pair))


def rename_trade(root, t, new_id):
    """Moves the folder of a trade under a new id. The pictures inside it are
    written as paths relative to the folder, so they need no touching."""
    if new_id == t.id:
        return t
    src, dst = trade_dir(root, t.id), trade_dir(root, new_id)
    if os.path.exists(dst):
        raise FileExistsError(f"a trade {new_id} already exists")
    os.rename(src, dst)
    t.id = new_id
    return t


def save_plan(root, k):
    k.check()
    _write(os.path.join(plan_dir(root, k.id), PLAN_FILE), plan_to_text(k))
    return k


def _load_one(problems, path, convert, root):
    """One record by its id. With a problems list a missing file is None
    and nothing more (the route answers 404), a file that does not read is
    None with the reason in the list (the route names it); without the list
    both raise, which is what the tests and the tools want."""
    if problems is not None and not os.path.isfile(path):
        return None
    return _load(problems, path, convert, root)


def load_plan(root, plan_id, problems=None):
    return _load_one(problems, os.path.join(plan_dir(root, plan_id), PLAN_FILE),
                     text_to_plan, root)


def all_plans(root, problems=None):
    """Every plan, newest first: a plan is looked for near the day it was made."""
    base = os.path.join(root, JOURNAL, PLANS)
    plans = []
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        path = os.path.join(base, name, PLAN_FILE)
        if os.path.isfile(path):
            k = _load(problems, path, text_to_plan, root)
            if k is not None:
                plans.append(k)
    plans.sort(key=lambda k: (k.day or datetime.min, k.id), reverse=True)
    return plans


def playbook_dir(root, playbook_id):
    return os.path.join(root, JOURNAL, PLAYBOOKS, playbook_id)


def save_playbook(root, p):
    p.check()
    _write(os.path.join(playbook_dir(root, p.id), PLAYBOOK_FILE), playbook_to_text(p))
    return p


def load_playbook(root, playbook_id, problems=None):
    return _load_one(problems, os.path.join(playbook_dir(root, playbook_id),
                                            PLAYBOOK_FILE), text_to_playbook, root)


def all_playbooks(root, problems=None):
    """Every playbook: the ones in use first, retired ones last, by name."""
    base = os.path.join(root, JOURNAL, PLAYBOOKS)
    found = []
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        path = os.path.join(base, name, PLAYBOOK_FILE)
        if os.path.isfile(path):
            p = _load(problems, path, text_to_playbook, root)
            if p is not None:
                found.append(p)
    found.sort(key=lambda p: (not p.offered, (p.name or p.id).lower()))
    return found


VERSIONS = "versions"       # the rules as they were before each revision


def new_playbook_id(root, name):
    """A playbook id from its name: 'EMT prop' -> emt-prop, with a counter when
    the name is taken. The id is the folder, and it does not change with the
    name later, because trades point at it."""
    stem = re.sub(r"-+", "-", re.sub(r"[^\w-]+", "-", (name or "playbook").lower())).strip("-")
    stem = stem or "playbook"
    base = os.path.join(root, JOURNAL, PLAYBOOKS)
    taken = set(os.listdir(base) if os.path.isdir(base) else [])
    if stem not in taken:
        return stem
    n = 2
    while f"{stem}-{n}" in taken:
        n += 1
    return f"{stem}-{n}"


def freeze_playbook(root, playbook_id):
    """Keeps the file as it is under versions/<version>.md before the rules
    are rewritten. A trade opened under the old rules will be shown them, not
    the new ones. Returns the name the version was kept under."""
    path = os.path.join(playbook_dir(root, playbook_id), PLAYBOOK_FILE)
    if not os.path.isfile(path):
        return None
    head, _ = mdfile.parse(_read(path))
    label = re.sub(r"[^\w.-]+", "-", _text(head.get("version"))) or "unversioned"
    target = os.path.join(playbook_dir(root, playbook_id), VERSIONS, label + ".md")
    if os.path.exists(target):          # the same number twice: keep both
        n = 2
        while os.path.exists(os.path.join(os.path.dirname(target), f"{label}-{n}.md")):
            n += 1
        target = os.path.join(os.path.dirname(target), f"{label}-{n}.md")
    _write(target, _read(path))
    return os.path.basename(target)[:-3]


def playbook_versions(root, playbook_id):
    """The frozen versions, oldest first by file name."""
    base = os.path.join(playbook_dir(root, playbook_id), VERSIONS)
    return sorted(name[:-3] for name in (os.listdir(base) if os.path.isdir(base) else [])
                  if name.endswith(".md"))


def load_playbook_version(root, playbook_id, label, problems=None):
    return _load_one(problems, os.path.join(playbook_dir(root, playbook_id),
                                            VERSIONS, label + ".md"),
                     text_to_playbook, root)


def delete_playbook(root, playbook_id):
    """To the trash with its versions, like a plan."""
    path = playbook_dir(root, playbook_id)
    if not os.path.isdir(path):
        return None
    target = _trash_target(root, f"playbook-{playbook_id}")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.move(path, target)
    return target


def note_dir(root, note_id):
    return os.path.join(root, JOURNAL, NOTES, note_id)


def save_note(root, n):
    n.check()
    _write(os.path.join(note_dir(root, n.id), NOTE_FILE), note_to_text(n))
    return n


def load_note(root, note_id, problems=None):
    return _load_one(problems, os.path.join(note_dir(root, note_id), NOTE_FILE),
                     text_to_note, root)


def all_notes(root, problems=None):
    """Every note, newest first."""
    base = os.path.join(root, JOURNAL, NOTES)
    notes = []
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        path = os.path.join(base, name, NOTE_FILE)
        if os.path.isfile(path):
            n = _load(problems, path, text_to_note, root)
            if n is not None:
                notes.append(n)
    notes.sort(key=lambda n: (n.day or datetime.min, n.id), reverse=True)
    return notes


def new_note_id(root, day, title):
    """A note id: YYYY-MM-DD-the-title, with a counter when the day already
    has one. The letters of the title are kept whatever alphabet they are in,
    so that the folder can be found by its name; a title with no letter at all
    is called a note."""
    slug = re.sub(r"[^\w]+", "-", (title or "").lower()).strip("-")[:40].strip("-")
    base = os.path.join(root, JOURNAL, NOTES)
    taken = set(os.listdir(base) if os.path.isdir(base) else [])
    stem = f"{day:%Y-%m-%d}-{slug or 'note'}"
    if stem not in taken:
        return stem
    n = 2
    while f"{stem}-{n:02d}" in taken:
        n += 1
    return f"{stem}-{n:02d}"


def delete_note(root, note_id):
    """To the trash with its screenshots, like a plan."""
    path = note_dir(root, note_id)
    if not os.path.isdir(path):
        return None
    target = _trash_target(root, f"note-{note_id}")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.move(path, target)
    return target


def new_plan_id(root, day, pair):
    """A plan id: YYYY-MM-DD-pair, with a counter when the day already has one."""
    slug = pair_slug(pair)
    base = os.path.join(root, JOURNAL, PLANS)
    taken = set(os.listdir(base) if os.path.isdir(base) else [])
    stem = f"{day:%Y-%m-%d}-{slug}"
    if stem not in taken:
        return stem
    n = 2
    while f"{stem}-{n:02d}" in taken:
        n += 1
    return f"{stem}-{n:02d}"


def delete_plan(root, plan_id):
    """To the trash with its screenshots, like a trade."""
    path = plan_dir(root, plan_id)
    if not os.path.isdir(path):
        return None
    target = _trash_target(root, f"plan-{plan_id}")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.move(path, target)
    return target


def all_accounts(root, problems=None):
    base = os.path.join(root, JOURNAL, ACCOUNTS)
    accounts = {}
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if name.endswith(".md"):
            a = _load(problems, os.path.join(base, name), text_to_account, root)
            if a is not None:
                accounts[a.id] = a
    return accounts


def all_adjustments(root, problems=None):
    base = os.path.join(root, JOURNAL, ADJUSTMENTS)
    items = []
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if name.endswith(".md"):
            c = _load(problems, os.path.join(base, name), text_to_adjustment, root)
            if c is not None:
                items.append(c)
    items.sort(key=lambda c: (c.day or datetime.max, c.id))
    return items


def card_path(root, day):
    return os.path.join(root, JOURNAL, CARDS, f"{day:%Y-%m-%d}.md")


def save_card(root, k):
    k.check()
    _write(card_path(root, k.day), card_to_text(k))
    return k


def load_card(root, day, problems=None):
    """The card of that day, or None if there is none yet."""
    path = card_path(root, day)
    if not os.path.isfile(path):
        return None
    return _load(problems, path, text_to_card, root)


def all_cards(root, problems=None):
    """Every daily card, newest first. The weekly ones are read by all_weeks."""
    base = os.path.join(root, JOURNAL, CARDS)
    items = []
    for name in sorted(os.listdir(base), reverse=True) if os.path.isdir(base) else []:
        if name.endswith(".md") and not _WEEK_FILE.match(name):
            k = _load(problems, os.path.join(base, name), text_to_card, root)
            if k is not None:
                items.append(k)
    return items


def delete_card(root, day):
    """The card goes to the trash; like a trade, there is nothing to shred."""
    path = card_path(root, day)
    if not os.path.isfile(path):
        return None
    target = _trash_target(root, f"card-{day:%Y-%m-%d}", ".md")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.move(path, target)
    return target


def week_path(root, key):
    return os.path.join(root, JOURNAL, CARDS, f"{key}.md")


def save_week(root, k):
    k.check()
    _write(week_path(root, k.week), week_to_text(k))
    return k


def load_week(root, key, problems=None):
    """The card of that week, or None if there is none yet."""
    path = week_path(root, key)
    if not os.path.isfile(path):
        return None
    return _load(problems, path, text_to_week, root)


def all_weeks(root, problems=None):
    """Every weekly card, newest first: the week files of the cards folder."""
    base = os.path.join(root, JOURNAL, CARDS)
    items = []
    for name in sorted(os.listdir(base), reverse=True) if os.path.isdir(base) else []:
        if _WEEK_FILE.match(name):
            k = _load(problems, os.path.join(base, name), text_to_week, root)
            if k is not None:
                items.append(k)
    return items


def delete_week(root, key):
    """To the trash, like the daily card."""
    path = week_path(root, key)
    if not os.path.isfile(path):
        return None
    target = _trash_target(root, f"week-{key}", ".md")
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
    target = _trash_target(root, trade_id)
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
    target = _trash_target(root, f"adjustment-{adjustment_id}", ".md")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.move(path, target)
    return target


def new_id(root, day, pair, keep=None):
    """A trade id: YYYY-MM-DD-NN-pair, where NN counts trades within the day.

    `keep` is the id a trade has now: when only its pair changed, the number
    stays and the folder keeps its place in the day."""
    slug = pair_slug(pair)
    prefix = day.strftime("%Y-%m-%d")
    base = os.path.join(root, JOURNAL, TRADES)
    taken = [name for name in (os.listdir(base) if os.path.isdir(base) else [])
             if name.startswith(prefix + "-") and name != keep]
    if keep and keep.startswith(prefix + "-") and len(keep) > 13:
        same_number = f"{prefix}-{keep[11:13]}-{slug}"
        if not any(name.startswith(f"{prefix}-{keep[11:13]}-") for name in taken):
            return same_number
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


# --- the lists the trade form offers ---------------------------------------
# Styles, timeframes and execution formats, in one file. Order is the owner's:
# a new word goes to the end of its list, because M15, H1, H4, D1 is a sequence
# and not an alphabet. A word removed here is only taken out of the form; the
# trades that carry it keep it.
VOCABULARY_FILE = "vocabulary.md"
VOCABULARY = {"styles": list(STYLES), "timeframes": list(TIMEFRAMES),
              "execution": list(EXECUTION)}


def vocabulary_file(root):
    return os.path.join(root, JOURNAL, VOCABULARY_FILE)


def all_words(root, kind):
    """One of the lists: what the file says, or what the journal starts with.

    A list the owner emptied stays empty; only a key that was never written
    falls back to the defaults."""
    head = {}
    path = vocabulary_file(root)
    if os.path.isfile(path):
        head, _ = mdfile.parse(_read(path))
    if kind not in head:
        return list(VOCABULARY[kind])
    return [str(w) for w in _list(head.get(kind))]


def save_words(root, kind, words):
    """Writes one list back, keeping the other two as they are."""
    if kind not in VOCABULARY:
        raise KeyError(kind)
    lists = {k: all_words(root, k) for k in VOCABULARY}
    clean, seen = [], set()
    for word in words:
        word = str(word).strip()
        if word and word.lower() not in seen:
            seen.add(word.lower())
            clean.append(word)
    lists[kind] = clean
    _write(vocabulary_file(root), mdfile.dump(
        lists, "The lists the trade form offers. Edited in the interface."))
    return clean


# --- the owner's settings --------------------------------------------------
# One file, one key per setting, next to the vocabulary. The stop edge is the
# loss, in R, up to which a stop is the stop as designed: -1 R plus what
# commission and swap add on top of it. Everything past it is a risk overrun,
# and every figure that says so (the rings, Past the stop, the mistakes of a
# report) is worked out from this number on every look, so a change here
# rewrites the past as well as the future.
SETTINGS_FILE = "settings.md"
STOP_EDGE = 1.2
STOP_EDGE_RANGE = (1.0, 2.0)


def settings_file(root):
    return os.path.join(root, JOURNAL, SETTINGS_FILE)


def _settings(root):
    path = settings_file(root)
    if not os.path.isfile(path):
        return {}
    head, _ = mdfile.parse(_read(path))
    return head


def clean_stop_edge(value):
    """A stop edge as the slider offers it: one decimal, inside the range."""
    try:
        edge = round(float(str(value).strip().replace(",", ".")), 1)
    except ValueError:
        raise RecordError(f"{value} is not a stop edge")
    low, high = STOP_EDGE_RANGE
    if not low <= edge <= high:
        raise RecordError(f"the stop edge is set between {low:g} and {high:g} R")
    return edge


def stop_edge(root):
    """What the file says, or the journal's own figure."""
    value = _text(_settings(root).get("stop_edge"))
    try:
        return clean_stop_edge(value) if value else STOP_EDGE
    except RecordError:
        return STOP_EDGE


def save_stop_edge(root, value):
    head = _settings(root)
    head["stop_edge"] = f"{clean_stop_edge(value):g}"
    _write(settings_file(root), mdfile.dump(
        head, "The owner's settings. Edited in the interface."))
    return clean_stop_edge(value)


def delete_account(root, account_id):
    """To the trash, like every other record. Checking for trades is the
    caller's job."""
    path = os.path.join(root, JOURNAL, ACCOUNTS, account_id + ".md")
    if not os.path.isfile(path):
        return None
    target = _trash_target(root, f"account-{account_id}", ".md")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.move(path, target)
    return target


# --- the trash --------------------------------------------------------------
# What was deleted, named by what it was and when it went: a trade keeps its
# id, the others carry their kind in front. The stamp at the end is what lets
# the same record be deleted twice.

_TRASHED = re.compile(r"^(?:(plan|playbook|note|card|week|adjustment|account)-)?(.+)-"
                      r"(\d{8}-\d{6})(\.md)?$")


def _trash_target(root, stem, suffix=""):
    """A free name in the trash: the stem, the second it went, the suffix.

    The stamp counts seconds, so a record deleted, written again and deleted
    within one second would land on its own earlier copy; it takes the next
    second instead."""
    when = datetime.now().replace(microsecond=0)
    while True:
        target = os.path.join(root, TRASH, f"{stem}-{when:%Y%m%d-%H%M%S}{suffix}")
        if not os.path.exists(target):
            return target
        when += timedelta(seconds=1)


def trash_list(root):
    """[(name in the trash, kind, id, deleted at)], newest first."""
    base = os.path.join(root, TRASH)
    items = []
    for name in os.listdir(base) if os.path.isdir(base) else []:
        m = _TRASHED.match(name)
        if not m:
            continue
        kind = m.group(1) or "trade"
        if (kind in ("trade", "plan", "playbook", "note")) == bool(m.group(4)):
            continue                     # a folder record with .md, or the reverse
        when = datetime.strptime(m.group(3), "%Y%m%d-%H%M%S")
        items.append((name, kind, m.group(2), when))
    # within one second, by name: os.listdir has an order of its own on every
    # file system, and the trash should read the same on all of them
    items.sort(key=lambda x: x[0])
    items.sort(key=lambda x: x[3], reverse=True)
    return items


def _trash_home(root, kind, record_id):
    """Where a record of that kind lives when it is not in the trash."""
    if kind == "trade":
        return trade_dir(root, record_id)
    if kind == "plan":
        return plan_dir(root, record_id)
    if kind == "playbook":
        return playbook_dir(root, record_id)
    if kind == "note":
        return note_dir(root, record_id)
    folder = {"card": CARDS, "week": CARDS,
              "adjustment": ADJUSTMENTS, "account": ACCOUNTS}[kind]
    return os.path.join(root, JOURNAL, folder, record_id + ".md")


def restore(root, name):
    """Puts a record back where it came from. Returns (kind, id).

    A record that has been written again since, under the same id, stays in
    the trash: nothing is overwritten to bring something back."""
    if not safe_dir_name(name):
        raise ValueError("bad name")
    entry = next((x for x in trash_list(root) if x[0] == name), None)
    if entry is None:
        raise FileNotFoundError(f"nothing named {name} in the trash")
    _, kind, record_id, _ = entry
    home = _trash_home(root, kind, record_id)
    if os.path.exists(home):
        raise FileExistsError(f"{kind} {record_id} exists in the journal already")
    os.makedirs(os.path.dirname(home), exist_ok=True)
    shutil.move(os.path.join(root, TRASH, name), home)
    return kind, record_id
