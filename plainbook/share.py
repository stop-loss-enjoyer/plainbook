#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The document a record is shown by: one file, with its pictures inside it and
no money in it.

The journal is private, so what leaves it is built here and nowhere else.
This module never imports `html.money` and never reads `pnl`, `risk_money` or
a balance: a field reaches the document only because a function below names
it. That is on purpose. A page of the journal shows everything and hides what
must not travel; this file shows nothing and adds what may. When a field is
added to a trade, the page gets it at once and the document does not, which
is the safe way round.

What a document is made of is what a trader can be asked about: the idea, the
screenshots, the rules that were ticked, the result in R, the conclusions.

The file is read in a browser and prints from one: the styles carry a print
block that turns the dark journal into ink on paper, so `Ctrl+P` is the way to
a PDF and no library is needed to make one.
"""
import base64
import os
import re
from datetime import datetime, timedelta

from . import __version__, flags, stats, store
from .html import (ACCENT, AXIS, BAD, DIM, EDGE, FAVICON, GOOD, GRID, GROUND,
                   INK, INK2, MONO, RAISED, SURFACE, WARN, esc, mark, pair)

# what a screenshot may be. A file of any other kind is not drawn: a document
# carries pictures and nothing else that could be executed by whoever opens it
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".avif": "image/avif"}

# base64 writes three bytes as four characters, so a picture carried inside the
# file weighs a third more than it does on disk
INFLATION = 4 / 3


def data_url(path):
    """One picture as text, or an empty string when it cannot be read.

    A picture that is missing must not kill the document: the rest of it is
    still worth reading, and a broken image says so on the page."""
    mime = MIME.get(os.path.splitext(path)[1].lower())
    if not mime:
        return ""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return ""
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


class Shots:
    """Where the pictures of one record come from and how they reach the page.

    `carry` says which of the two documents this is: one that holds its
    pictures, which is what gets sent, or one that points at the journal
    serving them, which is what the preview draws. The preview stays light
    that way, and it is the same markup either way, so what is previewed is
    what is sent."""

    def __init__(self, folder, base, carry=True):
        self.folder = folder
        self.base = base.rstrip("/")
        self.carry = carry

    def src(self, name):
        name = os.path.basename(name)
        if not self.carry:
            return f"{self.base}/{name}"
        return data_url(os.path.join(self.folder, name))

    def img(self, name, alt="screenshot"):
        src = self.src(name)
        if not src:
            return ""
        return f'<img src="{src}" alt="{esc(alt)}" loading="lazy">'

    def weight(self, names):
        """What those pictures will add to the file, in bytes."""
        total = 0
        for name in names:
            try:
                total += os.path.getsize(os.path.join(self.folder,
                                                      os.path.basename(name)))
            except OSError:
                pass
        return int(total * INFLATION)


def trade_shots(root, trade_id, carry=True):
    return Shots(os.path.join(store.trade_dir(root, trade_id), store.SHOTS),
                 f"/shot/{trade_id}", carry)


def shot_names(t):
    """Every picture a trade holds, in the order the document draws them."""
    names = [n for block in t.idea for n in block.images]
    names += list(t.exit_images)
    names += re.findall(r"!\[\]\(([^)]+)\)", t.conclusions)
    return names


# a line of the list and a card of a trade, in bytes of markup. Measured on
# real trades: near enough for a figure that is read as "will this fit in a
# message or not"
LINE = 800
CARD = 2000
_EMPTY = None


def empty_weight():
    """What a document with nothing in it weighs: the styles, the flags and
    the shell around them. Worked out once, since it cannot change while the
    journal runs."""
    global _EMPTY
    if _EMPTY is None:
        _EMPTY = len(document("", "", "").encode("utf-8"))
    return _EMPTY


def weigh(root, trades, shots=True):
    """What the finished file will weigh, in bytes: the pictures plus the text
    around them. Said in the preview, because a file of five megabytes and one
    of a hundred are sent in different ways."""
    text = empty_weight() + LINE * len(trades)
    if not shots:
        return text
    return (text + CARD * len(trades)
            + sum(trade_shots(root, t.id).weight(shot_names(t))
                  for t in trades))


def size_text(n):
    if n >= 1024 * 1024:
        return f"{n / 1024 / 1024:.1f} MB"
    return f"{max(n // 1024, 1)} KB"


# --- the pieces of a document ----------------------------------------------

def r_text(x):
    return "-" if x is None else f"{x:+.2f}"


def r_class(x):
    if x is None or abs(x) < 0.005:
        return ""
    return "good" if x > 0 else "bad"


def day_text(when, with_time):
    if when is None:
        return "-"
    return f"{when:%d.%m.%Y %H:%M}" if with_time else f"{when:%d.%m.%Y}"


def prose(text):
    """Prose written by the owner: blank lines cut paragraphs, `- ` makes a
    list, `**bold**` stays bold. The same shape the journal reads it in."""
    out = []
    for chunk in re.split(r"\n\s*\n", (text or "").strip()):
        lines = [x.strip() for x in chunk.split("\n") if x.strip()]
        if not lines:
            continue
        if all(x.startswith(("- ", "* ")) for x in lines):
            out.append("<ul>" + "".join(f"<li>{bold(x[2:])}</li>"
                                        for x in lines) + "</ul>")
        else:
            out.append(f"<p>{bold(chr(10).join(lines))}</p>")
    return "".join(out)


_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)


def bold(text):
    return _BOLD.sub(r"<strong>\1</strong>", esc(text)).replace("\n", "<br>")


def with_shots(text, shots):
    """Text that has pictures standing inside it, drawn where they stand."""
    def draw(m):
        return shots.img(m.group(1)) or ""
    return _BOLD.sub(r"<strong>\1</strong>",
                     re.sub(r"!\[\]\(([^)]+)\)", draw, esc(text))).replace("\n", "<br>")


def tile(name, value, sub="", cls=""):
    under = f'<div class="sub">{sub}</div>' if sub else ""
    return (f'<div class="tile"><div class="name">{esc(name)}</div>'
            f'<div class="value {cls}">{value}</div>{under}</div>')


def summary_tiles(s):
    """The figures of a selection, all of them in R.

    Money is not among them and not left out silently: the foot of the
    document says so, or a reader would take the absence for a journal that
    does not keep the figure."""
    if not s.trades:
        return '<p class="muted">No closed trade in this selection.</p>'
    wr = f"{s.wr:.1f}%" if s.decided else "-"
    payoff = f"{s.payoff:.2f}" if s.payoff is not None else "-"
    return (f'<div class="tiles">'
            + tile("trades", str(s.trades),
                   f"{s.wins} won · {s.losses} lost · {s.be} at zero")
            + tile("win rate", wr, "wins against wins and losses")
            + tile("EV", r_text(s.average_r), "per closed trade, R",
                   r_class(s.average_r))
            + tile("Σ R", r_text(s.sum_r), "the selection in risk units",
                   r_class(s.sum_r))
            + tile("payoff", payoff, "R won for every R lost")
            + "</div>")


def anchor(t):
    """Where a trade stands in the file, so the list can point at it."""
    return "t-" + re.sub(r"[^A-Za-z0-9_-]", "-", t.id)


def trades_table(j, trades, linked=False):
    """The selection as a list: one line a trade, R the last word on it.
    When the trades stand in full further down the file, a line is the way
    to its trade: the pair is the link, and the whole line answers a click."""
    rows = ""
    for t in sorted(trades, key=lambda x: (x.closed or x.opened, x.opened)):
        r = j.r(t.id)
        name = pair(t.pair)
        at = ""
        if linked:
            name = f'<a class="to" href="#{anchor(t)}">{name}</a>'
            at = f' class="go" data-to="{anchor(t)}"'
        rows += (f'<tr{at}><td class="dim">{day_text(t.opened, False)}</td>'
                 f'<td class="dim">{day_text(t.closed, False)}</td>'
                 f'<td>{name}</td><td>{esc(t.direction)}</td>'
                 f'<td>{esc(t.style)}</td>'
                 f'<td>{esc(t.result or "open")}</td>'
                 f'<td class="num {r_class(r)}">{r_text(r)}</td></tr>')
    return (f'<table class="list"><thead><tr><th>entry</th><th>exit</th>'
            f'<th>pair</th><th>side</th><th>style</th><th>result</th>'
            f'<th class="num">R</th></tr></thead><tbody>{rows}</tbody></table>'
            + (GO_SCRIPT if linked else ""))


# A line of the list opens its trade wherever it is pressed, not only on the
# pair. A link cannot be a table row, so this does it for the rows that carry
# one. Nothing here reaches the network: the file stays what it is.
GO_SCRIPT = ('<script>document.querySelectorAll("tr.go").forEach(function(r){'
             'r.addEventListener("click",function(e){if(!e.target.closest("a"))'
             'location.hash=r.dataset.to})})</script>')


def rules_list(rules, broken, word, reasons=None):
    """The rules with a tick or a cross each, and the reason under a cross."""
    broken = set(broken or ())
    reasons = reasons or {}
    items = ""
    for rule in rules:
        why = ""
        if rule.number in broken and rule.number in reasons:
            why = f'<span class="why">{esc(reasons[rule.number])}</span>'
        detail = (f'<span class="detail">{esc(rule.detail)}</span>'
                  if rule.detail else "")
        items += (f'<li class="{"no" if rule.number in broken else "ok"}">'
                  f'<span class="n">{rule.number}</span>'
                  f'<span>{esc(rule.text)}{detail}{why}</span></li>')
    count = len(broken)
    line = (f"every rule {word}" if not count else
            f"{count} rule{'s' if count != 1 else ''} not {word}")
    return f'<ol class="rules">{items}</ol><p class="caption">{line}</p>'


def checklist_card(t, book):
    """What the trade was held to, when it was held to anything."""
    if book is None:
        return ""
    entry = book.checklist(t.setup)
    parts = [f'<p class="meta">{esc(book.name or book.id)}'
             + (f' · <b>{esc(book.version)}</b>' if book.version else "")
             + (f' · {esc(t.setup)}' if t.setup else "") + "</p>"]
    if t.deviations is None:
        parts.append('<p class="muted">The rules were not ticked for this '
                     'trade.</p>')
    elif entry:
        parts.append(rules_list(entry, t.deviations, "met", t.reasons))
    if book.management and t.exit_deviations is not None:
        parts.append("<h3>Management</h3>"
                     + rules_list(book.management, t.exit_deviations, "held",
                                  t.reasons))
    return f'<div class="card"><h2>Checklist</h2>{"".join(parts)}</div>'


def plan_named(root, t):
    """The plan a trade followed, in the one line a plan is named by. A plan
    deleted since leaves nothing, and the trade is shown without the row: a
    document says what it can stand behind."""
    if not t.plan or not store.safe_dir_name(t.plan):
        return ""
    try:
        return store.load_plan(root, t.plan).label
    except (OSError, ValueError):
        return ""


def trade_facts(root, j, t):
    """The fields of a trade a reader is allowed to see, and only those.

    Risk stands in percent, which is what it is written as; what that percent
    was in money is the size of the account, and the account is not the
    subject here."""
    r = j.r(t.id)
    account = j.accounts[t.account].name if t.account in j.accounts else t.account
    rows = [("account", esc(account)),
            ("pair", pair(t.pair)),
            ("direction", esc(t.direction)),
            ("style", esc(t.style)),
            ("entry TF", esc(t.entry_tf)),
            ("execution", esc(", ".join(t.execution) or "-")),
            ("risk", f"{t.risk:g}%"),
            ("entry", esc(day_text(t.opened, t.opened_time))),
            ("exit", esc(day_text(t.closed, t.closed_time))),
            ("result", esc(t.result or "position open")),
            ("R", f'<b class="{r_class(r)}">{r_text(r)}</b>')]
    plan = plan_named(root, t)
    if plan:
        rows.append(("plan", esc(plan)))
    if t.playbook and (t.setup or t.playbook_version):
        rows.append(("setup", esc(" · ".join(x for x in (t.setup,
                                                         t.playbook_version) if x))))
    if t.note:
        rows.append(("note", esc(t.note)))
    return "".join(f'<tr><td class="dim">{esc(k)}</td><td>{v}</td></tr>'
                   for k, v in rows)


def ways_strip(near, place):
    """The buttons of a trade page, the way the journal draws its own: back
    to the list on the left, the trades either side on the right with the
    place of this one between them. A neighbour that is not there is a
    button that cannot be pressed, so the row keeps its shape on the first
    page and the last."""
    before, after = near or (None, None)
    def button(t, word):
        if t is None:
            return f'<span class="btn off">{word}</span>'
        return f'<a class="btn" href="#{anchor(t)}">{word}</a>'
    n, of = place or (0, 0)
    counted = f'<span class="place">{n} of {of}</span>' if of else ""
    return ('<nav class="ways"><a class="btn" href="#trades">&larr; the list</a>'
            '<span class="turn">'
            + button(before, "&larr; previous") + counted
            + button(after, "next &rarr;") + "</span></nav>")


def trade_card(root, j, t, book=None, carry=True, heading=None, near=None,
               place=None):
    """One trade whole: the facts, the checklist, the idea with its
    screenshots, the exit, the conclusions. In a file of many trades it is
    headed and stands as a page of its own, with the ways out above and
    below it: to the list, and to the trades on either side, `near` being
    the pair of them and `place` this trade's number and the count."""
    shots = trade_shots(root, t.id, carry)
    idea = ""
    for block in t.idea:
        pictures = "".join(shots.img(n, "idea screenshot") for n in block.images)
        idea += (f'<div class="block">'
                 + (f"<h3>{esc(block.tf)}</h3>" if block.tf else "")
                 + f'<div class="text">{bold(block.text)}</div>'
                 + (f'<div class="shots">{pictures}</div>' if pictures else "")
                 + "</div>")
    exits = "".join(shots.img(n, "exit screenshot") for n in t.exit_images)
    # a trade named by a heading stands in a list of trades: it takes the
    # anchor the list points at, and a way back to the list
    named = f'<h2>{esc(heading)}</h2>' if heading else ""
    ways = ways_strip(near, place) if heading else ""
    where = f' id="{anchor(t)}"' if heading else ""
    return (f'<section class="trade"{where}>{ways}'
            f'<div class="card">{named}'
            f'<p class="meta">{esc(t.id)}</p>'
            f'<table class="props">{trade_facts(root, j, t)}</table></div>'
            + checklist_card(t, book)
            + (f'<div class="card"><h2>Idea</h2>{idea}</div>' if idea else "")
            + (f'<div class="card"><h2>Exit moment</h2>'
               f'<div class="shots">{exits}</div></div>' if exits else "")
            + (f'<div class="card"><h2>Conclusions</h2>'
               f'<div class="text shots">{with_shots(t.conclusions, shots)}</div>'
               f'</div>' if t.conclusions.strip() else "")
            + ways + "</section>")


