#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The local journal server. 127.0.0.1 only, port 8778 (PLAINBOOK_PORT changes it).

Run:   python3 -m plainbook.server
Open:  http://127.0.0.1:8778
"""
import csv
import http.server
import io
import json
import os
import re
import shutil
import threading
import time
import urllib.parse
from datetime import datetime, timedelta

from . import html as H
from . import reports, stats, store
from .balances import Journal
from .model import (Trade, Account, Adjustment, IdeaBlock, Card, Week, Graded,
                    Plan, RecordError, DIRECTIONS, RESULTS, NARRATIVES,
                    CARD_SECTIONS, WEEK_SECTIONS, ASSESSMENT_ROWS, TRADE_KEYS,
                    PAIR_NOT_SET)

PORT = int(os.environ.get("PLAINBOOK_PORT") or 8778)
# the journal root can be overridden; the tests and a split data folder use it
ROOT = os.path.abspath(os.environ.get("PLAINBOOK_ROOT") or
                       os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DRAFTS = os.path.join(ROOT, ".drafts")
# money moved by hand. A correction is not offered here: it has a form of its
# own, where the real balance is typed in and the difference is worked out.
MONEY_KINDS = ["deposit", "withdrawal", "fee"]
esc = H.esc
Safe = H.Safe


def amount(j, x, account=None, signed=False):
    """A sum of money with its currency: the account's own, or the one every
    account shares when the figure spans accounts. When they share none the
    number stands alone, because a sum of two currencies has no name."""
    if x is None:
        return "-"
    return f"{H.money(x, signed)} {H.sign(j.currency(account))}".rstrip()


def offered(kind, *own):
    """A list of the trade form, plus what the trade being edited carries.

    A word the owner took out of a list must not vanish from a trade that has
    it: the form sends back what it shows, so a checkbox that is not drawn is a
    deletion."""
    words = store.all_words(ROOT, kind)
    return words + [w for w in own if w and w not in words]

_cache = {"journal": None, "time": 0.0}


def journal(fresh=False):
    """The journal is re-read from disk: the files are the source of truth."""
    if fresh or _cache["journal"] is None or time.time() - _cache["time"] > 2:
        _cache["journal"] = Journal.load(ROOT)
        _cache["time"] = time.time()
    return _cache["journal"]


def drop_cache():
    _cache["journal"] = None


# What the journal answers after a form: the word travels in the address of the
# redirect (`?said=`), the handler takes it out of the query before any page
# sees it, and every page draws it the same way. A thread of its own per
# request, which is what the server gives us.
SAID = threading.local()


def said_box():
    """The message, and the address cleaned of it.

    The word travels in the query, so a page reloaded an hour later would say
    "Trade opened" again. It is taken out of the address as the page appears,
    which is what history.replaceState is for."""
    text = getattr(SAID, "text", "")
    if not text:
        return ""
    return (f'<div class="toast" role="status">{esc(text)}</div>'
            f'<script>history.replaceState({{}}, "", '
            f'{json.dumps(getattr(SAID, "url", "/"))})</script>')


def page(title, body, tab="journal", header_right="", problems=()):
    """A page with the journal's warnings on top of it.

    A record that failed to load is named on every page rather than in a log:
    the figures on the page are missing it, and the person has to know."""
    found = list(journal().problems) + list(problems)
    notice = ""
    if found:
        rows = "".join(f'<li><code>{esc(path)}</code>: {esc(why)}</li>'
                       for path, why in found)
        n = len(found)
        notice = (f'<div class="notice"><b>{n} record{"" if n == 1 else "s"} '
                  f'could not be read</b> and {"is" if n == 1 else "are"} left '
                  f'out of every figure until the file is fixed. '
                  f'<span class="caption">python3 tools/check_journal.py checks '
                  f'the whole journal the same way.</span><ul>{rows}</ul></div>')
    return H.page(title, body, tab, header_right, notice, said_box())


# --- filters ---------------------------------------------------------------

# (form field name, object attribute, label in the interface)
FILTER_FIELDS = [("account", "account", "account"), ("pair", "pair", "pair"),
                 ("style", "style", "style"), ("direction", "direction", "direction"),
                 ("result", "result", "result")]


def apply_filters(j, q):
    trades = list(j.trades)
    for name, attr, _ in FILTER_FIELDS:
        value = (q.get(name) or [""])[0]
        if value:
            if name == "result" and value == "open":
                trades = [t for t in trades if t.is_open]
            else:
                trades = [t for t in trades if getattr(t, attr) == value]
    since = (q.get("from") or [""])[0]
    until = (q.get("to") or [""])[0]
    if since:
        trades = [t for t in trades if f"{t.opened:%Y-%m}" >= since]
    if until:
        trades = [t for t in trades if f"{t.opened:%Y-%m}" <= until]
    return trades


def filter_form(j, q):
    values = {name: (q.get(name) or [""])[0] for name, _, _ in FILTER_FIELDS}
    choices = {
        "account": sorted(j.accounts),
        "pair": sorted({t.pair for t in j.trades}),
        "style": sorted({t.style for t in j.trades}),
        "direction": list(DIRECTIONS),
        "result": list(RESULTS) + ["open"],
    }
    parts = ['<form class="filters" method="get" action="/">']
    group = (q.get("group") or [""])[0]
    if group:
        parts.append(f'<input type="hidden" name="group" value="{esc(group)}">')
    for name, _, label in FILTER_FIELDS:
        options = '<option value="">all</option>' + "".join(
            f'<option value="{esc(v)}"{" selected" if v == values[name] else ""}>'
            f'{esc(v)}</option>' for v in choices[name])
        parts.append(f'<div><label>{label}</label>'
                     f'<select name="{name}">{options}</select></div>')
    months = stats.months(j.trades)
    for name, label in (("from", "from month"), ("to", "to month")):
        current = (q.get(name) or [""])[0]
        options = '<option value="">-</option>' + "".join(
            f'<option value="{m}"{" selected" if m == current else ""}>{m}</option>'
            for m in months)
        parts.append(f'<div><label>{label}</label>'
                     f'<select name="{name}">{options}</select></div>')
    parts.append('<div><button class="btn primary">Show</button></div>')
    parts.append('<div><a class="btn" href="/">Reset</a></div>')
    parts.append("</form>")
    return "".join(parts)


# --- grouping by period ----------------------------------------------------

GROUPS = [("week", "Weeks"), ("month", "Months"), ("quarter", "Quarters")]


def group_key(date, group):
    if group == "week":
        return stats.week(date)
    if group == "quarter":
        return stats.quarter(date)
    return f"{date:%Y-%m}"


def group_label(key, group, sample):
    """(label, dates) for the total row. sample is any trade of the group: the
    calendar bounds of a week cannot be recovered from the key alone."""
    if group == "week":
        monday = sample.opened - timedelta(days=sample.opened.weekday())
        return key.split("-")[1], f"{monday:%d.%m} - {monday + timedelta(days=6):%d.%m.%Y}"
    if group == "quarter":
        year, q = key.split("-")
        return f"{q} {year}", ""
    year, month = key.split("-")
    return f"{reports.MONTH_NAMES[int(month) - 1]} {year}", ""


def group_switch(q, current):
    parts = []
    for code, name in GROUPS:
        params = {k: v[:] for k, v in q.items()}
        params["group"] = [code]
        href = "/?" + urllib.parse.urlencode(params, doseq=True)
        parts.append(f'<a class="{"current" if code == current else ""}" '
                     f'href="{href}">{name}</a>')
    return '<div class="switch">' + "".join(parts) + "</div>"


FUNNEL = ('<svg viewBox="0 0 16 16" width="13" height="13" fill="none" '
          'stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" '
          'aria-hidden="true"><path d="M2 3h12l-4.6 5.4v4.6l-2.8 1.5V8.4L2 3z"/>'
          '</svg>')


def active_filters(q):
    names = [name for name, _, _ in FILTER_FIELDS] + ["from", "to"]
    return sum(1 for name in names if (q.get(name) or [""])[0])


def filters_box(j, q):
    """The filters hide behind a button: the list matters on the front page,
    not the form.

    Since the form is out of sight, the button has to show that a filter is on,
    or it is a mystery why there are so few trades. Hence the accent and the
    count on the button."""
    count = active_filters(q)
    badge = f'<span class="badge">{count}</span>' if count else ""
    return (f'<details class="filters-box">'
            f'<summary class="btn icon{" active" if count else ""}" '
            f'title="Filters">{FUNNEL}{badge}</summary>'
            f'<div class="popover">{filter_form(j, q)}</div></details>')


# --- front page ------------------------------------------------------------

def result_class(t):
    return {"Win": "win", "Lose": "lose", "BE": "flat"}.get(t.result, "muted")


def link_cell(href, inner, cls=""):
    """A table cell that is entirely a link, padding included.

    The link fills the cell instead of sitting inside it, so a row is opened by
    clicking anywhere on it and not only on the few characters of the date."""
    return f'<td class="{("cell " + cls).strip()}"><a href="{href}">{inner}</a></td>'


def trade_row(j, t):
    r = j.r(t.id)
    href = f"/trade/{U(t.id)}"
    cells = [(f"{t.opened:%d.%m.%Y}", ""), (esc(t.account), ""),
             (H.pair(t.pair), ""), (esc(t.direction), ""), (esc(t.style), ""),
             (esc(t.entry_tf), ""), (f"{t.risk:g}%", "num"),
             (esc(t.result or "open"), result_class(t)),
             (H.money(t.pnl, signed=True), f"num {result_class(t)}"),
             ("-" if r is None else f"{r:+.2f}", "num")]
    return ("<tr>" + "".join(link_cell(href, inner, cls) for inner, cls in cells)
            + "</tr>")


def sum_class(x):
    return "win" if x > 0 else "lose" if x < 0 else "muted"


def trades_table(j, trades, group="week"):
    if not trades:
        return '<p class="muted">Nothing matches the filter.</p>'
    rows = ['<table><thead><tr><th>date</th><th>account</th><th>pair</th>'
            '<th>direction</th><th>style</th><th>TF</th><th class="num">risk</th>'
            f'<th>result</th><th class="num">PnL {H.sign(j.currency())}</th>'
            '<th class="num">R</th></tr></thead><tbody>']
    buckets = {}
    for t in trades:
        buckets.setdefault(group_key(t.opened, group), []).append(t)
    for key in sorted(buckets, reverse=True):
        batch = sorted(buckets[key], key=lambda t: t.opened, reverse=True)
        s = stats.summary(j, batch)
        label, dates = group_label(key, group, batch[0])
        wr = f"WR {s.wr:.0f}%" if s.decided else "-"
        rows.append(
            f'<tr class="group"><td colspan="7">'
            f'<span class="label">{esc(label)}</span>'
            f'<span class="dates">{esc(dates)}</span>'
            f'<span class="dates">{len(batch)} trades</span></td>'
            f'<td>{wr}</td>'
            f'<td class="num {sum_class(s.sum_pnl)}">'
            f'{H.money(s.sum_pnl, signed=True)}</td>'
            f'<td class="num {sum_class(s.sum_r)}">{s.sum_r:+.2f}</td></tr>')
        rows += [trade_row(j, t) for t in batch]
    return "".join(rows) + "</tbody></table>"


def period_tile(j, trades, group):
    """The total of the current week (month, quarter): what you look at first."""
    name = {"week": "this week", "month": "this month",
            "quarter": "this quarter"}[group]
    key = group_key(datetime.now(), group)
    inside = [t for t in trades if group_key(t.opened, group) == key]
    s = stats.summary(j, inside)
    if not inside:
        return (f'<div class="tile"><div class="name">{name}</div>'
                f'<div class="value muted">-</div>'
                f'<div class="sub">no trades yet</div></div>')
    sub = f"{len(inside)} trades"
    if s.decided:
        sub += f" · WR {s.wr:.0f}%"
    if s.trades:
        sub += f" · {amount(j, s.sum_pnl, signed=True)}"
    still_open = len(inside) - s.trades
    if still_open:
        sub += f" · {still_open} open"
    return (f'<div class="tile"><div class="name">{name}</div>'
            f'<div class="value {sum_class(s.sum_r)}">{s.sum_r:+.2f} R</div>'
            f'<div class="sub">{esc(sub)}</div></div>')


def account_tiles(j):
    """Balances of the live accounts. Archived ones are not on the front page:
    the account is done with and there is nothing to watch, so it stays in the
    statistics and in the history."""
    parts = []
    for a in sorted(j.accounts):
        account = j.accounts[a]
        if account.archived:
            continue
        # Start balance, current balance and the difference in colour. Turning
        # the risk percent into dollars is done in the head, no line for it here.
        #
        # The difference is what the account earned, not simply balance minus
        # start: money paid out would otherwise read as a loss. The line adds
        # up exactly, start + result + added - cashed out is the balance.
        balance = j.balance(a)
        result = j.result(a)
        colour = H.GOOD if result >= 0 else H.BAD
        moved = ""
        if j.deposited(a):
            moved += f' · added {amount(j, j.deposited(a), a)}'
        if j.cashed_out(a):
            moved += f' · cashed out {amount(j, j.cashed_out(a), a)}'
        cls, limit = daily_limit_state(j, account)
        parts.append(
            f'<div class="tile{cls}"><div class="name">{esc(account.name or a)}</div>'
            f'<div class="value">{amount(j, balance, a)}</div>'
            f'<div class="sub">start {amount(j, account.start_balance, a)} · '
            f'<span style="color:{colour}">{amount(j, result, a, signed=True)}</span>'
            f'{moved}</div>{limit}</div>')
    return '<div class="tiles narrow">' + "".join(parts) + "</div>"


def daily_limit_state(j, account, now=None):
    """How close an account stands to its daily loss limit: (tile class, line).

    A prop firm closes the account for a day that loses more than the limit,
    and the loss it counts is the closed one plus whatever is still at risk in
    the market. So both are added up: what today has cost, and what the open
    trades could still cost at their stops. The tile turns amber at four
    fifths of the limit and red past it."""
    limit = account.daily_loss_limit
    if not limit:
        return "", ""
    now = now or datetime.now()
    closed = j.closed_on(account.id, now)
    at_risk = j.open_risk(account.id)
    used = max(0.0, -closed) + at_risk
    words = f"today {amount(j, closed, account.id, signed=True)}"
    if at_risk:
        words += f", {amount(j, at_risk, account.id)} at risk in open trades"
    words += f" · limit {amount(j, limit, account.id)}"
    cls = " over" if used >= limit else " warn" if used >= 0.8 * limit else ""
    if cls == " over":
        words = "daily loss limit reached: " + words
    return cls, f'<div class="sub">{esc(words)}</div>'


def open_positions(j):
    open_trades = j.open_trades()
    if not open_trades:
        return ""
    rows = "".join(
        "<tr>" + "".join(
            link_cell(f"/trade/{U(t.id)}", inner, cls) for inner, cls in
            [(f"{t.opened:%d.%m.%Y %H:%M}" if t.opened_time
              else f"{t.opened:%d.%m.%Y}", ""), (esc(t.account), ""),
             (H.pair(t.pair), ""), (esc(t.direction), ""), (esc(t.style), ""),
             (f"{t.risk:g}%", "num"),
             (amount(j, j.computed[t.id].risk_money, t.account), "num")])
        + f'<td><a class="btn" href="/close/{U(t.id)}">Close</a></td></tr>'
        for t in open_trades)
    return (f'<div class="card is-open"><h2>Open positions: {len(open_trades)}</h2>'
            f'<table><thead><tr><th>entry</th><th>account</th><th>pair</th>'
            f'<th>direction</th><th>style</th><th class="num">risk</th>'
            f'<th class="num">in money</th><th></th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def winrate_tile(name, styles, j, trades):
    """Winrate over a subset of styles. An empty selection gets a dash, not 0%.

    Under the number there are only three figures: wins, losses, break-evens.
    Which is which is told by colour, no labels needed."""
    s = stats.summary(j, [t for t in trades if styles is None or t.style in styles])
    if not s.trades:
        return (f'<div class="tile"><div class="name">{esc(name)}</div>'
                f'<div class="value muted">-</div>'
                f'<div class="sub muted">no trades</div></div>')
    sub = (f'<span class="breakdown"><span class="win">{s.wins}</span> / '
           f'<span class="lose">{s.losses}</span> / '
           f'<span class="be">{s.be}</span></span>')
    value = f"{s.wr:.1f}%" if s.decided else "-"
    return (f'<div class="tile"><div class="name">{esc(name)}</div>'
            f'<div class="value">{value}</div>'
            f'<div class="sub">{sub}</div></div>')


def streak_tile(j, trades):
    """The run the selection is on now, and the longest runs it has had."""
    best_win, best_loss, (kind, n) = stats.streaks(j, trades)
    if not kind:
        return ('<div class="tile"><div class="name">streak</div>'
                '<div class="value muted">-</div>'
                '<div class="sub muted">no decided trades</div></div>')
    word = ("win" if n == 1 else "wins") if kind == "Win" else \
           ("loss" if n == 1 else "losses")
    return (f'<div class="tile"><div class="name">streak</div>'
            f'<div class="value {"win" if kind == "Win" else "lose"}">{n} {word}'
            f'</div><div class="sub">longest: {best_win} wins, {best_loss} losses'
            f'</div></div>')


def export_csv(j, trades):
    """The selection as a table for a spreadsheet: every stored field and the
    figures worked out from them, one trade per line."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([key for _, key in TRADE_KEYS if key != "notion id"]
               + ["R", "balance at entry", "risk in money", "currency"])
    for t in trades:
        c = j.computed[t.id]
        r = j.r(t.id)
        w.writerow([t.id, t.account, t.pair, t.direction, t.style, t.entry_tf,
                    "; ".join(t.execution), f"{t.risk:g}",
                    store._date_to_text(t.opened, t.opened_time),
                    t.result or "", "" if t.pnl is None else f"{t.pnl:g}",
                    store._date_to_text(t.closed, t.closed_time),
                    t.note, t.plan,
                    "" if r is None else f"{r:.4f}",
                    f"{c.balance_at_entry:.2f}", f"{c.risk_money:.2f}",
                    j.currency(t.account)])
    return out.getvalue()