def slice_card(j, heading, rows):
    """A breakdown of the selection, in R. The column of money the journal
    prints here has no place in a document."""
    if not rows:
        return ""
    body = ""
    for value, s in rows:
        shown = pair(value) if heading == "By pair" else esc(value)
        wr = f"{s.wr:.1f}%" if s.decided else "-"
        body += (f'<tr><td>{shown}</td><td class="num">{s.trades}</td>'
                 f'<td class="num">{wr}</td>'
                 f'<td class="num {r_class(s.sum_r)}">{r_text(s.sum_r)}</td>'
                 f'<td class="num">{r_text(s.average_r)}</td></tr>')
    return (f'<div class="card"><h2>{esc(heading)}</h2>'
            f'<table><thead><tr><th></th><th class="num">trades</th>'
            f'<th class="num">WR</th><th class="num">Σ R</th>'
            f'<th class="num">EV</th></tr></thead><tbody>{body}</tbody>'
            f'</table></div>')


def slices(j, trades):
    """The four breakdowns worth reading without the journal around them."""
    cuts = [("By pair", lambda t: [t.pair]),
            ("By style", lambda t: [t.style]),
            ("By direction", lambda t: [t.direction]),
            ("By entry TF", lambda t: [t.entry_tf or "-"])]
    cards = ""
    for heading, key in cuts:
        cards += slice_card(j, heading, stats.by_values(j, trades, key))
    return f'<div class="twin">{cards}</div>' if cards else ""


# --- the whole file ---------------------------------------------------------

def document(title, lead, body, note=""):
    """The file itself: one column, its own styles, nothing fetched from
    anywhere. It opens with no journal running and no network."""
    made = datetime.now().strftime("%d.%m.%Y")
    foot = ("Written in Plainbook, a plain-text trading journal. "
            f"Exported {made}. Sums of money, balances and account sizes are "
            "deliberately left out: the figures here are in R, the risk taken "
            "on the trade.")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<link rel="icon" href="{FAVICON}"><style>{CSS}</style></head><body>
{flags.SPRITE}
<div class="sheet">
{note}
<div class="doc-head"><div class="brand">{mark(17)}plainbook</div>
<h1>{esc(title)}</h1>
<p class="lead">{lead}</p></div>
{body}
<p class="foot">{foot}</p>
</div>
</body></html>"""


def trade_document(root, j, t, book=None, carry=True, note=""):
    lead = " · ".join(x for x in (day_text(t.opened, False), t.style,
                                  t.result or "position open") if x)
    return document(f"{t.pair} {t.direction}".strip(), esc(lead),
                    trade_card(root, j, t, book, carry), note)


def trade_pages(root, j, trades, book_of, carry):
    """Every trade in full, each a page of its own that opens from the list:
    the file shows one at a time, and the heading of each leads to the list
    and to the trades on either side."""
    order = sorted(trades, key=lambda x: (x.closed or x.opened, x.opened))
    cards = ""
    for i, t in enumerate(order):
        near = (order[i - 1] if i else None,
                order[i + 1] if i + 1 < len(order) else None)
        cards += trade_card(root, j, t, book_of(t) if book_of else None, carry,
                            heading=f"{t.pair} {t.direction} · "
                                    f"{day_text(t.opened, False)}",
                            near=near, place=(i + 1, len(order)))
    return f'<div class="trades">{cards}</div>'


HOW_TO_OPEN = " Press a line to open the trade."


def selection_document(root, j, trades, title, lead, book_of=None,
                       shots=True, carry=True, note=""):
    """A stretch of the journal: the figures, the list, then every trade in
    full when the pictures are asked for."""
    closed = [t for t in trades if not t.is_open]
    s = stats.summary(j, closed)
    body = ('<div class="report">' + summary_tiles(s)
            + f'<div class="card" id="trades"><h2>The trades</h2>'
            f'{trades_table(j, trades, linked=shots)}'
            f'<p class="caption">{len(trades)} trade'
            f'{"" if len(trades) == 1 else "s"}, ordered by the exit.'
            f'{HOW_TO_OPEN if shots else ""}</p></div>'
            + slices(j, closed) + "</div>")
    if shots:
        body += trade_pages(root, j, trades, book_of, carry)
    return document(title, lead, body, note)


def report_document(root, j, r, text="", book_of=None, shots=False,
                    carry=True, note=""):
    """A month or a quarter as it is read in the journal, in R: the figures,
    the breakdowns, the trades, and the conclusions written under them."""
    closed = [t for t in r.trades if not t.is_open]
    # the period ends the moment the next one begins, so the day it is read
    # by is the one before that
    last = r.end - timedelta(days=1)
    lead = (f"{r.start:%d.%m.%Y} to {last:%d.%m.%Y} · "
            f"{r.total.trades} trade{'' if r.total.trades == 1 else 's'} closed")
    body = ('<div class="report">' + summary_tiles(r.total)
            + (f'<div class="card"><h2>Conclusions</h2>'
               f'<div class="text">{prose(text)}</div></div>' if text.strip() else "")
            + slices(j, closed)
            + f'<div class="card" id="trades"><h2>The trades</h2>'
            f'{trades_table(j, r.trades, linked=shots)}'
            f'<p class="caption">Every trade that closed inside the period, '
            f'ordered by the exit.{HOW_TO_OPEN if shots else ""}</p></div>'
            "</div>")
    if shots:
        body += trade_pages(root, j, r.trades, book_of, carry)
    return document(r.name, esc(lead), body, note)


CSS = f"""
*{{box-sizing:border-box}}
:root{{color-scheme:dark}}
body{{margin:0;background:{GROUND};color:{INK};
 font:13.5px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;
 -webkit-font-smoothing:antialiased}}