def home_page(q):
    j = journal()
    trades = apply_filters(j, q)
    group = (q.get("group") or [""])[0]
    if group not in dict(GROUPS):
        group = "week"
    s = stats.summary(j, trades)
    styles = store.all_words(ROOT, "styles")
    # a style of the list gets a tile once it has trades: a row of empty tiles
    # says nothing and pushes the ones that count off the screen
    traded = [name for name in styles if any(t.style == name for t in j.trades)]
    tiles = (f'<div class="tiles">'
             + period_tile(j, trades, group)
             + f'<div class="tile"><div class="name">selection</div>'
             f'<div class="value">{s.trades}</div><div class="sub">trades</div></div>'
             # the styles come from the list on the Accounts tab: one added
             # or dropped there is added or dropped here as well
             + winrate_tile("winrate overall", None, j, trades)
             + "".join(winrate_tile(f"winrate {name}", (name,), j, trades)
                       for name in traded)
             # There is deliberately no total in money here: it would add up the
             # dollars of a prop account and of your own, and those are different
             # kinds of money. The total of a selection is honestly said in R.
             + f'<div class="tile"><div class="name">total R</div>'
             f'<div class="value">{s.sum_r:+.2f}</div>'
             f'<div class="sub">average {s.average_r:+.2f} R</div></div>'
             + streak_tile(j, trades) + '</div>')
    today = datetime.now().strftime("%Y-%m-%d")
    # Building a report belongs on the Reports tab, where the form for it is.
    # The header is for what is written before the market, not after it.
    right = ('<a class="btn primary" href="/new">+ Trade</a>'
             '<a class="btn" href="/plan/new">+ Plan</a>'
             f'<a class="btn" href="/card/{today}">+ DRC</a>'
             f'<a class="btn" href="/week/{stats.week(datetime.now())}">+ WRC</a>')
    # the same selection as a file: a spreadsheet gets the filtered list
    export = "/export.csv" + ("?" + urllib.parse.urlencode(
        {k: v for k, v in q.items() if k != "group"}, doseq=True)
        if any(k != "group" for k in q) else "")
    head = (f'<div class="card-head"><h2>Trades</h2>'
            f'<span class="right">{filters_box(j, q)}'
            f'{group_switch(q, group)}'
            f'<a class="btn" href="{esc(export)}" title="the selection as CSV">'
            f'CSV</a></span></div>')
    body = (account_tiles(j) + open_positions(j) + tiles +
            '<div class="card">' + head +
            trades_table(j, trades, group) + "</div>")
    return page("Journal", body, "journal", right)


# --- trade page ------------------------------------------------------------

def trade_page(trade_id):
    j = journal()
    t = next((x for x in j.trades if x.id == trade_id), None)
    if t is None:
        return None
    computed = j.computed[t.id]
    r = j.r(t.id)
    fields = [("account", j.accounts[t.account].name
               if t.account in j.accounts else t.account),
              ("pair", H.pair(t.pair)), ("direction", t.direction),
              ("style", t.style),
              ("entry TF", t.entry_tf), ("execution", ", ".join(t.execution) or "-"),
              ("risk", f"{t.risk:g}% = {amount(j, computed.risk_money, t.account)}"),
              ("balance at entry", amount(j, computed.balance_at_entry, t.account)),
              ("entry", f"{t.opened:%d.%m.%Y %H:%M}" if t.opened_time
               else f"{t.opened:%d.%m.%Y}"),
              ("exit", ("-" if not t.closed else
                        f"{t.closed:%d.%m.%Y %H:%M}" if t.closed_time
                        else f"{t.closed:%d.%m.%Y}")),
              ("result", t.result or "position open"),
              ("PnL", amount(j, t.pnl, t.account, signed=True)),
              ("R", f"{r:+.2f}" if r is not None else "-")]
    table = "".join(f'<tr><td class="muted">{esc(k)}</td><td>{esc(v)}</td></tr>'
                    for k, v in fields)
    if t.plan:
        table += (f'<tr><td class="muted">plan</td><td>'
                  f'<a href="/plan/{U(t.plan)}">{esc(plan_title(t.plan))}</a>'
                  f'</td></tr>')
    if t.note:
        table += f'<tr><td class="muted">note</td><td>{esc(t.note)}</td></tr>'

    idea = ""
    for block in t.idea:
        images = "".join(f'<img src="/shot/{U(t.id)}/{U(os.path.basename(s))}" '
                         f'alt="idea screenshot">' for s in block.images)
        idea += (f'<div class="idea-block">'
                 f'{f"<h3>{esc(block.tf)}</h3>" if block.tf else ""}'
                 f'<div>{esc(block.text).replace(chr(10), "<br>")}</div>'
                 f'<div class="shots">{images}</div></div>')
    exit_shots = "".join(
        f'<img src="/shot/{U(t.id)}/{U(os.path.basename(s))}" alt="exit screenshot">'
        for s in t.exit_images)
    conclusions = re.sub(r"!\[\]\(([^)]+)\)",
                         lambda m: f'<img src="/shot/{U(t.id)}/'
                                   f'{U(os.path.basename(m.group(1)))}" alt="screenshot">',
                         esc(t.conclusions)).replace("\n", "<br>")

    buttons = (f'<a class="btn" href="/edit/{U(t.id)}">Edit</a>'
               f'<form method="post" action="/trade/{U(t.id)}/delete" '
               f'style="display:inline" onsubmit="return confirm('
               f'\'Delete trade {esc(t.id)}? The folder moves to .trash.\')">'
               f'<button class="btn danger">Delete</button></form>')
    if t.is_open:
        buttons = (f'<a class="btn primary" href="/close/{U(t.id)}">Close trade</a>'
                   + buttons)
    body = (f'<div class="card{" is-open" if t.is_open else ""}">'
            f'<h2>{esc(t.id)}</h2><table class="props">{table}</table></div>'
            + (f'<div class="card"><h2>Idea</h2>{idea}</div>' if idea else "")
            + (f'<div class="card"><h2>Exit moment</h2>'
               f'<div class="shots">{exit_shots}</div></div>' if exit_shots else "")
            + (f'<div class="card"><h2>Conclusions</h2>'
               f'<div class="shots">{conclusions}</div>'
               f'</div>' if t.conclusions.strip() else ""))
    return page(t.id, body, "journal", buttons)


# --- statistics ------------------------------------------------------------

def account_tabs(j, q, selected):
    """The account switch above the chart. It reuses the account filter, so the
    choice also applies to the tables below.

    Archived accounts are not offered: the account is done with and there is
    nothing left to watch on its curve. One picked by hand through the filter
    still gets its tab, or the page would answer a choice it does not show."""
    shown = [a for a in sorted(j.accounts)
             if not j.accounts[a].archived or a == selected]
    parts = []
    for code, name in [("", "All accounts")] + [(a, j.accounts[a].name or a)
                                                for a in shown]:
        params = {k: v[:] for k, v in q.items()}
        if code:
            params["account"] = [code]
        else:
            params.pop("account", None)
        href = "/stats" + ("?" + urllib.parse.urlencode(params, doseq=True)
                           if params else "")
        cls = "btn primary" if code == selected else "btn"
        parts.append(f'<a class="{cls}" href="{href}">{esc(name)}</a>')
    return '<p style="margin:0 0 10px">' + " ".join(parts) + "</p>"


def ring(title, rows, steps, kind):
    """One ring of the R distribution, with its slices written out beside it."""
    total = sum(n for _, n, _ in rows)
    coloured = [(label, n, sum_r, steps[i % len(steps)])
                for i, (label, n, sum_r) in enumerate(rows)]
    if not total:
        return (f'<div class="ring"><h3>{esc(title)}</h3>'
                f'<p class="muted">None yet.</p></div>')
    sum_r = sum(r for _, _, r in rows)
    return (f'<div class="ring"><h3>{esc(title)}</h3>'
            f'<div class="ring-body">'
            f'{H.donut_svg([(label, n, colour) for label, n, _, colour in coloured], middle=str(total), under=f"{sum_r:+.1f} R")}'
            f'{H.donut_legend(coloured, total)}</div></div>')


def r_rings(j, trades):
    """Where the trades landed by the size of R: losses in one ring, wins in
    the other. The share of a bucket is read off the ring directly, instead of
    being measured against the tallest bar of a histogram."""
    losses, wins, be = stats.r_split(j, trades)
    if not sum(n for _, n, _ in losses) and not sum(n for _, n, _ in wins):
        return ('<div class="card"><h2>R distribution</h2>'
                '<p class="muted">Nothing to plot yet.</p></div>')
    s = stats.summary(j, trades)
    head = (f'{s.trades} closed · {s.wins} won · {s.losses} lost'
            + (f' · {be} break-even' if be else ''))
    return (f'<div class="card"><h2>R distribution</h2>'
            f'<p class="caption">{esc(head)}</p>'
            f'<div class="rings">'
            f'{ring("Losses", losses, H.LOSS_STEPS, "lose")}'
            f'{ring("Wins", wins, H.WIN_STEPS, "win")}'
            f'</div>'
            f'<p class="caption">Each ring is one pile of trades cut by the size '
            f'of R: the further from zero, the brighter the slice. In the middle '
            f'of a ring stands the number of trades in it and their total R. '
            f'Break-even trades are in neither ring; they ended at zero. On the '
            f'losses, -1 to -1.2 R is the stop as designed, since commission and '
            f'swap are paid on top of it; a loss past -1.2 R was not the stop '
            f'but too much size.</p>'
            f'</div>')


def streaks_card(j, trades):
    best_win, best_loss, (kind, n) = stats.streaks(j, trades)
    now = "-" if not kind else f'{n} {"wins" if kind == "Win" else "losses"}'
    tiles = "".join(
        f'<div class="tile"><div class="name">{name}</div>'
        f'<div class="value {cls}">{value}</div></div>'
        for name, value, cls in (("longest run of wins", best_win or "-", "win"),
                                 ("longest run of losses", best_loss or "-", "lose"),
                                 ("the run now", now,
                                  "win" if kind == "Win" else "lose" if kind else "muted")))
    return (f'<div class="card"><h2>Streaks</h2><div class="tiles">{tiles}</div>'
            f'<p class="caption" style="margin:10px 0 0">Counted in the order the '
            f'trades closed. A break-even neither extends a run nor breaks it.'
            f'</p></div>')


def stats_page(q):
    j = journal()
    trades = apply_filters(j, q)
    selected = (q.get("account") or [""])[0]
    # with a month filter the curve begins at the balance the account entered
    # that month with, not at the day the account was opened
    since_key = (q.get("from") or [""])[0]
    since = datetime.strptime(since_key + "-01", "%Y-%m-%d") if since_key else None

    # One account gets a large chart with its own scale: you see the swings, not
    # a flat line. All accounts get a picture each: their magnitudes differ, and
    # on one scale the small moves of a small account vanish next to a 100k prop.
    filtered = any((q.get(name) or [""])[0] for name, _, _ in FILTER_FIELDS
                   if name != "account")
    how = (' With a filter on, only the chosen trades move the line from the '
           'first month on: it shows what those trades alone did to the '
           'account, over the balance everything before them had built.'
           if filtered or since else '')
    if selected and selected in j.accounts:
        points = stats.equity(j, selected, trades, since)
        name = j.accounts[selected].name or selected
        charts = (f'<div class="card"><h2>Equity: {esc(name)}</h2>'
                  f'{account_tabs(j, q, selected)}'
                  f'{H.equity_svg([(name, H.SERIES[0], points)], height=300, cid="acc")}'
                  + (f'<p class="caption">{how.strip()}</p>' if how else '')
                  + '</div>')
    else:
        cards = ""
        for i, a in enumerate(sorted(j.accounts)):
            if j.accounts[a].archived:
                continue
            points = stats.equity(j, a, trades, since)
            if not points:
                continue
            name = j.accounts[a].name or a
            cards += (f'<h3>{esc(name)}</h3>'
                      f'{H.equity_svg([(name, H.SERIES[i % len(H.SERIES)], points)], height=190, cid=f"acc-{i}")}')
        charts = (f'<div class="card"><h2>Equity by account</h2>'
                  f'{account_tabs(j, q, "")}'
                  f'{cards or "<p class=\'muted\'>Nothing to plot yet.</p>"}'
                  f'<p class="caption">Each account has its own scale, which is '
                  f'why they are drawn separately. Archived accounts are not '
                  f'drawn; their trades stay in the figures below.{how}</p></div>')

    slices = ""
    for heading, key, show in (("By style", lambda t: t.style, esc),
                               ("By pair", lambda t: t.pair, H.pair),
                               ("By account", lambda t: t.account, esc)):
        rows = "".join(
            f'<tr><td>{show(v)}</td><td class="num">{s.trades}</td>'
            f'<td class="num">{s.wr:.1f}%</td>'
            f'<td class="num">{s.sum_r:+.2f}</td><td class="num">{s.average_r:+.2f}</td>'
            f'<td class="num">{H.money(s.sum_pnl, signed=True)}</td></tr>'
            for v, s in stats.by_field(j, trades, key))
        slices += (f'<div class="card"><h2>{heading}</h2><table><thead><tr>'
                   f'<th></th><th class="num">trades</th><th class="num">WR</th>'
                   f'<th class="num">Σ R</th><th class="num">average R</th>'
                   f'<th class="num">Σ {H.sign(j.currency())}</th></tr></thead><tbody>{rows}</tbody>'
                   f'</table>'
                   f'<p class="caption">WR is wins against wins + losses; '
                   f'break-even trades are not in it, their weight is in R. '
                   f'"trades" and average R count every closed trade.</p>'
                   f'</div>')

    body = (filter_form(j, q).replace('action="/"', 'action="/stats"')
            + charts
            + r_rings(j, trades) + streaks_card(j, trades) + slices)
    return page("Statistics", body, "stats")