.sheet{{max-width:900px;margin:0 auto;padding:34px 22px 60px}}
h1{{font-size:26px;line-height:1.2;margin:0 0 6px;letter-spacing:-.01em}}
h2{{font-size:13px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
 color:{INK2};margin:0 0 12px}}
h3{{font-size:13px;margin:18px 0 8px;color:{INK}}}
p{{margin:0 0 10px}}
b,strong{{font-weight:600}}
.dim,.muted,.caption,.meta{{color:{DIM}}}
.caption{{font-size:12px;margin:10px 0 0}}
.meta{{font-size:12px;margin:0 0 12px}}
.good{{color:{GOOD}}}
.bad{{color:{BAD}}}
.num{{text-align:right;font-family:{MONO};font-variant-numeric:tabular-nums}}

.doc-head{{margin-bottom:22px;padding-bottom:18px;
 border-bottom:1px solid {AXIS}}}
.brand{{display:flex;align-items:center;gap:7px;color:{DIM};font-size:12px;
 letter-spacing:.04em;margin-bottom:14px}}
.brand .mark{{display:block}}
.lead{{color:{INK2};margin:0}}

.card{{background:{SURFACE};border:1px solid {EDGE};border-radius:6px;
 padding:16px 18px;margin-bottom:14px}}
.twin{{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}}
.twin .card{{margin-bottom:0}}
.twin{{margin-bottom:14px}}