# --- search ----------------------------------------------------------------

def _snippet(texts, needle, width=110):
    """The first place the word occurs, with a little of what surrounds it."""
    low = needle.lower()
    for text in texts:
        text = (text or "").replace("\n", " ")
        i = text.lower().find(low)
        if i < 0:
            continue
        start = max(0, i - width // 3)
        end = min(len(text), i + len(needle) + width * 2 // 3)
        return Safe(("…" if start else "") + esc(text[start:i])
                    + f"<mark>{esc(text[i:i + len(needle)])}</mark>"
                    + esc(text[i + len(needle):end]) + ("…" if end < len(text) else ""))
    return ""


def search_page(q):
    needle = (q.get("q") or [""])[0].strip()
    j = journal()
    form = (f'<form method="get" action="/search" class="filters">'
            f'<div style="flex:1"><label>a word or a phrase</label>'
            f'<input type="text" name="q" value="{esc(needle)}" style="width:100%" '
            f'autofocus placeholder="from an idea, a conclusion, a plan or a card">'
            f'</div><div><button class="btn primary">Find</button></div></form>')
    if not needle:
        body = (f'<div class="card"><h2>Search</h2>{form}<p class="caption">'
                f'Looks through the text of every trade, plan and card: the '
                f'ideas, the conclusions, the notes, the analysis, the reviews. '
                f'Case does not matter.</p></div>')
        return page("Search", body, "search")

    low = needle.lower()

    def hit(texts):
        return any(low in (x or "").lower() for x in texts)

    found = []
    for t in j.trades:
        texts = [t.id, t.pair, t.note, t.conclusions] + [b.text for b in t.idea]
        if hit(texts):
            found.append(("trade", f"/trade/{U(t.id)}",
                          f"{t.opened:%d.%m.%Y} · {t.pair} {t.direction} · {t.style}"
                          + (f" · {t.result}" if t.result else " · open"),
                          _snippet(texts[2:], needle)))
    for k in store.all_plans(ROOT, []):
        texts = [k.id, k.title, k.pair, k.plan, k.updates, k.review] \
            + [b.text for b in k.analysis]
        if hit(texts):
            found.append(("plan", f"/plan/{U(k.id)}", plan_label(k),
                          _snippet(texts[3:] + texts[1:2], needle)))
    for c in store.all_cards(ROOT, []):
        texts = [getattr(c, name) for name, _, _ in CARD_SECTIONS] \
            + [row.trade for row in c.assessment]
        if hit(texts):
            found.append(("card", f"/card/{U(c.id)}",
                          f"{c.day:%d.%m.%Y}" + (f" · grade {c.grade}" if c.grade else ""),
                          _snippet(texts, needle)))
    for c in store.all_weeks(ROOT, []):
        texts = [getattr(c, name) for name, _, _ in WEEK_SECTIONS] \
            + [row.trade for row in c.assessment]
        if hit(texts):
            found.append(("week", f"/week/{U(c.id)}",
                          f"week {c.number}, {week_dates(c)}"
                          + (f" - grade {c.grade}" if c.grade else ""),
                          _snippet(texts, needle)))
    rows = "".join(
        f'<tr><td class="muted">{kind}</td>'
        f'<td><a href="{href}">{esc(label)}</a></td>'
        f'<td class="caption">{snippet}</td></tr>'
        for kind, href, label, snippet in found)
    n = len(found)
    body = (f'<div class="card"><h2>Search</h2>{form}</div>'
            f'<div class="card"><h2>{n} {"record" if n == 1 else "records"} '
            f'with "{esc(needle)}"</h2>'
            + (f'<table><tbody>{rows}</tbody></table>' if found else
               '<p class="muted">Nothing carries that word.</p>')
            + '</div>')
    return page("Search", body, "search")


# --- forms -----------------------------------------------------------------

_FILE_NAME = re.compile(r"^[a-z0-9_-]+\.(png|jpg|jpeg|gif|webp)$")
_TOKEN = re.compile(r"^[0-9a-f]{16}$")

FORM_SCRIPT = """
// the token is set by a script further down the page, so read it when sending
const token = () => document.body.dataset.token || '';
// A screenshot is held in the form by its own hidden field: remove the node and
// the field never reaches the server, so the picture leaves the trade. No
// separate "delete" call is needed: the shots folder is rewritten whole from
// whatever the form sent.
function refresh_zone(zone){
  const hint = zone.querySelector('.hint');
  if (!hint) return;
  if (hint.dataset.empty === undefined) hint.dataset.empty = hint.textContent;
  const n = zone.querySelectorAll('.shot').length;
  hint.textContent = n ? n + (n === 1 ? ' screenshot' : ' screenshots') +
                         ' · Ctrl+V to add another' : hint.dataset.empty;
}
function make_shot(url, field, value){
  const s = document.createElement('span');
  s.className = 'shot';
  s.innerHTML = '<img alt="screenshot"><button type="button" class="remove" ' +
    'title="remove screenshot">&times;</button><input type="hidden">';
  s.querySelector('img').src = url;
  const input = s.querySelector('input');
  input.name = field;
  input.value = value;
  return s;
}
function init_zones(){
  document.querySelectorAll('.dropzone').forEach(zone => {
    if (zone.dataset.ready) return;
    zone.dataset.ready = '1';
    zone.tabIndex = 0;
    refresh_zone(zone);
    zone.addEventListener('click', e => {
      const button = e.target.closest('.remove');
      if (!button) return;
      button.closest('.shot').remove();
      refresh_zone(zone);
    });
    zone.addEventListener('paste', async e => {
      for (const item of e.clipboardData.items) {
        if (!item.type.startsWith('image/')) continue;
        const blob = item.getAsFile();
        const answer = await fetch('/draft/upload?token=' + token() +
                                   '&zone=' + encodeURIComponent(zone.dataset.zone),
                                   {method:'POST', body: blob,
                                    headers:{'Content-Type': blob.type}});
        if (!answer.ok) { alert('Screenshot was not saved'); return; }
        const data = await answer.json();
        zone.appendChild(make_shot(data.url, 'file_' + zone.dataset.zone, data.file));
        refresh_zone(zone);
      }
    });
  });
}
function add_block(){
  const template = document.getElementById('block-template');
  const n = document.querySelectorAll('.form-block').length + 1;
  const div = document.createElement('div');
  div.className = 'form-block card';
  div.innerHTML = template.innerHTML.replaceAll('__N__', n);
  document.getElementById('blocks').appendChild(div);
  document.querySelector('[name=blocks]').value = n;
  init_zones();
}
document.addEventListener('DOMContentLoaded', () => { init_zones(); });
"""


def select(name, values, current="", empty=None, labels=None, style="",
           required=False):
    """A menu. `labels` gives a value a name of its own, as a plan id needs.

    A menu with no empty option arrives with its first value picked whether the
    person looked at it or not, so a field that has no sensible default asks
    for `empty` and `required` together."""
    options = f'<option value="">{esc(empty)}</option>' if empty else ""
    options += "".join(
        f'<option value="{esc(v)}"{" selected" if v == current else ""}>'
        f'{esc((labels or {}).get(v, v))}</option>' for v in values)
    where = f' style="{style}"' if style else ""
    must = " required" if required else ""
    return f'<select name="{name}"{where}{must}>{options}</select>'


def shot_in_zone(base, path, field):
    """A thumbnail of an already saved screenshot, with a cross.

    `base` is where the pictures of this record are served from, `/shot/<id>`
    for a trade and `/plan-shot/<id>` for a plan. The cross simply removes the
    node from the form, and together with the hidden field that is what keeps
    the screenshot in the record."""
    return (f'<span class="shot">'
            f'<img src="{base}/{U(os.path.basename(path))}" alt="screenshot">'
            f'<button type="button" class="remove" title="remove screenshot">'
            f'&times;</button>'
            f'<input type="hidden" name="{field}" value="{esc(path)}"></span>')


def shots_base(trade_id):
    return f"/shot/{U(trade_id)}"


def plan_shots_base(plan_id):
    return f"/plan-shot/{U(plan_id)}"


def dropzone(name, hint, shots=()):
    return (f'<div class="dropzone" data-zone="{esc(name)}">{"".join(shots)}'
            f'<div class="hint">{esc(hint)}</div></div>')


def idea_form_block(n, tf="", text="", existing=(), base=None):
    return ('<div class="form-block card">'
            + block_inside(n, tf, text, existing, base) + "</div>")


def block_inside(n, tf="", text="", existing=(), base=None):
    old = [shot_in_zone(base, s, f"have_idea-{n}") for s in existing]
    return f"""<div class="fields"><div class="field"><label>timeframe</label>
<input type="text" name="idea_tf_{n}" value="{esc(tf)}" placeholder="H4" size="8"></div></div>
<label style="margin-top:8px">idea text</label>
<textarea name="idea_text_{n}">{esc(text)}</textarea>
{dropzone(f"idea-{n}", "click here and press Ctrl+V to paste a screenshot", old)}"""


def trade_form(t=None, token=""):
    """One form for opening and for editing: the fields are the same."""
    j = journal()
    editing = t is not None
    accounts = [a for a in sorted(j.accounts) if not j.accounts[a].archived or
                (editing and t.account == a)]
    pairs = sorted(set(store.all_pairs(ROOT)) |
                   {x.pair for x in j.trades if x.pair != PAIR_NOT_SET})
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    entry = (t.opened.strftime("%Y-%m-%dT%H:%M") if editing else now)
    chosen = t.execution if editing else []
    checkboxes = "".join(
        f'<label class="caption" style="display:inline-block;margin-right:10px">'
        f'<input type="checkbox" name="execution" value="{esc(v)}"'
        f'{" checked" if v in chosen else ""}> {esc(v)}</label>'
        for v in offered("execution", *chosen))
    # A list of pairs drawn by the browser cannot carry the flags, and it does
    # not close on a second click on the field. This one is ours: the same
    # coins as everywhere else, and it opens and shuts on the field.
    pair_options = "".join(
        f'<button type="button" class="option" data-value="{esc(p)}">'
        f'{H.pair(p)}</button>' for p in pairs)

    # the plans are offered newest first: a trade is nearly always taken under
    # the plan just written, and an old one is still there to be picked
    plans = store.all_plans(ROOT)
    if editing and t.plan and t.plan not in {k.id for k in plans}:
        plans = plans + [Plan(id=t.plan, day=t.opened)]
    plan_ids = [k.id for k in plans]
    plan_names = {k.id: plan_label(k) for k in plans}

    if editing and t.idea:
        blocks = ""
        for i, b in enumerate(t.idea, 1):
            blocks += idea_form_block(i, b.tf, b.text, b.images, shots_base(t.id))
        count = len(t.idea)
    else:
        blocks = idea_form_block(1)
        count = 1

    action = f"/edit/{U(t.id)}" if editing else "/new"
    title = "Edit trade" if editing else "New trade"
    # The same position taken on two accounts is entered once. The copy repeats
    # the idea and the screenshots and differs only in the account and the risk,
    # which is the only thing that differs in real life too.
    duplicate = "" if editing else f"""
<details class="fold" style="margin-top:14px">
<summary>Duplicate on another account
<span class="caption">same idea and screenshots, its own risk</span></summary>
<div class="fields">
<div class="field"><label>account</label>
{select("dup_account", accounts, "", empty="-")}</div>
<div class="field"><label>risk, %</label>
<input type="number" name="dup_risk" step="0.05" min="0.05" style="width:90px"
 value="1"></div>
</div>
<p class="caption" style="margin:8px 0 0">Pick an account and the journal writes
two trades: this one, and a copy on that account with the risk set here.</p>
</details>"""
    # For a closed trade the exit and the conclusions are edited here too,
    # or editing the idea would wipe their screenshots: the shots folder is
    # rewritten from whatever the form sent.
    closing = ""
    if editing and not t.is_open:
        closing = f"""<input type="hidden" name="closed" value="1">
<div class="card"><h2>Outcome</h2>
{outcome_fields(t)}</div>
<div class="card"><h2>Exit moment</h2>
{dropzone("exit", "click here and press Ctrl+V",
          [shot_in_zone(shots_base(t.id), s, "have_exit") for s in t.exit_images])}</div>
<div class="card"><h2>Conclusions</h2>
<textarea name="conclusions">{esc(conclusions_text(t.conclusions))}</textarea>
{dropzone("concl", "screenshots for conclusions, Ctrl+V here",
          [shot_in_zone(shots_base(t.id), s, "have_concl")
           for s in conclusion_images(t.conclusions)])}</div>"""
    return f"""<form method="post" action="{action}">
<input type="hidden" name="token" value="{esc(token)}">
<input type="hidden" name="blocks" value="{count}">
<div class="card"><h2>{title}</h2>
<div class="fields">
<div class="field"><label>account</label>
{select("account", accounts, t.account if editing else "")}</div>
<div class="field"><label>pair</label>
<div class="picker">
<input type="text" name="pair" value="{esc(t.pair if editing else "")}"
 placeholder="EURUSD" autocomplete="off" required>
<div class="options" hidden>{pair_options}</div></div></div>
<div class="field"><label>direction</label>
{select("direction", DIRECTIONS, t.direction if editing else "")}</div>
<div class="field"><label>style</label>
{select("style", offered("styles", t.style if editing else ""),
        t.style if editing else "")}</div>
<div class="field"><label>entry TF</label>
{select("entry_tf", offered("timeframes", t.entry_tf if editing else ""),
        t.entry_tf if editing else "", empty="-")}</div>
<div class="field"><label>risk, %</label>
<input type="number" name="risk" step="0.05" min="0.05" style="width:90px"
 value="{t.risk if editing else 1}"></div>
<div class="field"><label>entry</label>
<input type="datetime-local" name="entry" value="{entry}"
 onclick="this.showPicker && this.showPicker()"></div>
<div class="field"><label>plan</label>
{select("plan", plan_ids, t.plan if editing else "", empty="-",
        labels=plan_names, style="max-width:270px")}</div>
</div>
<p class="caption" style="margin:8px 0 0">execution: {checkboxes}</p>
{duplicate}
</div>
<div id="blocks">{blocks}</div>
<template id="block-template">{block_inside("__N__")}</template>
<p><button type="button" class="btn" onclick="add_block()">+ idea block</button></p>
{closing}
<div class="actions"><button class="btn primary">{"Save" if editing else "Open trade"}</button>
<a class="btn" href="{f"/trade/{U(t.id)}" if editing else "/"}">Cancel</a></div>
</form>
<script>{FORM_SCRIPT}</script>
<script>document.body.dataset.token = {json.dumps(token)};
init_zones();</script>"""


def outcome_fields(t):
    """What a trade ended with: asked when it is closed and editable afterwards,
    because a result picked by accident stays wrong otherwise.

    The exit carries the hour, and the balance of a trade opened later the same
    day counts the money this close returned. An exit left at midnight is an
    exit whose hour is not known, the same convention the entry follows."""
    exit_at = (t.closed or datetime.now()).strftime("%Y-%m-%dT%H:%M")
    return f"""<div class="fields">
<div class="field"><label>result</label>
{select("result", RESULTS, t.result or "", empty="pick one", required=True)}</div>
<div class="field"><label>PnL, {H.sign(journal().currency(t.account))}</label>
<input type="number" name="pnl" step="0.01" style="width:130px"
 value="{t.pnl if t.pnl is not None else ""}" required></div>
<div class="field"><label>exit</label>
<input type="datetime-local" name="exit" value="{exit_at}"
 onclick="this.showPicker && this.showPicker()"></div>
</div>"""


def close_form(t, token):
    exit_shots = [shot_in_zone(shots_base(t.id), s, "have_exit")
                  for s in t.exit_images]
    concl_shots = [shot_in_zone(shots_base(t.id), s, "have_concl")
                   for s in conclusion_images(t.conclusions)]
    return f"""<form method="post" action="/close/{U(t.id)}">
<input type="hidden" name="token" value="{esc(token)}">
<div class="card"><h2>Close trade {esc(t.id)}</h2>
{outcome_fields(t)}
<p class="caption">Risk was {t.risk:g}% = {amount(journal(), journal().computed[t.id].risk_money, t.account)}.
R is calculated automatically.</p></div>
<div class="card"><h2>Exit moment</h2>
{dropzone("exit", "click here and press Ctrl+V", exit_shots)}</div>
<div class="card"><h2>Conclusions</h2>
<textarea name="conclusions">{esc(conclusions_text(t.conclusions))}</textarea>
{dropzone("concl", "screenshots for conclusions, Ctrl+V here", concl_shots)}</div>
<div class="actions"><button class="btn primary">Close trade</button>
<a class="btn" href="/trade/{U(t.id)}">Cancel</a></div>
</form>
<script>{FORM_SCRIPT}</script>
<script>document.body.dataset.token = {json.dumps(token)};init_zones();</script>"""


# --- screenshot drafts -----------------------------------------------------

SIGNATURES = [(b"\x89PNG", ".png"), (b"\xff\xd8\xff", ".jpg"),
              (b"GIF8", ".gif"), (b"RIFF", ".webp")]
SHOT_LIMIT = 32 * 1024 * 1024   # a chart screenshot is a few megabytes


def draft_dir(token):
    if not _TOKEN.match(token or ""):
        raise ValueError("bad token")
    return os.path.join(DRAFTS, token)


def save_draft(token, zone, data):
    if len(data) > SHOT_LIMIT:
        raise ValueError("image is too big")
    ext = next((e for sig, e in SIGNATURES if data.startswith(sig)), None)
    if ext is None:
        raise ValueError("not an image")
    zone = re.sub(r"[^a-z0-9-]", "", zone)
    folder = draft_dir(token)
    os.makedirs(folder, exist_ok=True)
    n = len([i for i in os.listdir(folder) if i.startswith(zone + "-")]) + 1
    name = f"{zone}-{n:02d}{ext}"
    with open(os.path.join(folder, name), "wb") as f:
        f.write(data)
    return name


def zone_sources(data, zone, folder, token):
    """Image paths for a zone: the old ones kept plus the new ones pasted.

    `folder` is the record's own directory, a trade's or a plan's."""
    removed = set(data.get("remove", []))
    paths = []
    inside = os.path.normpath(folder) + os.sep
    for s in data.get("have_" + zone, []):
        if s in removed:
            continue
        # a kept picture is named by the form, and the form is a request: a
        # path that leads out of the record's own folder is not a picture
        full = os.path.normpath(os.path.join(folder, s))
        if full.startswith(inside):
            paths.append(full)
    for name in data.get("file_" + zone, []):
        if _FILE_NAME.match(name):
            paths.append(os.path.join(draft_dir(token), name))
    return [p for p in paths if os.path.exists(p)]


# what a zone of a form is called on the disk
ZONE_PREFIX = {"exit": "exit", "concl": "conclusions", "review": "review",
               "plan": "plan", "update": "update"}


def apply_shots(record, zones):
    """Rewrites the shots folder whole, so no leftovers from editing stay behind.

    `record` is the folder of the trade or of the plan; the pictures live in
    its `shots` subfolder."""
    folder = os.path.join(record, store.SHOTS)
    fresh = folder + ".new"
    shutil.rmtree(fresh, ignore_errors=True)
    os.makedirs(fresh, exist_ok=True)
    result = {}
    for zone, sources in zones.items():
        prefix = (ZONE_PREFIX.get(zone)
                  or f"idea-{int(zone.split('-')[1]):02d}")
        names = []
        for i, src in enumerate(sources, 1):
            name = f"{prefix}-{i:02d}{os.path.splitext(src)[1] or '.png'}"
            shutil.copyfile(src, os.path.join(fresh, name))
            names.append(os.path.join(store.SHOTS, name))
        result[zone] = names
    shutil.rmtree(folder, ignore_errors=True)
    os.replace(fresh, folder)
    return result


def add_shots(record, prefix, sources):
    """Adds pictures to the shots folder without touching what is already there.

    `apply_shots` rewrites the folder whole from a form that shows every zone.
    An update is added from the plan page, where no such form stands, so its
    screenshots are appended under the first free numbers instead."""
    folder = os.path.join(record, store.SHOTS)
    os.makedirs(folder, exist_ok=True)
    taken = set(os.listdir(folder))
    names, n = [], 1
    for src in sources:
        ext = os.path.splitext(src)[1] or ".png"
        while f"{prefix}-{n:02d}{ext}" in taken:
            n += 1
        name = f"{prefix}-{n:02d}{ext}"
        shutil.copyfile(src, os.path.join(folder, name))
        taken.add(name)
        names.append(os.path.join(store.SHOTS, name))
    return names


def place_shots(text, images):
    """The new file names put back where the old ones stood, the rest at the end.

    The pictures of a text keep their place in it, and a picture just pasted
    has no place yet, so it goes after the last line."""
    queue = list(images)
    kept = _IMAGE_IN_TEXT.sub(
        lambda m: f"![]({queue.pop(0)})" if queue else "", text).strip()
    return "\n\n".join([kept] + [f"![]({s})" for s in queue]).strip()


def drop_draft(token):
    shutil.rmtree(draft_dir(token), ignore_errors=True)


DRAFT_LIFETIME = 24 * 3600


def sweep_drafts(lifetime=DRAFT_LIFETIME):
    """An abandoned form keeps its pasted screenshots forever, so sweep them.

    Called when a new form is handed out: the drafts folder is small, and
    walking it on every form is cheaper than a timer of its own."""
    now = time.time()
    for name in os.listdir(DRAFTS) if os.path.isdir(DRAFTS) else []:
        path = os.path.join(DRAFTS, name)
        try:
            if os.path.isdir(path) and now - os.path.getmtime(path) > lifetime:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


def new_token():
    sweep_drafts()
    return os.urandom(8).hex()


# --- handling the forms ----------------------------------------------------

def one(data, key, default=""):
    return (data.get(key) or [default])[0].strip()


def apply_fields(t, data):
    entry = datetime.strptime(one(data, "entry"), "%Y-%m-%dT%H:%M")
    t.account = one(data, "account")
    # EURUSD and eurusd are one pair, so the filters and the tables see one
    t.pair = one(data, "pair").upper() or PAIR_NOT_SET
    t.direction = one(data, "direction")
    t.style = one(data, "style")
    t.entry_tf = one(data, "entry_tf")
    t.execution = data.get("execution", [])
    t.plan = one(data, "plan")
    t.risk = float(one(data, "risk", "1").replace(",", "."))
    t.opened = entry
    t.opened_time = bool(entry.hour or entry.minute) or t.opened_time
    return t


def blocks_from_form(data):
    blocks = []
    for n in range(1, int(one(data, "blocks", "1")) + 1):
        text = one(data, f"idea_text_{n}")
        tf = one(data, f"idea_tf_{n}")
        blocks.append((n, IdeaBlock(tf=tf, text=text)))
    return blocks


def build_trade(data, token, account="", risk=None):
    """Writes one trade from the new trade form.

    The duplicate is written through here as well, with an account and a risk
    of its own; everything else it reads from the same form."""
    entry = datetime.strptime(one(data, "entry"), "%Y-%m-%dT%H:%M")
    pair = one(data, "pair").upper() or PAIR_NOT_SET
    t = Trade(id=store.new_id(ROOT, entry, pair), account="")
    apply_fields(t, data)
    if account:
        t.account = account
    if risk is not None:
        t.risk = risk
    zones, t.idea = {}, []
    for n, block in blocks_from_form(data):
        paths = [os.path.join(draft_dir(token), name)
                 for name in data.get(f"file_idea-{n}", []) if _FILE_NAME.match(name)]
        if not (block.text.strip() or paths):
            continue
        zones[f"idea-{len(t.idea)+1}"] = [p for p in paths if os.path.exists(p)]
        t.idea.append(block)
    t.check()
    names = apply_shots(store.trade_dir(ROOT, t.id), zones)
    for i, block in enumerate(t.idea, 1):
        block.images = names.get(f"idea-{i}", [])
    store.save_trade(ROOT, t)
    return t


def create_trade(data):
    """One trade, or two when an account for a duplicate was picked.

    The copy is written before the drafts are swept, so both trades get the
    screenshots that were pasted into the form."""
    token = one(data, "token")
    twin = one(data, "dup_account")
    if twin and twin == one(data, "account"):
        raise RecordError("the duplicate needs an account of its own")
    t = build_trade(data, token)
    if twin:
        risk = one(data, "dup_risk")
        build_trade(data, token, account=twin,
                    risk=float(risk.replace(",", ".")) if risk else t.risk)
    drop_draft(token)
    drop_cache()
    return t


def edit_trade(t, data):
    token = one(data, "token")
    apply_fields(t, data)
    # the folder is named after the day and the pair, so it follows them
    if not store.id_fits(t):
        try:
            store.rename_trade(ROOT, t, store.new_id(ROOT, t.opened, t.pair,
                                                     keep=t.id))
        except OSError as e:
            raise RecordError(str(e))
    folder = store.trade_dir(ROOT, t.id)
    zones, kept = {}, []
    for n, block in blocks_from_form(data):
        paths = zone_sources(data, f"idea-{n}", folder, token)
        if not (block.text.strip() or paths):
            continue
        zones[f"idea-{len(kept)+1}"] = paths
        kept.append(block)
    # The exit and the conclusions only come from the form of a closed trade.
    # If they were not in the form, keep them as they are: empty zones would
    # wipe the screenshots off the disk.
    editing_close = one(data, "closed") == "1"
    if editing_close:
        apply_outcome(t, data)
        zones["exit"] = zone_sources(data, "exit", folder, token)
        zones["concl"] = zone_sources(data, "concl", folder, token)
    else:
        own = os.path.join(folder, "{}")
        zones["exit"] = [own.format(s) for s in t.exit_images]
        zones["concl"] = [own.format(s)
                          for s in conclusion_images(t.conclusions)]
    t.idea = kept
    t.check()
    names = apply_shots(folder, zones)
    for i, block in enumerate(t.idea, 1):
        block.images = names.get(f"idea-{i}", [])
    t.exit_images = names.get("exit", [])
    t.conclusions = (build_conclusions(one(data, "conclusions"),
                                       names.get("concl", []))
                     if editing_close
                     else rewrite_conclusions(t.conclusions, names.get("concl", [])))
    store.save_trade(ROOT, t)
    drop_draft(token)
    drop_cache()
    return t


_IMAGE_IN_TEXT = re.compile(r"!\[\]\(([^)]+)\)")


def conclusion_images(text):
    return _IMAGE_IN_TEXT.findall(text or "")


def conclusions_text(text):
    """The conclusions for the input field: the zone below owns the images."""
    without = _IMAGE_IN_TEXT.sub("", text or "")
    return re.sub(r"\n{3,}", "\n\n", without).strip()


def build_conclusions(text, images):
    return "\n\n".join([text.strip()] + [f"![]({s})" for s in images]).strip()


def rewrite_conclusions(text, images):
    """Swaps the image paths inside the conclusions for the new file names."""
    queue = list(images)
    return _IMAGE_IN_TEXT.sub(
        lambda m: f"![]({queue.pop(0)})" if queue else "", text).strip()


def apply_outcome(t, data):
    """The three fields of `outcome_fields`, read back the same way by the
    closing form and by the form of a closed trade."""
    result = one(data, "result")
    if result not in RESULTS:
        raise RecordError("pick how the trade ended: " + ", ".join(RESULTS))
    t.result = result
    t.pnl = float(one(data, "pnl", "0").replace(",", "."))
    closed, _ = store._date(one(data, "exit"))
    if closed is None:
        raise RecordError("the exit date is missing")
    t.closed = closed
    t.closed_time = bool(closed.hour or closed.minute)
    return t


def close_trade(t, data):
    token = one(data, "token")
    apply_outcome(t, data)
    conclusions = one(data, "conclusions")
    folder = store.trade_dir(ROOT, t.id)
    zones = {f"idea-{i}": [os.path.join(folder, s) for s in b.images]
             for i, b in enumerate(t.idea, 1)}
    zones["exit"] = zone_sources(data, "exit", folder, token)
    zones["concl"] = zone_sources(data, "concl", folder, token)
    t.check()
    names = apply_shots(folder, zones)
    for i, block in enumerate(t.idea, 1):
        block.images = names.get(f"idea-{i}", [])
    t.exit_images = names.get("exit", [])
    t.conclusions = build_conclusions(conclusions, names.get("concl", []))
    store.save_trade(ROOT, t)
    drop_draft(token)
    drop_cache()
    return t


# --- trading plans ---------------------------------------------------------
# A plan is written before the market opens and answers what a trade cannot:
# what was supposed to happen. It holds the analysis by timeframe, what will be
# done and what will not, the notes added while it runs and the review after. A
# trade points at the plan it followed, so the plan can be asked the only
# question that matters about a plan: what came out of it.


def plan_label(k):
    """A plan in one line, for a list and for the menu of the trade form."""
    span = f"{k.day:%d.%m.%Y}"
    if k.until and k.until != k.day:
        span += f" to {k.until:%d.%m.%Y}"
    bits = [span, "" if k.pair == PAIR_NOT_SET else k.pair, k.title, k.narrative]
    return " · ".join(b for b in bits if b)


_BOLD = re.compile(r"\*\*(.+?)\*\*")


def inline(text):
    """Plain text with line breaks, and **bold** left readable.

    The updates of a plan are written as `**date**: what happened`, which reads
    as a list in the file and has to read as one on the page too."""
    return _BOLD.sub(r"<strong>\1</strong>", esc(text)).replace("\n", "<br>")


def with_shots(text, base):
    """Text of a record with its screenshots drawn where they stand in it.

    A picture is kept in the text as `![](shots/name.png)`, so a screenshot
    pasted into an update stays under the line it belongs to."""
    return _IMAGE_IN_TEXT.sub(
        lambda m: f'<img src="{base}/{U(os.path.basename(m.group(1)))}" '
                  f'alt="screenshot">', inline(text))


def plan_title(plan_id):
    """The name of a plan for a link. A plan deleted later leaves its id."""
    try:
        return plan_label(store.load_plan(ROOT, plan_id))
    except (OSError, ValueError):
        return plan_id


def plan_trades(j, plan_id):
    return [t for t in j.trades if t.plan == plan_id]


def plan_result(j, trades):
    """What the plan came to, in one line."""
    if not trades:
        return "no trades yet"
    s = stats.summary(j, trades)
    open_now = sum(1 for t in trades if t.is_open)
    bits = [f"{len(trades)} trades" if len(trades) != 1 else "1 trade"]
    if open_now:
        bits.append(f"{open_now} open")
    if s.trades:
        bits += ([f"WR {s.wr:.0f}%"] if s.decided else []) + \
                [f"{s.sum_r:+.2f} R", amount(j, s.sum_pnl, signed=True)]
    return " · ".join(bits)


def plan_followed(j, k, trades):
    """Did the trades go the way the plan said? One line, or nothing when the
    plan expected nothing in particular.

    A bullish plan is followed by a long and gone against by a short; a plan
    that said "no trade" is gone against by every trade taken under it."""
    side = {"bullish": "long", "bearish": "short"}.get(k.narrative)
    if not trades or not (side or k.narrative == "no trade"):
        return ""

    def told(xs):
        if not xs:
            return "none"
        s = stats.summary(j, xs)
        words = f"{len(xs)} trade" if len(xs) == 1 else f"{len(xs)} trades"
        return words + (f" at {s.sum_r:+.2f} R" if s.trades else "")

    if k.narrative == "no trade":
        return f"the plan was not to trade; taken anyway: {told(trades)}"
    with_it = [t for t in trades if t.direction == side]
    against = [t for t in trades if t.direction != side]
    return f"with the narrative: {told(with_it)} · against it: {told(against)}"


def plans_page():
    j = journal()
    problems = []
    plans = store.all_plans(ROOT, problems)
    right = '<a class="btn primary" href="/plan/new">+ Plan</a>'
    if not plans:
        body = ('<div class="card"><h2>Trading plans</h2>'
                '<p class="muted">No plans yet. The button above writes the '
                'first one: the analysis, and what you will do with it.</p></div>')
        return page("Plans", body, "plans", right, problems)
    today = datetime.now()
    rows = ""
    for k in plans:
        trades = plan_trades(j, k.id)
        s = stats.summary(j, trades)
        href = f"/plan/{U(k.id)}"
        span = f"{k.day:%d.%m.%Y}"
        if k.until and k.until != k.day:
            span += f" - {k.until:%d.%m.%Y}"
        cells = [(esc(span), ""), (H.pair(k.pair), ""),
                 (esc(k.narrative) or "-", ""),
                 (esc(k.title) or "-", ""),
                 ("current" if k.covers(today) else "", "muted"),
                 (str(len(trades)), "num"),
                 ("-" if not s.trades else f"{s.sum_r:+.2f}",
                  f"num {sum_class(s.sum_r)}")]
        rows += ("<tr>" + "".join(link_cell(href, inner, cls)
                                  for inner, cls in cells) + "</tr>")
    body = (f'<div class="card"><h2>Trading plans</h2>'
            f'<table><thead><tr><th>dates</th><th>pair</th><th>narrative</th>'
            f'<th>title</th><th></th><th class="num">trades</th>'
            f'<th class="num">Σ R</th></tr></thead><tbody>{rows}</tbody></table>'
            f'<p class="caption">A plan is written before the market opens; a '
            f'trade is tied to it in its own form. Σ R counts the trades tied '
            f'to the plan, which is the only honest answer to whether the plan '
            f'was any good.</p></div>')
    return page("Plans", body, "plans", right, problems)


def plan_page(plan_id):
    if not store.safe_dir_name(plan_id):
        return None
    try:
        k = store.load_plan(ROOT, plan_id)
    except (OSError, RecordError):
        return None
    j = journal()
    base = plan_shots_base(k.id)
    trades = plan_trades(j, k.id)
    fields = [("from", f"{k.day:%d.%m.%Y}"),
              ("until", f"{k.until:%d.%m.%Y}" if k.until and k.until != k.day
               else "the same day"),
              ("pair", H.pair(k.pair)),
              ("narrative", k.narrative or "-"),
              ("trades", plan_result(j, trades))]
    followed = plan_followed(j, k, trades)
    if followed:
        fields.append(("plan against fact", followed))
    table = "".join(f'<tr><td class="muted">{esc(name)}</td><td>{esc(value)}</td></tr>'
                    for name, value in fields)

    analysis = ""
    for block in k.analysis:
        images = "".join(f'<img src="{base}/{U(os.path.basename(src))}" '
                         f'alt="analysis screenshot">' for src in block.images)
        analysis += (f'<div class="idea-block">'
                     f'{f"<h3>{esc(block.tf)}</h3>" if block.tf else ""}'
                     f'<div>{esc(block.text).replace(chr(10), "<br>")}</div>'
                     f'<div class="shots">{images}</div></div>')
    review = with_shots(k.review, base)
    updates = (f'<div class="shots">{with_shots(k.updates, base)}</div>'
               if k.updates.strip() else
               '<p class="muted">Nothing has happened to the plan yet.</p>')
    token = new_token()
    update_form = (f'<form method="post" action="/plan/{U(k.id)}/update" '
                   f'style="margin-top:12px">'
                   f'<input type="hidden" name="token" value="{esc(token)}">'
                   f'<label>add an update</label>'
                   f'<input type="text" name="update" style="width:100%"'
                   f' placeholder="what changed since the plan was written" required>'
                   f'{dropzone("update", "click here and press Ctrl+V to paste a screenshot")}'
                   f'<div class="actions"><button class="btn">Add</button></div>'
                   f'</form>')

    rows = "".join(trade_row(j, t) for t in
                   sorted(trades, key=lambda t: t.opened, reverse=True))
    trades_card = (f'<div class="card"><h2>Trades of this plan</h2>'
                   f'<table><thead><tr><th>date</th><th>account</th><th>pair</th>'
                   f'<th>direction</th><th>style</th><th>TF</th>'
                   f'<th class="num">risk</th><th>result</th>'
                   f'<th class="num">PnL {H.sign(j.currency())}</th><th class="num">R</th></tr></thead>'
                   f'<tbody>{rows}</tbody></table>'
                   f'<p class="caption">{esc(plan_result(j, trades))}</p></div>'
                   if trades else
                   '<div class="card"><h2>Trades of this plan</h2>'
                   '<p class="muted">Nothing has been tied to this plan yet. '
                   'The plan is picked in the form of a trade.</p></div>')

    buttons = (f'<a class="btn" href="/plan/{U(k.id)}/edit">Edit</a>'
               f'<form method="post" action="/plan/{U(k.id)}/delete" '
               f'style="display:inline" onsubmit="return confirm('
               f'\'Delete plan {esc(k.id)}? The folder moves to .trash.\')">'
               f'<button class="btn danger">Delete</button></form>')
    body = (f'<div class="card{" is-open" if k.covers(datetime.now()) else ""}">'
            f'<h2>{esc(k.title or plan_label(k))}</h2>'
            f'<table class="props">{table}</table></div>'
            + (f'<div class="card"><h2>Analysis</h2>{analysis}</div>'
               if analysis else "")
            + (f'<div class="card"><h2>Plan</h2>'
               f'<div class="shots">{with_shots(k.plan, base)}</div></div>'
               if k.plan.strip() else "")
            + f'<div class="card"><h2>Updates</h2>{updates}{update_form}</div>'
            + (f'<div class="card"><h2>Review</h2>'
               f'<div class="shots">{review}</div></div>'
               if k.review.strip() else "")
            + trades_card
            + f'<script>{FORM_SCRIPT}</script>'
            + f'<script>document.body.dataset.token = {json.dumps(token)};'
              f'init_zones();</script>')
    return page(k.title or k.id, body, "plans", buttons)


def plan_form(k=None, token=""):
    """One form for writing a plan and for editing it: the fields are the same."""
    editing = k is not None
    pairs = sorted(set(store.all_pairs(ROOT)) |
                   {x.pair for x in journal().trades if x.pair != PAIR_NOT_SET})
    pair_options = "".join(
        f'<button type="button" class="option" data-value="{esc(p)}">'
        f'{H.pair(p)}</button>' for p in pairs)
    today = datetime.now().strftime("%Y-%m-%d")
    base = plan_shots_base(k.id) if editing else None
    if editing and k.analysis:
        blocks = ""
        for i, b in enumerate(k.analysis, 1):
            blocks += idea_form_block(i, b.tf, b.text, b.images, base)
        count = len(k.analysis)
    else:
        blocks = idea_form_block(1)
        count = 1
    action = f"/plan/{U(k.id)}/edit" if editing else "/plan/new"
    review = ""
    if editing:
        review = f"""<div class="card"><h2>Updates</h2>
<textarea name="updates">{esc(k.updates)}</textarea>
{dropzone("update", "screenshots of the updates, Ctrl+V here",
          [shot_in_zone(base, src, "have_update")
           for src in conclusion_images(k.updates)])}
<p class="caption">Written as the plan runs; the plan page adds a dated line to
this without opening the form. A screenshot keeps the line it was pasted
under.</p></div>
<div class="card"><h2>Review</h2>
<textarea name="review">{esc(conclusions_text(k.review))}</textarea>
{dropzone("review", "screenshots for the review, Ctrl+V here",
          [shot_in_zone(base, src, "have_review")
           for src in conclusion_images(k.review)])}</div>"""
    return f"""<form method="post" action="{action}">
<input type="hidden" name="token" value="{esc(token)}">
<input type="hidden" name="blocks" value="{count}">
<div class="card"><h2>{"Edit plan" if editing else "New plan"}</h2>
<div class="fields">
<div class="field"><label>title</label>
<input type="text" name="title" value="{esc(k.title) if editing else ""}"
 placeholder="weekly" style="width:160px"></div>
<div class="field"><label>pair</label>
<div class="picker">
<input type="text" name="pair" value="{esc(k.pair) if editing and k.pair != PAIR_NOT_SET else ""}"
 placeholder="EURUSD" autocomplete="off">
<div class="options" hidden>{pair_options}</div></div></div>
<div class="field"><label>narrative</label>
{select("narrative", NARRATIVES, k.narrative if editing else "", empty="-")}</div>
<div class="field"><label>from</label>
<input type="date" name="from" required
 value="{f"{k.day:%Y-%m-%d}" if editing else today}"
 onclick="this.showPicker && this.showPicker()"></div>
<div class="field"><label>until</label>
<input type="date" name="until"
 value="{f"{k.until:%Y-%m-%d}" if editing and k.until and k.until != k.day else ""}"
 onclick="this.showPicker && this.showPicker()"></div>
</div>
<p class="caption">Until is left empty for a plan that lives one day.</p>
</div>
<div id="blocks">{blocks}</div>
<template id="block-template">{block_inside("__N__")}</template>
<p><button type="button" class="btn" onclick="add_block()">+ analysis block</button></p>
<div class="card"><h2>Plan</h2>
<textarea name="plan_text" placeholder="what you will do, and what you will not">{esc(conclusions_text(k.plan)) if editing else ""}</textarea>
{dropzone("plan", "screenshots of the positions, Ctrl+V here",
          [shot_in_zone(base, src, "have_plan")
           for src in conclusion_images(k.plan)] if editing else ())}
</div>
{review}
<div class="actions"><button class="btn primary">{"Save" if editing else "Write the plan"}</button>
<a class="btn" href="{f"/plan/{U(k.id)}" if editing else "/plans"}">Cancel</a></div>
</form>
<script>{FORM_SCRIPT}</script>
<script>document.body.dataset.token = {json.dumps(token)};
init_zones();</script>"""


def plan_fields(k, data):
    k.title = one(data, "title")
    k.pair = one(data, "pair").upper() or PAIR_NOT_SET
    k.narrative = one(data, "narrative")
    k.day = datetime.strptime(one(data, "from"), "%Y-%m-%d")
    until = one(data, "until")
    k.until = datetime.strptime(until, "%Y-%m-%d") if until else None
    k.plan = one(data, "plan_text")
    return k


def plan_blocks(data, folder, token, k=None):
    """The analysis blocks of the form: the kept pictures plus the pasted ones."""
    zones, kept = {}, []
    for n, block in blocks_from_form(data):
        if k is None:
            paths = [os.path.join(draft_dir(token), name)
                     for name in data.get(f"file_idea-{n}", [])
                     if _FILE_NAME.match(name)]
            paths = [p for p in paths if os.path.exists(p)]
        else:
            paths = zone_sources(data, f"idea-{n}", folder, token)
        if not (block.text.strip() or paths):
            continue
        zones[f"idea-{len(kept) + 1}"] = paths
        kept.append(block)
    return zones, kept


def create_plan(data):
    token = one(data, "token")
    day = datetime.strptime(one(data, "from"), "%Y-%m-%d")
    pair = one(data, "pair").upper() or PAIR_NOT_SET
    k = Plan(id=store.new_plan_id(ROOT, day, pair))
    plan_fields(k, data)
    folder = store.plan_dir(ROOT, k.id)
    zones, k.analysis = plan_blocks(data, folder, token)
    zones["plan"] = zone_sources(data, "plan", folder, token)
    k.check()
    names = apply_shots(folder, zones)
    for i, block in enumerate(k.analysis, 1):
        block.images = names.get(f"idea-{i}", [])
    k.plan = build_conclusions(one(data, "plan_text"), names.get("plan", []))
    store.save_plan(ROOT, k)
    drop_draft(token)
    return k


def edit_plan(k, data):
    token = one(data, "token")
    plan_fields(k, data)
    folder = store.plan_dir(ROOT, k.id)
    zones, k.analysis = plan_blocks(data, folder, token, k)
    zones["review"] = zone_sources(data, "review", folder, token)
    zones["plan"] = zone_sources(data, "plan", folder, token)
    # the updates are edited as they are written, images and all: the zone sends
    # back what the text still shows, and the names are put back in its places
    zones["update"] = zone_sources(data, "update", folder, token)
    k.updates = one(data, "updates")
    k.check()
    names = apply_shots(folder, zones)
    for i, block in enumerate(k.analysis, 1):
        block.images = names.get(f"idea-{i}", [])
    k.review = build_conclusions(one(data, "review"), names.get("review", []))
    k.plan = build_conclusions(one(data, "plan_text"), names.get("plan", []))
    k.updates = place_shots(one(data, "updates"), names.get("update", []))
    store.save_plan(ROOT, k)
    drop_draft(token)
    return k


def add_update(k, data):
    """A dated line at the end of the updates: the plan meets the week.

    The screenshots pasted with it are appended to the shots folder rather than
    rewritten into it: this form shows one zone, and a rewrite from a form that
    shows one zone would take every other picture of the plan with it."""
    text = one(data, "update")
    if not text:
        raise RecordError("an update without a word in it")
    token = one(data, "token")
    folder = store.plan_dir(ROOT, k.id)
    shots = add_shots(folder, "update",
                      zone_sources(data, "update", folder, token)) if token else []
    line = f"**{datetime.now():%d.%m.%Y}**: {text}"
    for name in shots:
        line += f"\n![]({name})"
    k.updates = (k.updates + "\n\n" + line) if k.updates.strip() else line
    store.save_plan(ROOT, k)
    if token:
        drop_draft(token)
    return k


# --- daily card ------------------------------------------------------------
# The paper Daily Report Card carried over as it is: the same fields in the same
# order. One file per day in journal/cards, next to the trades, under git.

GRADES = ["A", "B", "C", "D", "F"]
# how tall a section field is, as on paper: the focus needs a line, the review does not
SECTION_HEIGHT = {"focus": 46, "learned": 62, "errors": 62}


def day_from_url(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise RecordError(f"bad date {text!r}: expected YYYY-MM-DD")


def day_trades(j, day):
    """The trades the day closed: what a new card is offered."""
    return [t for t in j.trades if not t.is_open and t.closed
            and t.closed.date() == day.date()]


def day_pnl(j, day):
    """What the day gave by closed trades, offered in a new card."""
    return sum(t.pnl or 0.0 for t in day_trades(j, day))


def assessment_rows(k, closed):
    """The table of the paper: numbered lines of a trade and the mark it earned.

    A card written by hand may carry more than the paper's rows, so every row
    it has is drawn; a row left empty is dropped when the form comes back."""
    listed = list(k.assessment) + [Graded() for _ in range(ASSESSMENT_ROWS)]
    options = "".join(f'<option value="{esc(t.pair)} {esc(t.direction)}, '
                      f'{t.closed:%d.%m}">' for t in closed)
    body = "".join(
        f'<tr><td class="muted">{n}.</td>'
        f'<td><input type="text" name="assess_trade" list="assesstrades" '
        f'style="width:100%" value="{esc(row.trade)}"></td>'
        f'<td><input type="text" name="assess_grade" list="grades" '
        f'style="width:90px" value="{esc(row.grade)}"></td></tr>'
        for n, row in enumerate(listed[:max(ASSESSMENT_ROWS, len(k.assessment))], 1))
    return (f'<h3>trades assessment</h3>'
            f'<datalist id="assesstrades">{options}</datalist>'
            f'<table><thead><tr><th style="width:24px"></th><th>trade</th>'
            f'<th style="width:110px">grade</th></tr></thead>'
            f'<tbody>{body}</tbody></table>')


def read_assessment(data):
    """The rows of the assessment table, the empty ones left out."""
    grades = data.get("assess_grade", [])
    rows = []
    for n, text in enumerate(data.get("assess_trade", [])):
        grade = grades[n] if n < len(grades) else ""
        if text.strip() or grade.strip():
            rows.append(Graded(trade=text.strip(), grade=grade.strip()))
    return rows


def cards_page():
    """Both report cards, the days over the weeks: two tables on one tab.

    They are one kind of record kept in two rhythms, and they sit in one folder,
    so the tab that lists them shows them one under the other."""
    problems = []
    cards = store.all_cards(ROOT, problems)
    weeks = store.all_weeks(ROOT, problems)
    today = datetime.now().strftime("%Y-%m-%d")
    right = (f'<a class="btn primary" href="/card/{today}">+ DRC</a>'
             f'<a class="btn" href="/week/{stats.week(datetime.now())}">+ WRC</a>')
    sign = H.sign(journal().currency())
    if cards:
        rows = "".join(
            "<tr>" + "".join(link_cell(f"/card/{U(k.id)}", inner, cls) for inner, cls in
                             [(f"{k.day:%d.%m.%Y}", ""),
                              (esc(k.grade) or "-", ""),
                              (H.money(k.pnl, signed=True) if k.pnl is not None
                               else "-", f"num {sum_class(k.pnl or 0)}"),
                              (esc(k.quality) or "-", ""),
                              (esc(first_line(k.overview or k.focus)), "muted")])
            + "</tr>" for k in cards)
        daily = (f'<table><thead><tr><th>date</th><th>process</th>'
                 f'<th class="num">P&amp;L {sign}</th><th>opportunity</th>'
                 f'<th>overview</th></tr></thead><tbody>{rows}</tbody></table>')
    else:
        daily = ('<p class="muted">No daily cards yet. <b>+ DRC</b> opens '
                 'today&rsquo;s.</p>')
    if weeks:
        rows = "".join(
            "<tr>" + "".join(link_cell(f"/week/{U(k.id)}", inner, cls) for inner, cls in
                             [(f'{k.number}<span class="muted" '
                               f'style="margin-left:8px">{week_dates(k)}</span>', ""),
                              (esc(k.grade) or "-", ""),
                              (H.money(k.pnl, signed=True) if k.pnl is not None
                               else "-", f"num {sum_class(k.pnl or 0)}"),
                              ("-" if k.trades is None else str(k.trades), "num"),
                              (esc(k.quality) or "-", ""),
                              (esc(first_line(k.lesson or k.focus)), "muted")])
            + "</tr>" for k in weeks)
        weekly = (f'<table><thead><tr><th>week</th><th>process</th>'
                  f'<th class="num">P&amp;L {sign}</th><th class="num">trades</th>'
                  f'<th>opportunity</th><th>key lesson</th>'
                  f'</tr></thead><tbody>{rows}</tbody></table>')
    else:
        weekly = ('<p class="muted">No weekly cards yet. <b>+ WRC</b> opens '
                  'the week that is running.</p>')
    body = (f'<div class="card"><h2>Daily report cards</h2>{daily}</div>'
            f'<div class="card"><h2>Weekly report cards</h2>{weekly}</div>')
    return page("Cards", body, "cards", right, problems)


def first_line(text, limit=90):
    line = (text or "").strip().split("\n")[0]
    return line if len(line) <= limit else line[:limit - 1] + "…"


def card_page(day):
    j = journal()
    k = store.load_card(ROOT, day)
    closed = day_trades(j, day)
    is_new = k is None
    if is_new:
        k = Card(day=day, pnl=day_pnl(j, day) or None)
    options = "".join(f'<option value="{g}">' for g in GRADES)
    sections = "".join(
        f'<h3>{esc(label)}</h3>'
        f'<textarea name="{name}" style="min-height:'
        f'{SECTION_HEIGHT.get(name, 84)}px">{esc(getattr(k, name))}</textarea>'
        for name, _, label in CARD_SECTIONS)
    delete = "" if is_new else (
        f'<span class="right"><button class="btn danger" '
        f'formaction="/card/{U(k.id)}/delete" formnovalidate '
        f'onclick="return confirm(\'Delete the card for {k.day:%d.%m.%Y}? '
        f'It goes to .trash.\')">Delete</button></span>')
    body = f"""<form method="post" action="/card/save">
<input type="hidden" name="previous" value="{k.day:%Y-%m-%d}">
<div class="card"><h2>Daily report card</h2>
<div class="fields">
<div class="field"><label>date</label>
<input type="date" name="date" value="{k.day:%Y-%m-%d}" required
 onclick="this.showPicker && this.showPicker()"></div>
<div class="field"><label>process grade</label>
<input type="text" name="grade" list="grades" value="{esc(k.grade)}"
 placeholder="A" style="width:110px"><datalist id="grades">{options}</datalist></div>
<div class="field"><label>P&amp;L, {H.sign(j.currency())}</label>
<input type="number" name="pnl" step="0.01" style="width:130px"
 value="{"" if k.pnl is None else f"{k.pnl:g}"}"></div>
<div class="field"><label>opportunity quality</label>
<input type="text" name="quality" list="grades" value="{esc(k.quality)}"
 placeholder="B" style="width:150px"></div>
</div>
<p class="caption">P&amp;L for the day by closed trades:
{amount(j, day_pnl(j, day), signed=True)}. The field is yours to override.</p>
</div>
<div class="card">{sections}</div>
<div class="card">{assessment_rows(k, closed)}</div>
<div class="actions"><button class="btn primary">Save card</button>
<a class="btn" href="/cards">Cancel</a>{delete}</div>
</form>"""
    return page(f"Card {day:%d.%m.%Y}", body, "cards")


def save_card(data):
    day = day_from_url(one(data, "date"))
    previous = one(data, "previous")
    k = Card(day=day, grade=one(data, "grade"), quality=one(data, "quality"))
    pnl = one(data, "pnl")
    k.pnl = float(pnl.replace(",", ".")) if pnl else None
    for name, _, _ in CARD_SECTIONS:
        setattr(k, name, one(data, name))
    k.assessment = read_assessment(data)
    old = store.load_card(ROOT, day)
    if old is not None and previous and previous != k.id:
        raise RecordError(f"there is a card for {k.id} already: open that one "
                          f"instead of moving this one onto it")
    if old is not None:
        k.extra = old.extra
    store.save_card(ROOT, k)
    # the date was changed in the form, which is a rename, not a second card
    if previous and previous != k.id:
        store.delete_card(ROOT, day_from_url(previous))
    return k


# --- weekly card -----------------------------------------------------------
# The paper Weekly Report Card, next to the daily one: the same fields in the
# same order, plus the assessment of the week's trades. One file per ISO week,
# in journal/cards with the daily ones, keyed the way the journal groups its
# trades by week.

def week_from_url(text):
    key = (text or "").strip().upper()
    Week(week=key).check()          # the format is the id, so it is checked here
    return key


def week_trades(j, key):
    """The trades the week closed: the figures a new card is offered."""
    return [t for t in j.trades if not t.is_open and t.closed
            and stats.week(t.closed) == key]


def week_dates(k):
    return f"{k.monday:%d.%m} - {k.monday + timedelta(days=6):%d.%m.%Y}"


def week_page(key):
    j = journal()
    k = store.load_week(ROOT, key)
    closed = week_trades(j, key)
    is_new = k is None
    if is_new:
        k = Week(week=key, pnl=sum(t.pnl or 0.0 for t in closed) or None,
                 trades=len(closed) or None)
    options = "".join(f'<option value="{g}">' for g in GRADES)
    progress = "".join(
        f'<option value="{n}"{" selected" if k.progress == n else ""}>{n}</option>'
        for n in range(1, 6))
    sections = ""
    for name, _, label in WEEK_SECTIONS:
        sections += (f'<h3>{esc(label)}</h3>'
                     f'<textarea name="{name}" style="min-height:'
                     f'{SECTION_HEIGHT.get(name, 84)}px">{esc(getattr(k, name))}'
                     f'</textarea>')
        if name == "focus":
            sections += (f'<div class="fields" style="margin-top:8px">'
                         f'<div class="field"><label>progress</label>'
                         f'<select name="progress" style="width:110px">'
                         f'<option value=""></option>{progress}</select>'
                         f'</div></div>')
    delete = "" if is_new else (
        f'<span class="right"><button class="btn danger" '
        f'formaction="/week/{U(k.id)}/delete" formnovalidate '
        f'onclick="return confirm(\'Delete the card for week {k.number}? '
        f'It goes to .trash.\')">Delete</button></span>')
    body = f"""<form method="post" action="/week/save">
<input type="hidden" name="previous" value="{k.week}">
<div class="card"><h2>Weekly report card</h2>
<div class="fields">
<div class="field"><label>week</label>
<input type="week" name="week" value="{k.week}" required
 onclick="this.showPicker && this.showPicker()" style="width:150px"></div>
<div class="field"><label>process grade</label>
<input type="text" name="grade" list="grades" value="{esc(k.grade)}"
 placeholder="A" style="width:110px"><datalist id="grades">{options}</datalist></div>
<div class="field"><label>P&amp;L, {H.sign(j.currency())}</label>
<input type="number" name="pnl" step="0.01" style="width:130px"
 value="{"" if k.pnl is None else f"{k.pnl:g}"}"></div>
<div class="field"><label>trades</label>
<input type="number" name="trades" step="1" min="0" style="width:90px"
 value="{"" if k.trades is None else k.trades}"></div>
<div class="field"><label>opportunity quality</label>
<input type="text" name="quality" list="grades" value="{esc(k.quality)}"
 placeholder="B" style="width:150px"></div>
</div>
<p class="caption">{week_dates(k)}. The week closed {len(closed)}
{"trade" if len(closed) == 1 else "trades"} for
{amount(j, sum(t.pnl or 0.0 for t in closed), signed=True)}. The fields are
yours to override.</p>
</div>
<div class="card">{sections}</div>
<div class="card">{assessment_rows(k, closed)}</div>
<div class="actions"><button class="btn primary">Save card</button>
<a class="btn" href="/cards">Cancel</a>{delete}</div>
</form>"""
    return page(f"Week {k.number}", body, "cards")


def save_week(data):
    key = week_from_url(one(data, "week"))
    previous = one(data, "previous")
    k = Week(week=key, grade=one(data, "grade"), quality=one(data, "quality"))
    pnl = one(data, "pnl")
    k.pnl = float(pnl.replace(",", ".")) if pnl else None
    trades = one(data, "trades")
    k.trades = int(float(trades.replace(",", "."))) if trades else None
    progress = one(data, "progress")
    k.progress = int(progress) if progress else None
    for name, _, _ in WEEK_SECTIONS:
        setattr(k, name, one(data, name))
    k.assessment = read_assessment(data)
    old = store.load_week(ROOT, key)
    if old is not None and previous and previous != k.week:
        raise RecordError(f"there is a card for {k.week} already: open that one "
                          f"instead of moving this one onto it")
    if old is not None:
        k.extra = old.extra
    store.save_week(ROOT, k)
    # the week was changed in the form, which is a rename, not a second card
    if previous and previous != k.week:
        store.delete_week(ROOT, week_from_url(previous))
    return k


# --- reports ---------------------------------------------------------------

def md_to_html(text, link=None):
    """A tiny renderer: we generate the reports ourselves, their markup is simple.

    `link(section, value)` may hand back an address for the first cell of a row,
    which is how a line of a report leads to the trades behind it."""
    parts, in_table, section = [], False, ""
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if not in_table:
                # the first row of a table is its head: no icons and no link,
                # or "account" would lead to an account by that name
                parts.append('<table><thead><tr>' + "".join(
                    f'<th class="{"num" if i else ""}">{esc(c)}</th>'
                    for i, c in enumerate(cells)) + "</tr></thead><tbody>")
                in_table = True
                continue
            # under "By pair" the first column holds symbols, so they get their
            # icons here, the same as everywhere else
            show = H.pair if section == "By pair" else esc
            first = show(cells[0])
            href = link(section, cells[0]) if link else None
            if href:
                first = f'<a href="{href}">{first}</a>'
            parts.append("<tr>" + f"<td>{first}</td>" + "".join(
                f'<td class="num">{esc(c)}</td>' for c in cells[1:]) + "</tr>")
            continue
        if in_table:
            parts.append("</tbody></table>")
            in_table = False
        if s.startswith("### "):
            section = s[4:]
            parts.append(f"<h3>{esc(section)}</h3>")
        elif s.startswith("## "):
            parts.append(f"<h2>{esc(s[3:])}</h2>")
        elif s.startswith("# "):
            parts.append(f"<h2>{esc(s[2:])}</h2>")
        elif s:
            parts.append(f"<p>{esc(s)}</p>")
    if in_table:
        parts.append("</tbody></table>")
    return "".join(parts)


def reports_page():
    j = journal()
    months = stats.months(j.trades)
    quarters = sorted({stats.quarter(t.opened) for t in j.trades})
    ready = reports.existing(ROOT)
    ready_rows = "".join(
        f'<tr><td><a href="/report/{U(p)}">{esc(p)}</a></td>'
        f'<td class="muted">{esc(report_kind(p))}</td></tr>' for p in ready
    ) or '<tr><td class="muted">none yet</td><td></td></tr>'
    form = f"""<form method="post" action="/report/build" class="filters">
<div><label>month</label>
{select("period_month", list(reversed(months)), "", empty="-")}</div>
<div><button class="btn primary" name="what" value="month">Build month</button></div>
<div><label>quarter</label>
{select("period_quarter", list(reversed(quarters)), "", empty="-")}</div>
<div><button class="btn" name="what" value="quarter">Build quarter</button></div>
</form>"""
    body = (f'<div class="card"><h2>Build a report</h2>{form}'
            f'<p class="caption">Rebuilding refreshes the numbers and never '
            f'touches your conclusions.</p></div>'
            f'<div class="card"><h2>Existing reports</h2>'
            f'<table><tbody>{ready_rows}</tbody></table></div>')
    return page("Reports", body, "reports")


def report_kind(period):
    return "quarter" if "Q" in period else "month"


# Which filter of the journal a column of a report belongs to. The heading is
# the one written into the file, so a report built long ago still links.
REPORT_LINKS = {"By style": "style", "By pair": "pair", "By account": "account",
                "By direction": "direction",
                "Balance change by account": "account"}


def report_link(period):
    """A row of a report leads to the trades it was counted from: the same
    filter, narrowed to the months of the report."""
    since, until = reports.period_months(period)

    def link(section, value):
        # the best and the worst row name a trade, so they lead to it directly
        if section == "Best and worst trade" and value:
            return f"/trade/{U(value)}"
        field = REPORT_LINKS.get(section)
        if not field or not value:
            return None
        return (f"/?{field}={U(value)}&from={U(since)}&to={U(until)}"
                f"&group={'month' if 'Q' in period else 'week'}")
    return link


def report_page(period):
    head, body = reports.read(ROOT, period)
    if body is None:
        return None
    j = journal()
    trades = reports.trades_of_period(j, period)
    conclusions = reports.previous_conclusions(ROOT, period)
    without = re.split(r"^## Conclusions\s*$", body, maxsplit=1, flags=re.M)[0]
    # the summary, then the rings, then the tables: the picture stands next to
    # the few figures it draws, not at the foot of a page of tables
    top, _, rest = without.partition("\n### ")
    link = report_link(period)
    form = f"""<form method="post" action="/report/{U(period)}">
<textarea name="conclusions" placeholder="What you learned this period">{esc(conclusions)}</textarea>
<p><button class="btn primary">Save conclusions</button>
<button class="btn" name="rebuild" value="1">Recalculate</button></p></form>"""
    caption = (f'<p class="caption">A pair, an account, a style, a direction or '
               f'one of the two trades named in these tables opens what is behind '
               f'the row, over the same months. The figures are the ones counted '
               f'at the last build, {esc(head.get("updated", ""))}; the rings are '
               f'drawn from the journal as it is now, so press Recalculate if a '
               f'trade of the period changed since.</p>')
    html = (f'<div class="card">{md_to_html(top, link)}'
            f'{"" if rest else caption}</div>'
            f'{r_rings(j, trades)}'
            + (f'<div class="card">{md_to_html("### " + rest, link)}{caption}</div>'
               if rest else "")
            + f'<div class="card"><h2>Conclusions</h2>{form}</div>')
    return page(period, html, "reports",
                  '<a class="btn" href="/reports">All reports</a>')


# --- accounts and pairs ----------------------------------------------------

_ACCOUNT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")


def accounts_page(message=""):
    j = journal(True)
    rows = []
    for a in sorted(j.accounts):
        account = j.accounts[a]
        trades = sum(1 for t in j.trades if t.account == a)
        adjustments = sum(1 for c in j.adjustments if c.account == a)
        used = trades + adjustments
        archive = ("Unarchive", "Archived") if account.archived else ("Archive", "Active")
        delete = (
            f'<form method="post" action="/account/delete" style="display:inline" '
            f'onsubmit="return confirm(\'Delete account {esc(account.name or a)}?\')">'
            f'<input type="hidden" name="id" value="{esc(a)}">'
            f'<button class="btn danger">Delete</button></form>'
            if used == 0 else
            f'<span class="caption">has {trades} trades / {adjustments} '
            f'adjustments, archive instead</span>')
        out = j.cashed_out(a)
        limit = account.daily_loss_limit
        rows.append(
            f'<tr><td>{esc(account.name or a)}<div class="caption">{esc(a)} · '
            f'{esc(account.currency)}</div></td>'
            f'<td class="num">{amount(j, account.start_balance, a)}</td>'
            f'<td class="num">{amount(j, j.balance(a), a)}</td>'
            f'<td class="num">{amount(j, out, a) if out else "-"}</td>'
            f'<td class="num">{trades}</td>'
            f'<td><form method="post" action="/account/limit" '
            f'style="display:inline;white-space:nowrap">'
            f'<input type="hidden" name="id" value="{esc(a)}">'
            f'<input type="number" name="limit" step="1" min="1" placeholder="none" '
            f'value="{"" if limit is None else f"{limit:g}"}" style="width:92px"> '
            f'<button class="btn">Set</button></form></td>'
            f'<td>{archive[1]}</td>'
            f'<td><form method="post" action="/account/archive" style="display:inline">'
            f'<input type="hidden" name="id" value="{esc(a)}">'
            f'<button class="btn">{archive[0]}</button></form> {delete}</td></tr>')

    pairs = store.all_pairs(ROOT)
    from_trades = {t.pair for t in j.trades if t.pair != PAIR_NOT_SET}
    # A pair that comes from trades has no button: the suggestion list does not
    # hold it anyway, and "remove" would look like an action that changes nothing.
    pair_rows = "".join(
        f'<tr><td>{H.pair(p)}</td>'
        f'<td class="caption">{"used in trades" if p in from_trades else "manual"}</td>'
        f'<td>' + (
            f'<form method="post" action="/pair/delete" style="display:inline">'
            f'<input type="hidden" name="pair" value="{esc(p)}">'
            f'<button class="btn">Remove</button></form>'
            if p not in from_trades else '<span class="caption">-</span>')
        + '</td></tr>'
        for p in sorted(set(pairs) | from_trades))

    def times(n):
        return "not used yet" if not n else f"{n} trade" if n == 1 else f"{n} trades"

    def word_button(action, kind, word, label):
        return (f'<form method="post" action="/list/{action}" style="display:inline">'
                f'<input type="hidden" name="kind" value="{esc(kind)}">'
                f'<input type="hidden" name="word" value="{esc(word)}">'
                f'<button class="btn">{label}</button></form>')

    def word_rows(kind, used):
        """What the form offers, and below it what the trades carry beyond that.

        A word only the trades have is the way back for a style you retired:
        it says how many trades hold it, and Add puts it in the form again."""
        words = store.all_words(ROOT, kind)
        rows = [f'<tr><td>{esc(w)}</td>'
                f'<td class="caption">{times(used.get(w, 0))}</td>'
                f'<td>{word_button("delete", kind, w, "Remove")}</td></tr>'
                for w in words]
        rows += [f'<tr><td>{esc(w)}</td>'
                 f'<td class="caption">{times(used[w])}, not offered</td>'
                 f'<td>{word_button("new", kind, w, "Add")}</td></tr>'
                 for w in sorted(set(used) - set(words))]
        return "".join(rows) or ('<tr><td colspan="3" class="caption">'
                                 'the list is empty</td></tr>')

    def counted(pick):
        used = {}
        for t in j.trades:
            for word in pick(t):
                if word:
                    used[word] = used.get(word, 0) + 1
        return used

    lists = ""
    for kind, label, hint in (
            ("styles", "Trading styles", "scalp"),
            ("timeframes", "Timeframes", "M5"),
            ("execution", "Execution formats", "OB retest")):
        used = counted({"styles": lambda t: [t.style],
                        "timeframes": lambda t: [t.entry_tf],
                        "execution": lambda t: t.execution}[kind])
        lists += f"""<details class="fold"><summary>{label}
<span class="caption">{len(store.all_words(ROOT, kind))} in the list</span></summary>
<form method="post" action="/list/new" class="filters">
<input type="hidden" name="kind" value="{kind}">
<div><label>add</label><input type="text" name="word" placeholder="{hint}"
 required style="width:160px"></div>
<div><button class="btn primary">Add</button></div>
</form>
<table><thead><tr><th>{label.lower()}</th><th>trades</th><th></th></tr></thead>
<tbody>{word_rows(kind, used)}</tbody></table></details>
"""

    live = [a for a in sorted(j.accounts) if not j.accounts[a].archived]
    every = sorted(j.accounts)
    today = datetime.now().strftime("%Y-%m-%d")

    def move_rows(kinds):
        # newest first: a list of money movements is read from the last one
        return "".join(
        f'<tr><td>{c.day:%d.%m.%Y}</td>'
        f'<td>{esc(j.accounts[c.account].name if c.account in j.accounts else c.account)}</td>'
        f'<td>{esc(c.kind)}</td>'
        f'<td class="num {"win" if c.amount > 0 else "lose"}">'
        f'{amount(j, c.amount, c.account, signed=True)}</td>'
        f'<td>{esc(c.comment) or "<span class=\'muted\'>-</span>"}</td>'
        f'<td><form method="post" action="/money/delete" style="display:inline" '
        f'onsubmit="return confirm(\'Delete this record? It moves to .trash.\')">'
        f'<input type="hidden" name="id" value="{esc(c.id)}">'
            f'<button class="btn danger">Delete</button></form></td></tr>'
            for c in reversed(j.adjustments) if c.kind in kinds)

    def move_table(kinds, empty):
        rows = move_rows(kinds)
        return (f'<table><thead><tr><th>date</th><th>account</th><th>what</th>'
                f'<th class="num">amount</th><th>comment</th><th></th></tr></thead>'
                f'<tbody>{rows}</tbody></table>' if rows else
                f'<p class="muted">{empty}</p>')

    def count(kinds):
        n = sum(1 for c in j.adjustments if c.kind in kinds)
        return f"{n} record" if n == 1 else f"{n} records"

    money = f"""<div class="card"><h2>Money and corrections</h2>
<details class="fold"><summary>Money in and out
<span class="caption">{count(MONEY_KINDS)}</span></summary>
<form method="post" action="/money/new" class="filters">
<div><label>account</label>{select("account", live)}</div>
<div><label>what</label>{select("kind", MONEY_KINDS)}</div>
<div><label>amount</label><input type="number" name="amount" step="0.01"
 min="0.01" placeholder="500" required style="width:120px"></div>
<div><label>date</label><input type="date" name="day" value="{today}"
 onclick="this.showPicker && this.showPicker()"></div>
<div><label>comment</label><input type="text" name="comment"
 placeholder="payout" style="width:200px"></div>
<div><button class="btn primary">Record</button></div>
</form>
<p class="caption">The amount is always positive: what it does to the balance is
decided by what you picked. A withdrawal is also counted as a cashout, and the
total sits in the accounts table above.</p>
{move_table(MONEY_KINDS, "No money has been moved yet.")}
<p class="caption">Deleting moves the record to <code>.trash</code>. Balances are
recomputed from what is left, nothing is stored as a number.</p>
</details>

<details class="fold"><summary>Correct a balance
<span class="caption">{count(("reconciliation",))}</span></summary>
<form method="post" action="/money/correct" class="filters">
<div><label>account</label>{select("account", every)}</div>
<div><label>real balance now</label><input type="number" name="balance"
 step="0.01" required style="width:150px"></div>
<div><label>date</label><input type="date" name="day" value="{today}"
 onclick="this.showPicker && this.showPicker()"></div>
<div><label>comment</label><input type="text" name="comment"
 placeholder="swap, commission, broker says otherwise" style="width:240px"></div>
<div><button class="btn">Correct</button></div>
</form>
<p class="caption">Type what the broker shows. The journal writes down the
difference as a correction and never touches the start balance or the trades:
that is what keeps the history honest.</p>
{move_table(("reconciliation",), "Nothing has been corrected yet.")}
</details>
<p class="caption">Both are kept in <code>journal/adjustments/</code>, and both
move the balance; they are apart here because one is money you moved and the
other is a difference you found.</p></div>"""

    trashed = store.trash_list(ROOT)
    trash_rows = "".join(
        f'<tr><td class="muted">{kind}</td><td>{esc(record_id)}</td>'
        f'<td>{when:%d.%m.%Y %H:%M}</td>'
        f'<td><form method="post" action="/trash/restore" style="display:inline">'
        f'<input type="hidden" name="name" value="{esc(name)}">'
        f'<button class="btn">Restore</button></form></td></tr>'
        for name, kind, record_id, when in trashed)
    trash = (f'<div class="card"><h2>Trash</h2>'
             + (f'<table><thead><tr><th>what</th><th>id</th><th>deleted</th>'
                f'<th></th></tr></thead><tbody>{trash_rows}</tbody></table>'
                if trashed else
                '<p class="muted">Nothing has been deleted.</p>')
             + f'<p class="caption">Everything deleted lands in <code>.trash</code> '
             f'next to the journal and is put back from here, screenshots and '
             f'all. A record written again under the same id since is not '
             f'overwritten: the one in the trash stays there.</p></div>')

    top = (f'<div class="card"><p>{esc(message)}</p></div>' if message else "")
    body = f"""{top}
<div class="card"><h2>Accounts</h2>
<table><thead><tr><th>account</th><th class="num">start</th><th class="num">current</th>
<th class="num">cashed out</th><th class="num">trades</th><th>daily loss limit</th>
<th>status</th><th></th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<p class="caption">An account with trades cannot be deleted, archive it instead.
Archived accounts stay in history and statistics but are not offered when opening
a trade. The daily loss limit is a prop rule: the most a day may lose before the
firm closes the account. With one set, the tile on the front page adds up what
today has already cost and what the open trades still put at risk, turns amber at
four fifths of the limit and red when it is reached. Leave it empty for an
account that has no such rule.</p></div>

{money}

<div class="card"><h2>New account</h2>
<form method="post" action="/account/new" class="filters">
<div><label>id</label><input type="text" name="id" placeholder="broker-2"
 pattern="[a-z0-9][a-z0-9-]*" required style="width:130px"></div>
<div><label>name</label><input type="text" name="name" placeholder="Broker 2"
 style="width:160px"></div>
<div><label>start balance</label><input type="number" name="start" step="0.01"
 value="10000" style="width:130px"></div>
<div><label>currency</label><input type="text" name="currency" value="USD"
 style="width:70px"></div>
<div><label>daily loss limit</label><input type="number" name="limit" step="1"
 min="1" placeholder="none" style="width:110px"></div>
<div><button class="btn primary">Create account</button></div>
</form>
<p class="caption">id is used in file names: latin letters, digits and dashes.
The currency is shown next to every sum of this account; its sign is drawn for
the usual ones and the code is written for the rest.</p></div>

{trash}

<div class="card"><h2>Trading pairs</h2>
<form method="post" action="/pair/new" class="filters">
<div><label>pair</label><input type="text" name="pair" placeholder="EURJPY"
 required style="width:130px"></div>
<div><button class="btn primary">Add pair</button></div>
</form>
<table><thead><tr><th>pair</th><th>source</th><th></th></tr></thead>
<tbody>{pair_rows}</tbody></table>
<p class="caption">Removing a pair only takes it out of the suggestion list;
trades already recorded with it are not touched.</p></div>

<div class="card"><h2>The trade form</h2>
{lists}
<p class="caption">These are the words the form offers: the style, the entry
timeframe and the execution checkboxes. A new one goes to the end of its list,
which is why the timeframes stay in the order you trade them. Removing a word
only stops it being offered: the trades that carry it keep it, and it still
shows in the filters, the statistics and the reports. Every style in the list
gets a winrate tile of its own on the journal page.</p></div>"""
    return page("Accounts", body, "accounts")


def create_account(data):
    account_id = one(data, "id").lower()
    if not _ACCOUNT_ID.match(account_id):
        raise RecordError("account id: latin letters, digits and dashes only")
    if account_id in journal(True).accounts:
        raise RecordError(f"account {account_id} already exists")
    limit = one(data, "limit")
    store.save_account(ROOT, Account(
        id=account_id, name=one(data, "name") or account_id,
        start_balance=float(one(data, "start", "0").replace(",", ".")),
        currency=(one(data, "currency", "USD") or "USD").upper(),
        daily_loss_limit=float(limit.replace(",", ".")) if limit else None))
    drop_cache()
    return f"Account {account_id} created."


def set_limit(data):
    account_id = one(data, "id")
    j = journal(True)
    if account_id not in j.accounts:
        raise RecordError("no such account")
    account = j.accounts[account_id]
    limit = one(data, "limit")
    account.daily_loss_limit = float(limit.replace(",", ".")) if limit else None
    store.save_account(ROOT, account)
    drop_cache()
    if account.daily_loss_limit is None:
        return f"{account_id}: no daily loss limit."
    return (f"{account_id}: the daily loss limit is "
            f"{amount(j, account.daily_loss_limit, account_id)}.")


def restore_record(data):
    try:
        kind, record_id = store.restore(ROOT, one(data, "name"))
    except (OSError, ValueError) as e:
        raise RecordError(str(e))
    drop_cache()
    return f"{kind} {record_id} is back in the journal."


def toggle_archive(data):
    account_id = one(data, "id")
    j = journal(True)
    if account_id not in j.accounts:
        raise RecordError("no such account")
    account = j.accounts[account_id]
    account.archived = not account.archived
    store.save_account(ROOT, account)
    drop_cache()
    return f"Account {account_id} {'archived' if account.archived else 'unarchived'}."


def delete_account(data):
    account_id = one(data, "id")
    j = journal(True)
    if account_id not in j.accounts:
        raise RecordError("no such account")
    used = (sum(1 for t in j.trades if t.account == account_id)
            + sum(1 for c in j.adjustments if c.account == account_id))
    if used:
        raise RecordError(f"account {account_id} has {used} records, "
                          f"archive it instead")
    store.delete_account(ROOT, account_id)
    drop_cache()
    return f"Account {account_id} moved to .trash."


def money_day(text):
    """The date of a money movement, today when the field came back empty."""
    if not text:
        return datetime.now()
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise RecordError(f"bad date {text!r}: expected YYYY-MM-DD")


def record_money(data):
    """A deposit, a withdrawal or a fee, written down as an adjustment.

    The form always sends a positive amount; the sign belongs to the kind, so
    that a withdrawal cannot be typed in as a plus by accident."""
    j = journal(True)
    account = one(data, "account")
    if account not in j.accounts:
        raise RecordError("no such account")
    kind = one(data, "kind")
    if kind not in MONEY_KINDS:
        raise RecordError(f"bad kind {kind!r}")
    money = abs(float(one(data, "amount", "0").replace(",", ".")))
    if not money:
        raise RecordError("amount is zero")
    day = money_day(one(data, "day"))
    c = Adjustment(id=store.new_adjustment_id(ROOT, day, kind, account),
                   account=account, kind=kind,
                   amount=money if kind == "deposit" else -money,
                   day=day, comment=one(data, "comment"))
    store.save_adjustment(ROOT, c)
    drop_cache()
    word = {"deposit": "added to", "withdrawal": "taken off",
            "fee": "charged to"}[kind]
    return f"{amount(j, money, account)} {word} {account}."


def correct_balance(data):
    """The real balance is typed in; the journal stores the difference.

    History is never edited to make a number agree with the broker: the gap is
    a record of its own, with the day it was noticed and a comment saying why."""
    j = journal(True)
    account = one(data, "account")
    if account not in j.accounts:
        raise RecordError("no such account")
    real = float(one(data, "balance", "0").replace(",", "."))
    day = money_day(one(data, "day"))
    gap = round(real - j.balance(account), 2)
    if not gap:
        return f"{account} already stands at {amount(j, real, account)}, nothing to correct."
    c = Adjustment(id=store.new_adjustment_id(ROOT, day, "reconciliation", account),
                   account=account, kind="reconciliation", amount=gap, day=day,
                   comment=one(data, "comment"))
    store.save_adjustment(ROOT, c)
    drop_cache()
    return (f"{account}: {amount(j, gap, account, signed=True)} written down as a "
            f"correction, the balance now reads {amount(j, real, account)}.")


def delete_money(data):
    adjustment_id = one(data, "id")
    if not store.safe_dir_name(adjustment_id):
        raise RecordError("bad id")
    if store.delete_adjustment(ROOT, adjustment_id) is None:
        raise RecordError("no such record")
    drop_cache()
    return f"Record {adjustment_id} moved to .trash."


def add_pair(data):
    pair = one(data, "pair").upper()
    if not re.match(r"^[A-Z0-9.\-]{2,20}$", pair):
        raise RecordError("pair: latin letters, digits, dot or dash")
    store.save_pairs(ROOT, store.all_pairs(ROOT) + [pair])
    return f"Pair {pair} added."


def remove_pair(data):
    pair = one(data, "pair").upper()
    store.save_pairs(ROOT, [p for p in store.all_pairs(ROOT) if p != pair])
    return f"Pair {pair} removed from the suggestion list."


# a word of a list: no line breaks, no header trouble, short enough for a select
_WORD = re.compile(r"^[^\s][^\n\r:]{0,23}$")


def _kind(data):
    kind = one(data, "kind")
    if kind not in store.VOCABULARY:
        raise RecordError("no such list")
    return kind


def add_word(data):
    kind, word = _kind(data), one(data, "word")
    if not _WORD.match(word):
        raise RecordError("a word of up to 24 characters, without a colon")
    words = store.all_words(ROOT, kind)
    if word.lower() in {w.lower() for w in words}:
        raise RecordError(f"{word} is already in the list")
    store.save_words(ROOT, kind, words + [word])
    return f"{word} is offered in the trade form now."


def remove_word(data):
    kind, word = _kind(data), one(data, "word")
    words = store.all_words(ROOT, kind)
    if kind == "styles" and len(words) <= 1:
        raise RecordError("a trade needs a style: keep at least one in the list")
    if word not in words:
        raise RecordError(f"{word} is not in the list")
    store.save_words(ROOT, kind, [w for w in words if w != word])
    return f"{word} is no longer offered in the trade form."


# --- HTTP ------------------------------------------------------------------

def U(s):
    return urllib.parse.quote(str(s), safe="")


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "Plainbook"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass                                   # quiet: a server log is not needed

    # --- responses ---
    def _send(self, text, code=200, kind="text/html; charset=utf-8", headers=()):
        data = text.encode("utf-8") if isinstance(text, str) else text
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _go(self, where, said=""):
        """A redirect, and the word the next page says in the middle of itself."""
        if said:
            where += ("&" if "?" in where else "?") + "said=" + U(said)
        self.send_response(303)
        self.send_header("Location", where)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _file(self, path):
        if not os.path.isfile(path):
            return self._send("no such file", 404, "text/plain; charset=utf-8")
        kind = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp"}.get(
                    os.path.splitext(path)[1].lower(), "application/octet-stream")
        with open(path, "rb") as f:
            self._send(f.read(), 200, kind)

    def _same_origin(self):
        """A simple guard against another page in the same browser."""
        origin = self.headers.get("Origin") or self.headers.get("Referer") or ""
        if not origin:
            return True
        host = urllib.parse.urlsplit(origin).netloc
        return host in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    # --- routes ---
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        q = urllib.parse.parse_qs(parsed.query)
        parts = [c for c in path.split("/") if c]
        # the word a form left in the address is taken out of the query here,
        # so that no page counts it as a filter of its own
        SAID.text = (q.pop("said", [""]) or [""])[0][:60]
        SAID.url = parsed.path + ("?" + urllib.parse.urlencode(q, doseq=True)
                                  if q else "")

        if path == "/":
            return self._send(home_page(q))
        if path == "/stats":
            return self._send(stats_page(q))
        if path == "/search":
            return self._send(search_page(q))
        if path == "/export.csv":
            j = journal()
            stamp = datetime.now().strftime("%Y-%m-%d")
            return self._send(export_csv(j, apply_filters(j, q)), 200,
                              "text/csv; charset=utf-8",
                              [("Content-Disposition",
                                f'attachment; filename="plainbook-{stamp}.csv"')])
        if path == "/reports":
            return self._send(reports_page())
        if path == "/cards":
            return self._send(cards_page())
        if len(parts) == 2 and parts[0] == "card":
            try:
                day = day_from_url(parts[1])
            except RecordError as e:
                return self._send(str(e), 404, "text/plain; charset=utf-8")
            return self._send(card_page(day))
        if path == "/weeks":
            return self._go("/cards")       # the weekly cards live on that tab
        if len(parts) == 2 and parts[0] == "week":
            try:
                key = week_from_url(parts[1])
            except RecordError as e:
                return self._send(str(e), 404, "text/plain; charset=utf-8")
            return self._send(week_page(key))
        if path == "/accounts":
            return self._send(accounts_page((q.get("m") or [""])[0]))
        if path == "/plans":
            return self._send(plans_page())
        if path == "/plan/new":
            return self._send(page("New plan", plan_form(None, new_token()),
                                     "plans"))
        if len(parts) == 2 and parts[0] == "plan":
            shown = plan_page(parts[1])
            return self._send(shown or "no such plan", 200 if shown else 404)
        if len(parts) == 3 and parts[0] == "plan" and parts[2] == "edit":
            if not store.safe_dir_name(parts[1]):
                return self._send("bad plan id", 400)
            try:
                k = store.load_plan(ROOT, parts[1])
            except OSError:
                return self._send("no such plan", 404)
            return self._send(page(k.title or k.id,
                                     plan_form(k, new_token()), "plans"))
        if len(parts) == 3 and parts[0] == "plan-shot":
            if not store.safe_dir_name(parts[1]):
                return self._send("bad plan id", 400, "text/plain; charset=utf-8")
            return self._file(os.path.join(store.plan_dir(ROOT, parts[1]),
                                           store.SHOTS,
                                           os.path.basename(parts[2])))
        if path == "/open-count":
            return self._send(str(len(journal().open_trades())), 200,
                              "text/plain; charset=utf-8")
        if len(parts) == 2 and parts[0] == "trade":
            shown = trade_page(parts[1])
            return self._send(shown or "no such trade", 200 if shown else 404)
        if len(parts) == 2 and parts[0] == "report":
            shown = report_page(parts[1])
            return self._send(shown or "no such report", 200 if shown else 404)
        if path == "/new":
            return self._send(page("New trade", trade_form(None, new_token()),
                                     "journal"))
        if len(parts) == 2 and parts[0] in ("edit", "close"):
            t = next((x for x in journal().trades if x.id == parts[1]), None)
            if t is None:
                return self._send("no such trade", 404)
            token = new_token()
            body = (trade_form(t, token) if parts[0] == "edit"
                    else close_form(t, token))
            return self._send(page(t.id, body, "journal"))
        if len(parts) == 3 and parts[0] == "shot":
            if not store.safe_dir_name(parts[1]):
                return self._send("bad trade id", 400, "text/plain; charset=utf-8")
            return self._file(os.path.join(store.shots_dir(ROOT, parts[1]),
                                           os.path.basename(parts[2])))
        if len(parts) == 3 and parts[0] == "draft":
            try:
                folder = draft_dir(parts[1])
            except ValueError:
                return self._send("bad token", 400)
            return self._file(os.path.join(folder, os.path.basename(parts[2])))
        return self._send("no such page", 404)

    def do_POST(self):
        if not self._same_origin():
            return self._send("foreign origin", 403)
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        q = urllib.parse.parse_qs(parsed.query)
        parts = [c for c in path.split("/") if c]
        length = int(self.headers.get("Content-Length") or 0)
        if length > SHOT_LIMIT:
            return self._send("body too large", 413, "text/plain; charset=utf-8")
        raw = self.rfile.read(length) if length else b""

        if path == "/draft/upload":
            token = (q.get("token") or [""])[0]
            try:
                name = save_draft(token, (q.get("zone") or [""])[0], raw)
            except ValueError as e:
                return self._send(str(e), 400, "text/plain; charset=utf-8")
            return self._send(json.dumps(
                {"file": name, "url": f"/draft/{U(token)}/{U(name)}"}),
                200, "application/json")

        data = urllib.parse.parse_qs(raw.decode("utf-8"), keep_blank_values=True)
        try:
            if path == "/new":
                t = create_trade(data)
                return self._go(f"/trade/{U(t.id)}", "Trade opened")
            if len(parts) == 2 and parts[0] == "edit":
                t = next((x for x in journal(True).trades if x.id == parts[1]), None)
                if t is None:
                    return self._send("no such trade", 404)
                edit_trade(t, data)
                return self._go(f"/trade/{U(t.id)}", "Trade saved")
            if path == "/plan/new":
                k = create_plan(data)
                return self._go(f"/plan/{U(k.id)}", "Plan written")
            if len(parts) == 3 and parts[0] == "plan":
                if not store.safe_dir_name(parts[1]):
                    return self._send("bad plan id", 400)
                if parts[2] == "delete":
                    if store.delete_plan(ROOT, parts[1]) is None:
                        return self._send("no such plan", 404)
                    return self._go("/plans", "Plan moved to the trash")
                try:
                    k = store.load_plan(ROOT, parts[1])
                except OSError:
                    return self._send("no such plan", 404)
                if parts[2] == "edit":
                    edit_plan(k, data)
                    said = "Plan saved"
                elif parts[2] == "update":
                    add_update(k, data)
                    said = "Update added"
                else:
                    return self._send("no such page", 404)
                return self._go(f"/plan/{U(k.id)}", said)
            if path == "/card/save":
                k = save_card(data)
                return self._go(f"/card/{U(k.id)}", "DRC saved")
            if len(parts) == 3 and parts[0] == "card" and parts[2] == "delete":
                store.delete_card(ROOT, day_from_url(parts[1]))
                return self._go("/cards", "DRC moved to the trash")
            if path == "/week/save":
                k = save_week(data)
                return self._go(f"/week/{U(k.id)}", "WRC saved")
            if len(parts) == 3 and parts[0] == "week" and parts[2] == "delete":
                store.delete_week(ROOT, week_from_url(parts[1]))
                return self._go("/cards", "WRC moved to the trash")
            if len(parts) == 3 and parts[0] == "trade" and parts[2] == "delete":
                if next((x for x in journal(True).trades if x.id == parts[1]),
                        None) is None:
                    return self._send("no such trade", 404)
                store.delete_trade(ROOT, parts[1])
                drop_cache()
                return self._go("/", "Trade moved to the trash")
            if len(parts) == 2 and parts[0] == "close":
                t = next((x for x in journal(True).trades if x.id == parts[1]), None)
                if t is None:
                    return self._send("no such trade", 404)
                close_trade(t, data)
                return self._go(f"/trade/{U(t.id)}", "Trade closed")
            for route, action in (("/account/new", create_account),
                                  ("/account/archive", toggle_archive),
                                  ("/account/delete", delete_account),
                                  ("/account/limit", set_limit),
                                  ("/trash/restore", restore_record),
                                  ("/money/new", record_money),
                                  ("/money/correct", correct_balance),
                                  ("/money/delete", delete_money),
                                  ("/pair/new", add_pair),
                                  ("/pair/delete", remove_pair),
                                  ("/list/new", add_word),
                                  ("/list/delete", remove_word)):
                if path == route:
                    # Accounts and pairs report back on their own page rather
                    # than on a separate error page: you stay where you were.
                    try:
                        message = action(data)
                    except (RecordError, ValueError) as e:
                        message = str(e)
                    return self._go("/accounts?m=" + U(message), message)
            if path == "/report/build":
                what = one(data, "what", "month")
                period = one(data, f"period_{what}")
                if not period:
                    return self._go("/reports")
                reports.build(ROOT, journal(True), period)
                return self._go(f"/report/{U(period)}", "Report built")
            if len(parts) == 2 and parts[0] == "report":
                conclusions = one(data, "conclusions")
                reports.build(ROOT, journal(True), parts[1], conclusions=conclusions)
                return self._go(f"/report/{U(parts[1])}",
                                "Conclusions saved" if conclusions
                                else "Report rebuilt")
        except (RecordError, ValueError) as e:
            return self._send(page("Error", f'<div class="card">'
                                     f'<h2>Not saved</h2><p>{esc(e)}</p>'
                                     f'<p><a href="/">Back to journal</a></p></div>'),
                              400)
        return self._send("no such page", 404)


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    os.makedirs(DRAFTS, exist_ok=True)
    store.make_layout(ROOT)
    server = Server(("127.0.0.1", PORT), Handler)
    print(f"Plainbook: http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