.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));
 background:{SURFACE};border:1px solid {EDGE};border-radius:6px;
 overflow:hidden;margin-bottom:14px}}
.tile{{padding:12px 15px 13px;border-right:1px solid {EDGE};
 border-bottom:1px solid {EDGE};margin:0 -1px -1px 0}}
.tile .name{{color:{DIM};font-size:11px;letter-spacing:.06em;
 text-transform:uppercase}}
.tile .value{{font:600 21px/1.25 {MONO};margin-top:4px}}
.tile .sub{{color:{DIM};font-size:11.5px;margin-top:3px}}

table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{text-align:left;font-weight:600;color:{DIM};font-size:11px;
 letter-spacing:.05em;text-transform:uppercase;padding:0 10px 7px 0;
 border-bottom:1px solid {AXIS}}}
td{{padding:7px 10px 7px 0;border-bottom:1px solid {GRID};vertical-align:top}}
tr:last-child td{{border-bottom:none}}
th.num,td.num{{padding-right:0}}
table.props td:first-child{{width:150px;white-space:nowrap}}
table.list td{{white-space:nowrap}}
/* A file of many trades reads as pages: the report is one, and each trade
   is one of its own, opened from a line of the list and closed by the way
   back in its heading. The address of the page is the hash, so the browser's
   own Back works, and a file opened fresh shows the report. */
a.to{{color:{INK};text-decoration:none;border-bottom:1px solid {AXIS}}}
tr.go{{cursor:pointer}}
tr.go:hover td{{background:{RAISED}}}
tr.go:hover a.to{{border-color:{DIM}}}
.trade[id]{{display:none}}
.trade[id]:target{{display:block}}
.sheet:has(.trade[id]:target) .report{{display:none}}
.ways{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;
 justify-content:space-between;margin-bottom:14px}}
.ways .turn{{display:flex;gap:8px;align-items:center}}
.ways .place{{color:{DIM};font:12px/1 {MONO};font-variant-numeric:tabular-nums;
 padding:0 6px}}
.btn{{display:inline-block;background:transparent;border:1px solid {AXIS};
 color:{INK2};padding:5px 11px;border-radius:4px;cursor:pointer;
 font:12px/1.4 system-ui,sans-serif;letter-spacing:.01em;white-space:nowrap;
 text-decoration:none}}
.btn:hover{{border-color:{DIM};color:{INK}}}
.btn.off,.btn.off:hover{{color:{DIM};border-color:{GRID};cursor:default;
 opacity:.6}}
/* the strip under the trade is the one you reach after the pictures; the
   card above it has its own gap */
.trade>.ways:last-child{{margin:0 0 14px}}
.sprite{{position:absolute;width:0;height:0;overflow:hidden}}
.pair{{display:inline-flex;align-items:center;gap:7px;white-space:nowrap}}
.pair .pi{{flex:none;display:block}}

.text{{white-space:normal;overflow-wrap:anywhere}}
.block{{margin-bottom:20px}}
.block:last-child{{margin-bottom:0}}
.shots{{display:flex;flex-direction:column;gap:12px;margin-top:12px}}
.shots img{{display:block;width:100%;height:auto;border:1px solid {AXIS};
 border-radius:5px;background:{GROUND}}}

ol.rules{{list-style:none;margin:0;padding:0;counter-reset:none}}
ol.rules li{{display:flex;gap:10px;padding:7px 0;
 border-bottom:1px solid {GRID}}}
ol.rules li:last-child{{border-bottom:none}}
ol.rules .n{{flex:none;width:22px;height:22px;border-radius:50%;
 display:inline-flex;align-items:center;justify-content:center;
 font:600 11px/1 {MONO};border:1px solid {AXIS};color:{DIM}}}
ol.rules li.ok .n{{color:{GOOD};border-color:rgba(72,172,122,.45)}}
ol.rules li.no .n{{color:{BAD};border-color:rgba(208,92,85,.5)}}
ol.rules li.no{{color:{INK}}}
ol.rules .detail,ol.rules .why{{display:block;color:{DIM};font-size:12px;
 margin-top:2px}}
ol.rules .why{{color:{WARN}}}
ul{{margin:0 0 10px;padding-left:18px}}

.foot{{color:{DIM};font-size:11.5px;line-height:1.6;margin-top:26px;
 padding-top:14px;border-top:1px solid {AXIS}}}

/* The bar the journal shows above a preview. It is not part of the file that
   is sent: it is added by the server for the page you look at first. */
.bar{{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:9px;
 align-items:center;background:{RAISED};border:1px solid {AXIS};
 border-radius:6px;padding:11px 14px;margin-bottom:22px}}
.bar .word{{color:{INK2};font-size:12px;margin-right:auto}}
.bar a{{display:inline-block;border:1px solid {AXIS};border-radius:4px;
 padding:5px 11px;color:{INK2};font-size:12px;text-decoration:none;
 white-space:nowrap}}
.bar a:hover{{border-color:{DIM};color:{INK}}}
.bar a.primary{{background:{ACCENT};border-color:{ACCENT};color:#07080c;
 font-weight:600}}
.bar a.on{{border-color:{ACCENT};color:{INK}}}
/* the button while the file is being built: still the button, visibly not
   waiting for another press */
.bar a.busy,.bar a.busy:hover{{background:{RAISED};border-color:{ACCENT};
 color:{INK2};cursor:progress;font-weight:400}}

@media (max-width:760px){{
 .twin{{grid-template-columns:1fr}}
 .sheet{{padding:20px 14px 40px}}
 table.list td,table.list th{{white-space:normal}}
}}

/* Paper. The journal is dark because a screen at night is looked at for
   hours; a printer would spend a cartridge on that ground, and a PDF made
   from it is unreadable on paper. So print inverts the theme and drops
   everything that only helps on a screen. */
@media print{{
 :root{{color-scheme:light}}
 body{{background:#fff;color:#16161a;font-size:10.5pt}}
 .sheet{{max-width:none;padding:0}}
 .bar,.ways{{display:none}}
 a.to{{border:none}}
 .trade[id],.report{{display:block}}
 h1{{font-size:20pt}}
 h2{{color:#5c5c66}}
 .dim,.muted,.caption,.meta,.tile .name,.tile .sub,.foot{{color:#5c5c66}}
 .good{{color:#1d7a4f}}
 .bad{{color:#a8342d}}
 h3,ol.rules li.no{{color:#16161a}}
 .card,.tiles{{background:#fff;border-color:#d5d5dc}}
 .tile{{border-color:#d5d5dc}}
 /* A card is not held together: one with three chart screenshots in it is
    taller than a sheet, and a card that refuses to be cut leaves the page
    before it empty. What must not be cut is a picture, a row and a rule. */
 tr,.tile,ol.rules li,.block h3{{break-inside:avoid;page-break-inside:avoid}}
 h1,h2,h3{{break-after:avoid;page-break-after:avoid}}
 th{{border-color:#c8c8d0}}
 td{{border-color:#e6e6ec}}
 ol.rules li{{border-color:#e6e6ec}}
 ol.rules .n{{border-color:#c8c8d0}}
 .shots img{{border-color:#d5d5dc;background:#fff;
  break-inside:avoid;page-break-inside:avoid}}
 .doc-head{{border-color:#c8c8d0}}
 .foot{{border-color:#c8c8d0}}
 /* a trade starts its own sheet, the way a folder of printed trades is read:
    one trade, one page. Written off what stands before it, so that a document
    of a single trade does not put a page break under its own title */
 .card + .trade,.twin + .trade,.trade + .trade{{
  break-before:page;page-break-before:always}}
 .trade .card{{border:none;padding:0 0 14px}}
}}
@page{{margin:14mm}}
"""
