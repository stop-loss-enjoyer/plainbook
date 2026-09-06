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
                    Playbook, Setup, Rule, PLAYBOOK_STATUSES, LIMITS,
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
    return H.page(title, body, tab, header_right, notice, said_box(),
                  attention=tabs_asking())


def tabs_asking():
    """The tabs drawn amber: the ones that wait for the owner.

    A journal with no playbook yet asks for one, because the rules are what
    the trade form will hold the trades against. A block that has run its
    course will ask for its review here as well, once trades carry a playbook."""
    books = store.all_playbooks(ROOT, [])
    if not books:
        return {"playbooks"}
    j = journal()
    if any(stats.review_due(p, len(playbook_trades(j, p.id))) for p in books):
        return {"playbooks"}
    return set()


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
        wr = (f'WR {s.wr:.0f}%<span class="dates">EV {s.average_r:+.2f}</span>'
              if s.decided else "-")
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
    # the trades that closed in the period, as a report counts a month and a
    # card counts a day; the list below groups by the entry
    inside = [t for t in trades if not t.is_open and t.closed
              and group_key(t.closed, group) == key]
    s = stats.summary(j, inside)
    if not inside:
        return (f'<div class="tile"><div class="name">{name}</div>'
                f'<div class="value muted">-</div>'
                f'<div class="sub">nothing closed yet</div></div>')
    sub = f"{len(inside)} closed"
    if s.decided:
        sub += f" · WR {s.wr:.0f}% · EV {s.average_r:+.2f} R"
    sub += f" · {amount(j, s.sum_pnl, signed=True)}"
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
        # the name is the way into the account: the statistics tab with this
        # account already chosen, its own equity curve and its own figures
        parts.append(
            f'<div class="tile{cls}"><div class="name">'
            f'<a href="/stats?account={U(a)}" title="statistics of this account">'
            f'{esc(account.name or a)}</a></div>'
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


def expectancy(s):
    """The EV of a summary, with the arithmetic behind it in the tooltip.

    The tooltip splits the sum between wins, losses and break-evens, so it
    can be seen what the break-evens cost: the one thing the winrate beside
    it does not show."""
    parts = [f"{word} {total:+.2f}" for n, word, total in
             ((s.wins, "wins", s.sum_r_win), (s.losses, "losses", s.sum_r_lose),
              (s.be, "break-evens", s.sum_r_be)) if n]
    how = (f"{s.sum_r:+.2f} R over {s.trades} closed trades: "
           + ", ".join(parts))
    return (f'<span class="ev {sum_class(s.average_r)}" title="{how}">'
            f'<span class="muted">EV</span> {s.average_r:+.2f} R</span>')


def winrate_tile(name, styles, j, trades):
    """Winrate over a subset of styles. An empty selection gets a dash, not 0%.

    To the right of the winrate stands the EV: what a closed trade brought on
    average, break-evens included. Under the two there are only three figures:
    wins, losses, break-evens. Which is which is told by colour, no labels
    needed."""
    s = stats.summary(j, [t for t in trades if styles is None or t.style in styles])
    if not s.trades:
        return (f'<div class="tile"><div class="name">{esc(name)}</div>'
                f'<div class="value muted">-</div>'
                f'<div class="sub muted">no trades</div></div>')
    sub = (f'<span class="breakdown"><span class="win">{s.wins}</span> / '
           f'<span class="lose">{s.losses}</span> / '
           f'<span class="be">{s.be}</span></span>')
    value = f"{s.wr:.1f}% {expectancy(s)}" if s.decided else "-"
    return (f'<div class="tile"><div class="name">{esc(name)}</div>'
            f'<div class="value">{value}</div>'
            f'<div class="sub">{sub}</div></div>')


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
                    t.playbook, t.playbook_version, t.setup,
                    "" if t.deviations is None else " ".join(map(str, t.deviations)),
                    "" if t.exit_deviations is None else " ".join(map(str, t.exit_deviations)),
                    "; ".join(f"{n}: {why}" for n, why in sorted(t.reasons.items())),
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
             f'<div class="sub">EV {s.average_r:+.2f} R</div></div>'
             '</div>')
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

def ticked_rules(p, t):
    """The rules the trade was held to, each marked met or not, or a line
    saying nobody ticked them."""
    rules = checklist_rules(p, t.setup)
    head = (f'<p class="pb-meta"><a href="/playbook/{U(p.id)}">{esc(playbook_label(p))}</a>'
            f' <b>{esc(p.version)}</b>'
            + (f' · <b>{esc(t.setup)}</b>' if t.setup else "") + '</p>')
    if t.deviations is None:
        entry = ('<p class="muted">The rules were not ticked for this trade: '
                 'it was tied to the playbook later. Edit the trade to '
                 'tick them.</p>')
    elif not rules:
        entry = '<p class="muted">The playbook has no rules to hold it to.</p>'
    else:
        entry = marked_rules(rules, t.deviations, "met", t.reasons)
    return head + entry + management_rules(p, t)


def marked_rules(rules, broken, word, reasons=None):
    """The rules with a tick or a cross each, the reason given under a
    cross, and the count under them."""
    broken = set(broken)
    reasons = reasons or {}
    rows = "".join(
        f'<li class="{"no" if r.number in broken else "ok"}">'
        f'<span class="n">{r.number}</span><span>{esc(r.text)}'
        + (f'<span class="detail">{esc(r.detail)}</span>' if r.detail else "")
        + (f'<span class="reason">{esc(reasons[r.number])}</span>'
           if r.number in broken and r.number in reasons else "")
        + '</span></li>' for r in rules)
    count = len(broken)
    line = (f"every rule {word}" if not count else
            f"{count} rule{'s' if count != 1 else ''} not {word}")
    return f'<ol class="rules ticked">{rows}</ol><p class="caption">{line}</p>'


def management_rules(p, t):
    """The management part of the checklist: a plain list to keep in mind
    while the position is open, ticks and crosses once it is closed."""
    if not p.management:
        return ""
    head = '<h3>Management</h3>'
    if t.is_open:
        return (head + '<p class="caption">Ticked when the trade is closed.</p>'
                + rules_list(p.management))
    if t.exit_deviations is None:
        return head + ('<p class="muted">The management rules were not ticked at '
                       'the close. Edit the trade to tick them.</p>')
    return head + marked_rules(p.management, t.exit_deviations, "held", t.reasons)


def outcome_warning(t):
    """A result that disagrees with the sign of the PnL is nearly always a slip
    of the hand. It is said on the page and not refused by the form, because
    the owner may mean it: a win eaten by commission is one."""
    if t.is_open or t.pnl is None:
        return ""
    if (t.result == "Win" and t.pnl < 0) or (t.result == "Lose" and t.pnl > 0):
        return (f'<div class="notice"><b>{esc(t.result)} with a PnL of '
                f'{H.money(t.pnl, signed=True)}</b>: the result and the money '
                f'disagree. If one of them is a slip, Edit puts it right.</div>')
    return ""


def way_back(report):
    """The button back to the report a trade was opened from. The address is
    taken from the query and trusted only if it names a period, so a link
    cannot send the reader anywhere else."""
    if not report or not reports.is_period(report):
        return ""
    return (f'<a class="btn" href="/report/{U(report)}">'
            f'← {esc(reports.parse_period(report)[2])}</a>')


def trade_page(trade_id, report=""):
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
    if t.playbook:
        words = [esc(playbook_title(t.playbook))]
        if t.playbook_version:
            words.append(esc(t.playbook_version))
        if t.setup:
            words.append(esc(t.setup))
        deviated = (" · rules not ticked" if t.deviations is None else
                    f' · rules not met: {", ".join(str(n) for n in t.deviations)}'
                    if t.deviations else " · every rule met")
        table += (f'<tr><td class="muted">playbook</td><td>'
                  f'<a href="/playbook/{U(t.playbook)}">{" · ".join(words)}</a>'
                  f'{deviated}</td></tr>')
    if t.note:
        table += f'<tr><td class="muted">note</td><td>{esc(t.note)}</td></tr>'
    checklist = ""
    if t.playbook:
        p = playbook_of_trade(t)
        if p is not None:
            checklist = f'<div class="card"><h2>Checklist</h2>{ticked_rules(p, t)}</div>'

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
    buttons = way_back(report) + buttons
    body = (f'<div class="card{" is-open" if t.is_open else ""}">'
            f'<h2>{esc(t.id)}</h2>{outcome_warning(t)}'
            f'<table class="props">{table}</table></div>'
            + checklist
            + (f'<div class="card"><h2>Idea</h2>{idea}</div>' if idea else "")
            + (f'<div class="card"><h2>Exit moment</h2>'
               f'<div class="shots">{exit_shots}</div></div>' if exit_shots else "")
            + (f'<div class="card"><h2>Conclusions</h2>'
               f'<div class="shots">{conclusions}</div>'
               f'</div>' if t.conclusions.strip() else ""))
    return page(t.id, body, "journal", buttons)


# --- statistics ------------------------------------------------------------

def account_tabs(j, q, selected, right=""):
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
    return ('<div class="card-head" style="margin-bottom:10px"><span>'
            + " ".join(parts) + f'</span><span class="right">{right}</span></div>')


def ring(title, rows, steps, kind, size=188):
    """One ring of the R distribution, with its slices written out beside it."""
    total = sum(n for _, n, _ in rows)
    coloured = [(label, n, sum_r, steps[i % len(steps)])
                for i, (label, n, sum_r) in enumerate(rows)]
    if not total:
        return (f'<div class="ring"><h3>{esc(title)}</h3>'
                f'<p class="muted">None yet.</p></div>')
    sum_r = sum(r for _, _, r in rows)
    donut = H.donut_svg([(label, n, colour) for label, n, _, colour in coloured],
                        size=size, thickness=round(size * 30 / 188),
                        middle=str(total), under=f"{sum_r:+.1f} R")
    return (f'<div class="ring"><h3>{esc(title)}</h3>'
            f'<div class="ring-body">{donut}{H.donut_legend(coloured, total)}</div></div>')


def r_rings(j, trades, compact=False):
    """Where the trades landed by the size of R: losses in one ring, wins in
    the other. The share of a bucket is read off the ring directly, instead of
    being measured against the tallest bar of a histogram.

    Compact, the rings shrink and their legends go under them, so the two fit
    beside another picture; the explanation is cut to the one sentence that
    is not said elsewhere on that page."""
    losses, wins, be = stats.r_split(j, trades)
    if not sum(n for _, n, _ in losses) and not sum(n for _, n, _ in wins):
        return ('<div class="card"><h2>R distribution</h2>'
                '<p class="muted">Nothing to plot yet.</p></div>')
    s = stats.summary(j, trades)
    head = (f'{s.trades} closed · {s.wins} won · {s.losses} lost'
            + (f' · {be} break-even' if be else ''))
    size = 150 if compact else 188
    if compact:
        explained = ('Cut by the size of R, the brighter the further from zero. '
                     'Losses of -1 to -1.2 R are the stop as designed; a loss past '
                     '-1.2 R counts as a mistake and is listed under Rules.')
    else:
        explained = ('Each ring is one pile of trades cut by the size '
                     'of R: the further from zero, the brighter the slice. In the middle '
                     'of a ring stands the number of trades in it and their total R. '
                     'Break-even trades are in neither ring; what their commission cost '
                     'is in the EV. On the losses, -1 to -1.2 R is the stop as designed, '
                     'since commission and swap are paid on top of it; a loss past '
                     '-1.2 R means the size was too large.')
    return (f'<div class="card"><h2>R distribution</h2>'
            f'<p class="caption">{esc(head)}</p>'
            f'<div class="rings{" compact" if compact else ""}">'
            f'{ring("Losses", losses, H.LOSS_STEPS, "lose", size)}'
            f'{ring("Wins", wins, H.WIN_STEPS, "win", size)}'
            f'</div>'
            f'<p class="caption">{explained}</p>'
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


def axis_switch(q, current):
    """The two readings of an equity curve: on the calendar, or one step per
    closed trade."""
    parts = []
    for code, name in (("date", "By date"), ("trade", "By trade")):
        params = {k: v[:] for k, v in q.items()}
        params["axis"] = [code]
        href = "/stats?" + urllib.parse.urlencode(params, doseq=True)
        parts.append(f'<a class="{"current" if code == current else ""}" '
                     f'href="{href}">{name}</a>')
    return '<div class="switch">' + "".join(parts) + "</div>"


def equity_chart(j, account, trades, since, axis, height, cid):
    """The curve of one account, from its start or from the month the filter
    begins at, with the base the wash is coloured against."""
    points = stats.equity_events(j, account, trades, since)
    if not points:
        return ""
    base = points[0][1]
    return H.equity_svg([(j.accounts[account].name or account,
                          H.SERIES[sorted(j.accounts).index(account) % len(H.SERIES)],
                          points)],
                        height=height, cid=cid, sign=H.sign(j.currency(account)),
                        base=base, axis=axis,
                        base_word="since the period began" if since else "from start")


# Kept out of the f-strings below: an expression part with a backslash in it
# is a syntax error before Python 3.12, and 3.10 is what the README promises.
NOTHING_TO_PLOT = "<p class='muted'>Nothing to plot yet.</p>"
EMPTY_CELL = "<span class='muted'>-</span>"


def stats_page(q):
    j = journal()
    trades = apply_filters(j, q)
    selected = (q.get("account") or [""])[0]
    axis = (q.get("axis") or ["date"])[0]
    if axis not in ("date", "trade"):
        axis = "date"
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
    legend = ('The dashed line is the balance the curve starts from; the wash '
              'is green above it and red below it. A hollow dot is money that '
              'moved outside a trade, a deposit, a withdrawal, a fee, and the '
              'line steps with it.')
    if selected and selected in j.accounts:
        name = j.accounts[selected].name or selected
        chart = equity_chart(j, selected, trades, since, axis, 300, "acc")
        charts = (f'<div class="card"><h2>Equity: {esc(name)}</h2>'
                  f'{account_tabs(j, q, selected, axis_switch(q, axis))}'
                  f'{chart or NOTHING_TO_PLOT}'
                  f'<p class="caption">{legend}{how}</p></div>')
    else:
        cards = ""
        for i, a in enumerate(sorted(j.accounts)):
            if j.accounts[a].archived:
                continue
            chart = equity_chart(j, a, trades, since, axis, 190, f"acc-{i}")
            if chart:
                cards += f'<h3>{esc(j.accounts[a].name or a)}</h3>{chart}'
        charts = (f'<div class="card"><h2>Equity by account</h2>'
                  f'{account_tabs(j, q, "", axis_switch(q, axis))}'
                  f'{cards or NOTHING_TO_PLOT}'
                  f'<p class="caption">Each account has its own scale, which is '
                  f'why they are drawn separately. Archived accounts are not '
                  f'drawn; their trades stay in the figures below. {legend}{how}'
                  f'</p></div>')

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
                   f'<th class="num">Σ R</th><th class="num">EV</th>'
                   f'<th class="num">Σ {H.sign(j.currency())}</th></tr></thead><tbody>{rows}</tbody>'
                   f'</table>'
                   f'<p class="caption">WR is wins against wins + losses; '
                   f'break-even trades are not in it, their weight is in R. '
                   f'"trades" and EV count every closed trade; EV is Σ R over '
                   f'them, break-evens included.</p>'
                   f'</div>')

    body = (filter_form(j, q).replace('action="/"', 'action="/stats"')
            + by_playbook_card(j, trades)
            + charts
            + r_rings(j, trades) + streaks_card(j, trades) + slices)
    return page("Statistics", body, "stats")


def by_playbook_card(j, trades):
    """The playbooks first: a row each with its setups under it, and the
    trades taken under none last. Nothing when no trade names a playbook."""
    rows = stats.by_playbook(j, trades)
    if not any(pid != stats.NO_PLAYBOOK for pid, _, _ in rows):
        return ""
    names = {b.id: playbook_label(b) for b in store.all_playbooks(ROOT, [])}
    body = ""
    for pid, s, c in rows:
        if pid == stats.NO_PLAYBOOK:
            body += (f'<tr><td class="muted">{stats.NO_PLAYBOOK}</td>{figures_cells(s)}'
                     f'<td class="num">{H.money(s.sum_pnl, signed=True)}</td>'
                     f'<td class="num">-</td><td class="num">-</td></tr>')
            continue
        body += (f'<tr><td><a href="/playbook/{U(pid)}">{esc(names.get(pid, pid))}</a></td>'
                 f'{figures_cells(s)}<td class="num">{H.money(s.sum_pnl, signed=True)}</td>'
                 f'{clean_cell(c)}{held_cell(c)}</tr>')
        own = [t for t in trades if t.playbook == pid]
        setups = stats.by_setup(j, own)
        if len(setups) > 1 or (setups and setups[0][0] != "-"):
            for name, ss, cc in setups:
                body += (f'<tr class="sub"><td>{esc(name)}</td>{figures_cells(ss)}'
                         f'<td class="num">{H.money(ss.sum_pnl, signed=True)}</td>'
                         f'{clean_cell(cc)}{held_cell(cc)}</tr>')
    return (f'<div class="card"><h2>By playbook</h2><table><thead><tr><th></th>'
            f'{figures_head()}<th class="num">Σ {H.sign(j.currency())}</th>'
            f'<th class="num">clean</th><th class="num">held</th></tr></thead>'
            f'<tbody>{body}</tbody></table>'
            f'<p class="caption">Closed trades, by the playbook they were opened '
            f'under, with its setups beneath it. Clean is the share of ticked '
            f'trades that met every rule at the entry; held, the share that kept '
            f'every management rule to the close. A trade tied to a playbook '
            f'later, never ticked, is counted but says nothing about the rules. '
            f'WR and EV as everywhere: WR without break-evens, EV over every '
            f'closed trade.</p></div>')


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
            f'autofocus placeholder="from an idea, a conclusion, a plan, a playbook or a card">'
            f'</div><div><button class="btn primary">Find</button></div></form>')
    if not needle:
        body = (f'<div class="card"><h2>Search</h2>{form}<p class="caption">'
                f'Looks through the text of every trade, plan, playbook and card: '
                f'the ideas, the conclusions, the notes, the analysis, the rules, '
                f'the reviews. '
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
    for b in store.all_playbooks(ROOT, []):
        texts = [b.id, b.name, b.intro, b.review] \
            + [r.text + " " + r.detail for r in b.rules] \
            + [x.name + " " + x.text for x in b.setups] \
            + [text for _, text in b.sections]
        if hit(texts):
            found.append(("playbook", f"/playbook/{U(b.id)}",
                          f"{playbook_label(b)} {b.version}".strip(),
                          _snippet(texts[2:], needle)))
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


def playbook_shots_base(playbook_id):
    return f"/playbook-shot/{U(playbook_id)}"


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


def last_risks(j):
    """The risk of the latest trade of each account, which is what the next
    one most likely carries: a prop account and one's own are run at different
    sizes, and the form should not ask for the figure every time."""
    return {t.account: t.risk for t in j.trades}     # sorted by entry: the last stays


# The risk field follows the account until a figure is typed into it by hand,
# and the risk of the duplicate follows its own account the same way.
RISK_SCRIPT = """
const risks = JSON.parse(document.querySelector('form').dataset.lastRisk || '{}');
function follow_account(selectName, inputName){
  const sel = document.querySelector('[name=' + selectName + ']');
  const input = document.querySelector('[name=' + inputName + ']');
  if (!sel || !input) return;
  input.dataset.auto = '1';
  input.addEventListener('input', () => { delete input.dataset.auto; });
  sel.addEventListener('change', () => {
    if (input.dataset.auto && risks[sel.value] !== undefined) input.value = risks[sel.value];
  });
}
follow_account('account', 'risk');
// the account of the trade itself is not offered a copy: its row goes away
// when it is picked above and comes back when another is
function hide_own_row(){
  const own = document.querySelector('[name=account]').value;
  document.querySelectorAll('.dup-row').forEach(row => {
    row.hidden = row.dataset.account === own;
  });
}
document.querySelector('[name=account]').addEventListener('change', hide_own_row);
hide_own_row();
"""


def duplicate_block(accounts, risks, names):
    """The same position taken on several accounts is entered once. Every
    live account gets a row: tick it and the journal writes a copy there, with
    the idea and the screenshots of the trade and a risk of its own, which is
    the only thing that differs in real life too. The row of the account the
    trade itself is on is hidden by the script and ignored by the server."""
    rows = "".join(
        f'<tr class="dup-row" data-account="{esc(a)}"><td>'
        f'<label style="display:flex;align-items:center;gap:8px;margin:0;'
        f'text-transform:none;letter-spacing:0;font-size:13px;color:inherit">'
        f'<input type="checkbox" name="dup" value="{esc(a)}"> '
        f'{esc(names.get(a) or a)}</label></td>'
        f'<td class="num"><input type="number" name="dup_risk_{esc(a)}" step="any" '
        f'min="0.01" style="width:90px" value="{risks.get(a, 1.0):g}"></td></tr>'
        for a in accounts)
    return f"""
<details class="fold" style="margin-top:14px">
<summary>Duplicate on other accounts
<span class="caption">same idea and screenshots, a risk of its own on each</span></summary>
<table style="width:auto"><thead><tr><th>account</th><th class="num">risk, %</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="caption" style="margin:8px 0 0">Tick an account and the journal writes
a copy of this trade there, with the risk set on its row. The risk starts at
that of your last trade on the account.</p>
</details>"""


def playbook_of_trade(t):
    """The playbook a trade was ticked against: the version it names when
    that version is kept, else the current one. None when it is gone."""
    if not t.playbook or not store.safe_dir_name(t.playbook):
        return None
    try:
        p = store.load_playbook(ROOT, t.playbook)
    except (OSError, ValueError):
        return None
    if t.playbook_version and t.playbook_version != p.version:
        for label in store.playbook_versions(ROOT, t.playbook):
            try:
                kept = store.load_playbook_version(ROOT, t.playbook, label)
            except (OSError, ValueError):
                continue
            if kept.version == t.playbook_version:
                return kept
    return p


def checklist_rules(p, setup):
    """The rules a trade is held to: those of its setup, then the filters. A
    playbook whose setups have no names has one, and every trade takes it."""
    named = any(x.name for x in p.setups)
    rules = []
    for x in p.setups:
        if not named or x.name == setup:
            rules.extend(x.rules)
    return rules + list(p.filters)


def check_row(pid, r, met, field="met", reason=""):
    """One rule of the checklist: the box, the few words, the whole rule
    behind the question mark, and a line for why the rule was not met, shown
    when the box is empty. `field` is `met` at the entry, `held` at the
    close."""
    why = (f'<button type="button" class="why" title="the whole rule" '
           f'onclick="show_why(this)">?</button>'
           f'<div class="detail" hidden>{esc(r.detail)}</div>' if r.detail else "")
    return (f'<div class="check"><input type="checkbox" id="{field}-{esc(pid)}-{r.number}" '
            f'name="{field}_{esc(pid)}" value="{r.number}"{" checked" if met else ""}>'
            f'<label for="{field}-{esc(pid)}-{r.number}"><span class="n">{r.number}</span>'
            f'{esc(r.text)}</label>{why}'
            f'<input type="text" class="why-in" name="why_{esc(pid)}_{r.number}" '
            f'value="{esc(reason)}" placeholder="why not: the fact, not the verdict"'
            f'{" hidden" if met else ""}></div>')


def exit_checklist(t):
    """The management rules of the trade's playbook, ticked at the close, or
    nothing when there is no playbook or it has no such rules. The boxes of a
    closed trade stand as they were ticked."""
    p = playbook_of_trade(t) if t.playbook else None
    if p is None or not p.management:
        return ""
    met = (set() if t.exit_deviations is None else
           {r.number for r in p.management} - set(t.exit_deviations))
    rows = "".join(check_row(p.id, r, r.number in met, "held", t.reasons.get(r.number, ""))
                   for r in p.management)
    note = ("" if t.is_open or t.exit_deviations is not None else
            '<p class="caption">The management rules were not ticked when this '
            'trade was closed. Tick them now and the trade records them; leave '
            'them alone and it stays as it is.</p>')
    return (f'<div class="card" id="exit-checklist"><h2>Management</h2>'
            f'<input type="hidden" name="ticked_exit" value="0" id="ticked-exit">'
            f'<div class="checklist" data-playbook="{esc(p.id)}">'
            f'<h3>{esc(playbook_label(p))} {esc(p.version)}</h3>{note}'
            f'<p class="about caption">How the position was held, whatever the setup.</p>'
            f'{rows}<p class="caption tally"></p></div></div>')


# The close form and the form of a closed trade tick the management rules;
# the count under the list and the touch mark are the same as at the entry.
EXIT_SCRIPT = """
(function(){
  const card = document.getElementById('exit-checklist');
  if (!card) return;
  const block = card.querySelector('.checklist');
  function count(){
    const boxes = [...block.querySelectorAll('input[type=checkbox]')];
    const met = boxes.filter(b => b.checked).length;
    block.querySelector('.tally').textContent = met === boxes.length ? 'every rule held'
      : met + ' of ' + boxes.length + ' rules held, ' + (boxes.length - met) + ' not';
  }
  card.addEventListener('change', e => {
    document.getElementById('ticked-exit').value = '1';
    if (e.target.type === 'checkbox') {
      const why = e.target.closest('.check').querySelector('.why-in');
      why.hidden = e.target.checked;
      if (!why.hidden) why.focus();
    }
    count();
  });
  count();
})();
"""


def checklist_block(p, t=None):
    """The checklist of one playbook in the trade form, drawn hidden and shown
    by the script when the playbook is picked. For a trade being edited the
    boxes stand as they were ticked."""
    own = t is not None and t.playbook == p.id
    met = (set() if not own or t.deviations is None else
           {r.number for r in p.rules} - set(t.deviations))
    named = any(x.name for x in p.setups)
    chosen = t.setup if own else ""
    if named and chosen not in [x.name for x in p.setups]:
        chosen = p.setups[0].name
    setups = ""
    if named:
        radios = "".join(
            f'<label class="radio"><input type="radio" name="setup_{esc(p.id)}" '
            f'value="{esc(x.name)}"{" checked" if x.name == chosen else ""}> '
            f'{esc(x.name)}</label>' for x in p.setups)
        setups = f'<div class="setups">{radios}</div>'
    reasons = t.reasons if own else {}
    groups = ""
    for x in p.setups:
        rows = "".join(check_row(p.id, r, r.number in met, reason=reasons.get(r.number, ""))
                       for r in x.rules)
        shown = not named or x.name == chosen
        groups += (f'<div class="setup-rules" data-setup="{esc(x.name)}"'
                   f'{"" if shown else " hidden"}>{rows}</div>')
    if p.filters:
        rows = "".join(check_row(p.id, r, r.number in met, reason=reasons.get(r.number, ""))
                       for r in p.filters)
        groups += f'<div class="filter-rules"><h3>Filters</h3>{rows}</div>'
    note = ""
    if own and t.deviations is None:
        note = ('<p class="caption">The rules were not ticked for this trade. '
                'Tick them now and the trade records them; leave them alone '
                'and it stays as it is.</p>')
    style = esc(p.styles[0]) if p.styles else ""
    frame = "" if t is not None else frame_html(p)
    return (f'<div class="checklist" data-playbook="{esc(p.id)}" data-style="{style}"'
            f'{"" if own else " hidden"}>'
            f'<h3>{esc(playbook_label(p))} {esc(p.version)}</h3>{frame}{note}{setups}{groups}'
            f'<p class="caption tally"></p></div>')


def frame_html(p):
    """The limits of the playbook against the journal now, in one line above
    the checklist: what the week and the month already hold, what is open,
    and the risk typed in the form against the cap. Red where the trade
    being opened would go past a limit; nothing is refused."""
    rows = stats.frame(journal(), p)
    limits = dict(p.limits)
    cells = ""
    for what, value, limit, reached in rows:
        shown = f"{value:+.2f}" if what == "R this week" else f"{value:.0f}"
        cap = f"{limit:+.0f}" if what == "R this week" else f"{limit:.0f}"
        cells += (f'<span class="{"over" if reached else ""}">{esc(what)} '
                  f'<b>{shown}</b> of {cap}</span>')
    risk = stats._figure(limits, "risk")
    if risk is not None:
        cells += (f'<span data-risk="{risk:g}">risk <b class="risk-now">-</b> '
                  f'of {risk:g}%</span>')
    if not cells:
        return ""
    return f'<div class="frame">{cells}</div>'


def block_notice(p, count):
    """A line on the page when a block has run its course and waits for its
    review; the tab is amber for the same reason."""
    if not stats.review_due(p, count):
        return ""
    number = count // p.block
    return (f'<p class="pb-meta over">block {number} is complete: <b>write its '
            f'review</b> below, then revise the rules under a new number if '
            f'they change.</p>')


def trade_form(t=None, token=""):
    """One form for opening and for editing: the fields are the same."""
    j = journal()
    editing = t is not None
    accounts = [a for a in sorted(j.accounts) if not j.accounts[a].archived or
                (editing and t.account == a)]
    risks = last_risks(j)
    risk = t.risk if editing else risks.get(accounts[0] if accounts else "", 1.0)
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

    # the playbooks offered are the ones in use; the one a trade being edited
    # was ticked against is drawn as it was then, retired or revised since
    books = [b for b in store.all_playbooks(ROOT, []) if b.offered]
    if editing and t.playbook:
        own = playbook_of_trade(t)
        if own is not None:
            books = [own] + [b for b in books if b.id != own.id]
    book_ids = [b.id for b in books]
    book_names = {b.id: f"{playbook_label(b)} {b.version}".strip() for b in books}
    # a playbook deleted since is still the trade's: the menu keeps its id,
    # or the form would post an empty choice and wipe the checklist
    if editing and t.playbook and t.playbook not in book_ids:
        book_ids.append(t.playbook)
        book_names[t.playbook] = f"{t.playbook} {t.playbook_version}".strip()
    checklists = "".join(checklist_block(b, t if editing else None) for b in books)

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
    duplicate = "" if editing else duplicate_block(
        accounts, risks, {a: j.accounts[a].name for a in accounts})
    # For a closed trade the exit and the conclusions are edited here too,
    # or editing the idea would wipe their screenshots: the shots folder is
    # rewritten from whatever the form sent.
    closing = ""
    if editing and not t.is_open:
        closing = f"""<input type="hidden" name="closed" value="1">
<div class="card"><h2>Outcome</h2>
{outcome_fields(t)}</div>
{exit_checklist(t)}
<div class="card"><h2>Exit moment</h2>
{dropzone("exit", "click here and press Ctrl+V",
          [shot_in_zone(shots_base(t.id), s, "have_exit") for s in t.exit_images])}</div>
<div class="card"><h2>Conclusions</h2>
<textarea name="conclusions">{esc(conclusions_text(t.conclusions))}</textarea>
{dropzone("concl", "screenshots for conclusions, Ctrl+V here",
          [shot_in_zone(shots_base(t.id), s, "have_concl")
           for s in conclusion_images(t.conclusions)])}</div>"""
    return f"""<form method="post" action="{action}" data-last-risk="{esc(json.dumps(risks))}">
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
<input type="number" name="risk" step="any" min="0.01" style="width:90px"
 value="{risk:g}" required></div>
<div class="field"><label>entry</label>
<input type="datetime-local" name="entry" value="{entry}"
 onclick="this.showPicker && this.showPicker()"></div>
<div class="field"><label>plan</label>
{select("plan", plan_ids, t.plan if editing else "", empty="-",
        labels=plan_names, style="max-width:270px")}</div>
<div class="field"><label>playbook</label>
{select("playbook", book_ids, t.playbook if editing else "", empty="-",
        labels=book_names)}</div>
</div>
<p class="caption" style="margin:8px 0 0">execution: {checkboxes}</p>
{duplicate}
</div>
<div class="card" id="checklist-card"{"" if editing and t.playbook else " hidden"}>
<h2>Checklist</h2>
<input type="hidden" name="ticked" value="0" id="ticked">
{checklists}
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
init_zones();</script>{"" if editing else f"<script>{RISK_SCRIPT}</script>"}
<script>{CHECKLIST_SCRIPT}</script><script>{EXIT_SCRIPT}</script>"""


# The checklist follows the playbook picked in the form: one block per
# playbook is on the page, the chosen one is shown, and within it the rules
# of the chosen setup. The count under it says how many of the rules in
# sight are ticked, and any touch of the block marks the trade as ticked.
CHECKLIST_SCRIPT = """
function tally(block){
  const boxes = [...block.querySelectorAll('input[type=checkbox]')]
    .filter(b => !b.closest('[hidden]'));
  const met = boxes.filter(b => b.checked).length;
  const out = block.querySelector('.tally');
  if (!boxes.length) { out.textContent = ''; return; }
  out.textContent = met === boxes.length ? 'every rule met'
    : met + ' of ' + boxes.length + ' rules met, ' + (boxes.length - met) + ' not';
}
function show_playbook(){
  const sel = document.querySelector('[name=playbook]');
  const card = document.getElementById('checklist-card');
  card.hidden = !sel.value;
  document.querySelectorAll('#checklist-card .checklist').forEach(block => {
    block.hidden = block.dataset.playbook !== sel.value;
    if (!block.hidden) tally(block);
  });
}
function pick_playbook(){
  show_playbook();
  const block = document.querySelector('#checklist-card .checklist:not([hidden])');
  const style = document.querySelector('[name=style]');
  if (block && block.dataset.style && style &&
      [...style.options].some(o => o.value === block.dataset.style))
    style.value = block.dataset.style;
}
function show_why(button){
  const detail = button.nextElementSibling;
  detail.hidden = !detail.hidden;
}
function follow_risk(){
  const risk = parseFloat(document.querySelector('[name=risk]').value);
  document.querySelectorAll('#checklist-card .checklist:not([hidden]) [data-risk]').forEach(cell => {
    const cap = parseFloat(cell.dataset.risk);
    cell.querySelector('.risk-now').textContent = isNaN(risk) ? '-' : risk + '%';
    cell.classList.toggle('over', !isNaN(risk) && risk > cap);
  });
}
document.querySelector('[name=risk]').addEventListener('input', follow_risk);
document.querySelector('[name=playbook]').addEventListener('change', follow_risk);
follow_risk();
document.querySelector('[name=playbook]').addEventListener('change', pick_playbook);
document.getElementById('checklist-card').addEventListener('change', e => {
  document.getElementById('ticked').value = '1';
  if (e.target.type === 'checkbox') {
    const why = e.target.closest('.check').querySelector('.why-in');
    why.hidden = e.target.checked;
    if (!why.hidden) why.focus();
  }
  const block = e.target.closest('.checklist');
  if (e.target.type === 'radio')
    block.querySelectorAll('.setup-rules').forEach(g => {
      g.hidden = g.dataset.setup !== e.target.value;
    });
  tally(block);
});
show_playbook();
"""


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
{exit_checklist(t)}
<div class="card"><h2>Exit moment</h2>
{dropzone("exit", "click here and press Ctrl+V", exit_shots)}</div>
<div class="card"><h2>Conclusions</h2>
<textarea name="conclusions">{esc(conclusions_text(t.conclusions))}</textarea>
{dropzone("concl", "screenshots for conclusions, Ctrl+V here", concl_shots)}</div>
<div class="actions"><button class="btn primary">Close trade</button>
<a class="btn" href="/trade/{U(t.id)}">Cancel</a></div>
</form>
<script>{FORM_SCRIPT}</script>
<script>document.body.dataset.token = {json.dumps(token)};init_zones();</script>
<script>{EXIT_SCRIPT}</script>"""


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


def apply_playbook(t, data, editing):
    """The playbook, the setup and the rules not met, from the form.

    A new trade records the checklist as it stands, ticked or not: the boxes
    left empty are the deviations, and leaving them all empty is a decision
    too. A trade being edited that was never ticked (tied to the playbook
    later) keeps that state unless the checklist was touched, so that fixing
    a screenshot does not turn "not ticked" into "every rule broken"."""
    pid = one(data, "playbook")
    if not pid:
        t.playbook = t.playbook_version = t.setup = ""
        t.deviations = t.exit_deviations = None
        t.reasons = {}
        return
    same = editing and t.playbook == pid
    if same:
        p = playbook_of_trade(t)
        if p is None:
            return                  # the playbook is gone: the trade keeps its record
    else:
        if not store.safe_dir_name(pid):
            raise RecordError(f"bad playbook {pid!r}")
        try:
            p = store.load_playbook(ROOT, pid)
        except (OSError, ValueError):
            p = None
        if p is None:
            raise RecordError(f"no playbook {pid!r}")
        # another playbook: what was ticked under the old one says nothing
        # about this one, at the entry or at the close
        t.exit_deviations = None
        t.reasons = {}
    t.playbook = pid
    t.setup = one(data, f"setup_{pid}")
    names = [x.name for x in p.setups if x.name]
    if names and t.setup not in names:
        raise RecordError("pick the setup the trade is taken under: " + ", ".join(names))
    if same and t.deviations is None and one(data, "ticked") != "1":
        return
    # the ticks are read against the rules the form drew, so the trade names
    # that version from now on: an attached trade ticked after a revision
    # moves to the version it was actually held to
    t.playbook_version = p.version
    met = set()
    for x in data.get(f"met_{pid}", []):
        try:
            met.add(int(x))
        except ValueError:
            pass
    t.deviations = [r.number for r in checklist_rules(p, t.setup) if r.number not in met]
    keep_reasons(t, data, pid, t.deviations, {r.number for r in p.management})


def keep_reasons(t, data, pid, broken, others):
    """The reasons typed under the rules not met: rewritten for the list
    just read, kept for the other list (`others` are its rule numbers)."""
    kept = {n: why for n, why in t.reasons.items() if n in others}
    for n in broken:
        why = " ".join(one(data, f"why_{pid}_{n}").split())
        if why:
            kept[n] = why
    t.reasons = kept


def apply_management(t, data, editing):
    """The management rules ticked at the close. A trade closed with no box
    ticked records every rule as not held, the same as at the entry; a
    closed trade being edited keeps "not ticked" unless the list was
    touched."""
    if not t.playbook:
        t.exit_deviations = None
        return
    p = playbook_of_trade(t)
    if p is None:
        return                      # the playbook is gone: the trade keeps its record
    if not p.management:
        t.exit_deviations = None
        return
    if editing and t.exit_deviations is None and one(data, "ticked_exit") != "1":
        return
    held = set()
    for x in data.get(f"held_{p.id}", []):
        try:
            held.add(int(x))
        except ValueError:
            pass
    t.exit_deviations = [r.number for r in p.management if r.number not in held]
    keep_reasons(t, data, p.id, t.exit_deviations,
                 {r.number for r in checklist_rules(p, t.setup)})


def apply_fields(t, data, editing=False):
    entry = datetime.strptime(one(data, "entry"), "%Y-%m-%dT%H:%M")
    t.account = one(data, "account")
    # EURUSD and eurusd are one pair, so the filters and the tables see one
    t.pair = one(data, "pair").upper() or PAIR_NOT_SET
    t.direction = one(data, "direction")
    t.style = one(data, "style")
    t.entry_tf = one(data, "entry_tf")
    t.execution = data.get("execution", [])
    t.plan = one(data, "plan")
    apply_playbook(t, data, editing)
    if t.account not in journal(True).accounts:
        raise RecordError(f"no account {t.account!r}")
    risk = one(data, "risk")
    if not risk:
        raise RecordError("the risk is missing")
    t.risk = float(risk.replace(",", "."))
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
    """One trade, and a copy on every other account that was ticked.

    The copies are written before the drafts are swept, so every trade gets
    the screenshots that were pasted into the form. A tick on the account of
    the trade itself is ignored: that trade is already being written."""
    token = one(data, "token")
    j = journal()
    twins = []
    for a in data.get("dup", []):
        if a == one(data, "account") or a in twins:
            continue
        if a not in j.accounts:
            raise RecordError(f"no account {a} to duplicate on")
        twins.append(a)
    t = build_trade(data, token)
    for a in twins:
        risk = one(data, f"dup_risk_{a}")
        build_trade(data, token, account=a,
                    risk=float(risk.replace(",", ".")) if risk else t.risk)
    drop_draft(token)
    drop_cache()
    return t


def edit_trade(t, data):
    token = one(data, "token")
    apply_fields(t, data, editing=True)
    editing_close = one(data, "closed") == "1"
    if editing_close:
        apply_outcome(t, data)
        apply_management(t, data, editing=True)
    # checked before anything on the disk moves: a folder renamed for a record
    # that is then refused would be a folder whose file names another id
    t.check()
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
    if editing_close:
        zones["exit"] = zone_sources(data, "exit", folder, token)
        zones["concl"] = zone_sources(data, "concl", folder, token)
    else:
        own = os.path.join(folder, "{}")
        zones["exit"] = [own.format(s) for s in t.exit_images]
        zones["concl"] = [own.format(s)
                          for s in conclusion_images(t.conclusions)]
    t.idea = kept
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
    apply_management(t, data, editing=False)
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


# --- playbooks -------------------------------------------------------------
# The standing rules of a way of trading, as a record. Written once, revised
# by version, and picked in the form of a trade later on.

def playbook_label(p):
    return p.name or p.id


def playbook_title(playbook_id):
    """The name of a playbook for a link. One deleted later leaves its id."""
    if not store.safe_dir_name(playbook_id):
        return playbook_id
    try:
        return playbook_label(store.load_playbook(ROOT, playbook_id))
    except (OSError, ValueError):
        return playbook_id


def status_chip(p):
    return f'<span class="chip {esc(p.status)}">{esc(p.status)}</span>'


def playbook_meta(p):
    """Version, first counted day and styles in one dim line."""
    bits = []
    if p.version:
        bits.append(f"version <b>{esc(p.version)}</b>")
    if p.since:
        bits.append(f"counts from <b>{p.since:%d.%m.%Y}</b>")
    if p.styles:
        bits.append("styles <b>" + esc(", ".join(p.styles)) + "</b>")
    return f'<p class="pb-meta">{" · ".join(bits)}</p>' if bits else ""


def block_bar(p, done):
    """How far the current block of trades has come: `done` of `p.block`.
    Nothing when the playbook has no block."""
    if not p.block:
        return ""
    within = done % p.block if done < p.block or done % p.block else p.block
    number = done // p.block + (1 if done % p.block or not done else 0)
    width = 100 * within / p.block
    total = (f' · <b>{done}</b> trades in all, next review at <b>{number * p.block}</b>'
             if done > p.block else "")
    return (f'<p class="pb-meta">block {number}: <b>{within} / {p.block}</b> trades{total}</p>'
            f'<div class="block-bar"><i style="width:{width:.0f}%"></i></div>')


def rules_list(rules):
    return ('<ol class="rules">' + "".join(
        f'<li><span class="n">{r.number}</span><span>{esc(r.text)}'
        + (f'<span class="detail">{esc(r.detail)}</span>' if r.detail else "")
        + '</span></li>' for r in rules) + '</ol>')


def playbook_rules(p):
    """The setups and the filters as they will be ticked in the trade form."""
    out = ""
    for s in p.setups:
        about = (f'<p class="about">{inline(" ".join(s.text.split()))}</p>'
                 if s.text.strip() else "")
        out += (f'<div class="setup">{f"<h3>{esc(s.name)}</h3>" if s.name else ""}'
                f'{about}{rules_list(s.rules)}</div>')
    if p.filters:
        out += (f'<div class="setup"><h3>Filters</h3>'
                f'<p class="about">Checked whatever the setup.</p>'
                f'{rules_list(p.filters)}</div>')
    if p.management:
        out += (f'<div class="setup"><h3>Management</h3>'
                f'<p class="about">Checked when the trade is closed.</p>'
                f'{rules_list(p.management)}</div>')
    return out or '<p class="muted">No rules written yet.</p>'


def paragraphs(text):
    """Prose from a file, where a line break is just where the line was
    wrapped: paragraphs are cut at blank lines, a `### ` line is a heading,
    lines starting with `- ` make a list."""
    out = []
    for chunk in re.split(r"\n\s*\n", text.strip()):
        lines = [x.strip() for x in chunk.split("\n") if x.strip()]
        if not lines:
            continue
        if all(x.startswith(("- ", "* ")) for x in lines):
            out.append("<ul>" + "".join(f"<li>{inline(x[2:])}</li>" for x in lines) + "</ul>")
        elif lines[0].startswith("### ") and len(lines) == 1:
            out.append(f"<h3>{esc(lines[0][4:])}</h3>")
        else:
            out.append(f"<p>{inline(' '.join(lines))}</p>")
    return "".join(out)


def playbooks_page():
    problems = []
    books = store.all_playbooks(ROOT, problems)
    right = '<a class="btn primary" href="/playbook/new">+ Playbook</a>'
    if not books:
        body = ('<div class="card"><h2>Playbooks</h2>'
                '<p class="pb-text">A playbook is one way of trading written '
                'down as rules: what has to be true before a trade is opened. '
                'When a trade is opened, the playbook is picked in its form and '
                'the rules are ticked one by one. A rule left unticked stays '
                'with the trade, and the statistics then say what every rule '
                'is worth in R.</p>'
                '<p class="muted">No playbooks yet. The button above writes '
                'the first one: the rules, a line each.</p></div>')
        return page("Playbooks", body, "playbooks", right, problems)
    j = journal()
    rows = ""
    for p in books:
        href = f"/playbook/{U(p.id)}"
        trades = playbook_trades(j, p.id)
        s = stats.summary(j, trades)
        cells = [(esc(playbook_label(p)), ""), (status_chip(p), ""),
                 (esc(p.version) or "-", "num"),
                 (esc(", ".join(p.styles)) or "-", ""),
                 (str(len(p.rules)), "num"),
                 (str(len(trades)), "num"),
                 ((f"{len(trades)} / {p.block}"
                   + (' <span class="over">review due</span>'
                      if stats.review_due(p, len(trades)) else ""))
                  if p.block else "-", "num"),
                 ("-" if not s.trades else f"{s.sum_r:+.2f}",
                  f"num {sum_class(s.sum_r)}"),
                 ("-" if not s.trades else f"{s.average_r:+.2f}", "num"),
                 (clean_cell(stats.compliance(trades))[len('<td class="num">'):-5], "num"),
                 (f"{p.since:%d.%m.%Y}" if p.since else "-", "")]
        rows += ("<tr>" + "".join(link_cell(href, inner, cls)
                                  for inner, cls in cells) + "</tr>")
    body = (f'<div class="card"><h2>Playbooks</h2>'
            f'<table><thead><tr><th>name</th><th>status</th>'
            f'<th class="num">version</th><th>styles</th><th class="num">rules</th>'
            f'<th class="num">trades</th><th class="num">block</th>'
            f'<th class="num">Σ R</th><th class="num">EV</th><th class="num">clean</th>'
            f'<th>counts from</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
            f'<p class="caption">A playbook is picked in the form of a trade, '
            f'and its rules are ticked there. A rule left unticked stays with '
            f'the trade, so that the statistics can say what the rule is worth.'
            f'</p></div>')
    return page("Playbooks", body, "playbooks", right, problems)


def playbook_trades(j, playbook_id):
    """Every trade opened under the playbook, whatever the version."""
    return [t for t in j.trades if t.playbook == playbook_id]


def playbook_trades_card(j, trades):
    if not trades:
        return ('<div class="card"><h2>Trades of this playbook</h2>'
                '<p class="muted">No trade has been opened under it yet. The '
                'playbook is picked in the form of a trade.</p></div>')
    rows = "".join(trade_row(j, t) for t in
                   sorted(trades, key=lambda t: t.opened, reverse=True))
    return (f'<div class="card"><h2>Trades of this playbook</h2>'
            f'<table><thead><tr><th>date</th><th>account</th><th>pair</th>'
            f'<th>direction</th><th>style</th><th>TF</th>'
            f'<th class="num">risk</th><th>result</th>'
            f'<th class="num">PnL {H.sign(j.currency())}</th><th class="num">R</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
            f'<p class="caption">{esc(plan_result(j, trades))}</p></div>')


def figures_head():
    return ('<th class="num">trades</th><th class="num">WR</th>'
            '<th class="num">Σ R</th><th class="num">EV</th>')


def figures_cells(s):
    return (f'<td class="num">{s.trades}</td>'
            f'<td class="num">{s.wr:.1f}%</td>'
            f'<td class="num {sum_class(s.sum_r)}">{s.sum_r:+.2f}</td>'
            f'<td class="num">{s.average_r:+.2f}</td>')


def clean_cell(c):
    """The share of ticked trades that met every rule, '-' when none was
    ticked, and the count of unticked ones in grey after it."""
    share = "-" if c.clean_share is None else f"{c.clean_share:.0f}%"
    tail = (f' <span class="muted">({c.unticked} not ticked)</span>'
            if c.unticked else "")
    return f'<td class="num">{share}{tail}</td>'


def held_cell(c):
    """The share of closed trades that held every management rule."""
    share = "-" if c.held_share is None else f"{c.held_share:.0f}%"
    tail = (f' <span class="muted">({c.held_unticked} not ticked)</span>'
            if c.held_unticked and c.held_ticked else "")
    return f'<td class="num">{share}{tail}</td>'


def compliance_line(c):
    """One line in words: how many went through the checklists and how."""
    bits = []
    if c.ticked:
        bits.append(f"at the entry <b>{c.clean}</b> met every rule, <b>{c.deviated}</b> broke one or more")
    if c.unticked:
        bits.append(f"<b>{c.unticked}</b> not ticked")
    if c.held_ticked:
        bits.append(f"held to the end <b>{c.held}</b>, broke a management rule <b>{c.held_broken}</b>")
    return f'<p class="pb-meta">{" · ".join(bits)}</p>' if bits else ""


def setups_card(j, p, trades):
    rows = stats.by_setup(j, trades)
    if len(rows) < 2 and not (rows and rows[0][0] != "-"):
        return ""
    body = "".join(
        f'<tr><td>{esc(name)}</td>{figures_cells(s)}{clean_cell(c)}{held_cell(c)}</tr>'
        for name, s, c in rows)
    return (f'<div class="card"><h2>By setup</h2><table><thead><tr><th></th>'
            f'{figures_head()}<th class="num">clean</th><th class="num">held</th>'
            f'</tr></thead><tbody>{body}</tbody></table>'
            f'<p class="caption">Closed trades. Clean is the share of ticked '
            f'trades that met every rule at the entry; held, the share that '
            f'kept every management rule to the close.</p></div>')


def rule_costs_card(j, p, trades):
    """What each rule cost, against the trades that met every rule."""
    same = [t for t in trades if t.playbook_version == p.version]
    rows, clean = stats.rule_costs(j, same, p.rules)
    if not any(n for _, n, _ in rows) and not clean.trades:
        return ""
    body = "".join(
        f'<tr><td><span class="n muted">{r.number}</span> {esc(r.text)}</td>'
        f'<td class="num">{n}</td>'
        f'<td class="num {sum_class(s.sum_r)}">{s.sum_r:+.2f}</td>'
        f'<td class="num">{s.average_r:+.2f}</td></tr>'
        for r, n, s in rows if n)
    versus = (f'<tr class="total"><td>kept every rule</td>'
              f'<td class="num">{clean.trades}</td>'
              f'<td class="num {sum_class(clean.sum_r)}">{clean.sum_r:+.2f}</td>'
              f'<td class="num">{clean.average_r:+.2f}</td></tr>')
    given = ""
    for r in p.rules:
        told = [(t, t.reasons[r.number]) for t in same if r.number in t.reasons]
        if told:
            items = "".join(
                f'<li><a href="/trade/{U(t.id)}">{t.opened:%d.%m.%Y}</a> {esc(why)}</li>'
                for t, why in sorted(told, key=lambda x: x[0].opened, reverse=True))
            given += (f'<div class="reasons"><b>{r.number}</b> {esc(r.text)}'
                      f'<ul>{items}</ul></div>')
    if given:
        given = (f'<details class="fold" style="margin-top:12px"><summary>Reasons given '
                 f'<span class="caption">what stood behind each rule not met, in the '
                 f'trader\'s words</span></summary>{given}</details>')
    return (f'<div class="card"><h2>What a rule costs</h2><table><thead><tr>'
            f'<th>rule not met</th><th class="num">trades</th>'
            f'<th class="num">Σ R</th><th class="num">EV</th></tr></thead>'
            f'<tbody>{body}{versus}</tbody></table>{given}'
            f'<p class="caption">Ticked trades of version {esc(p.version)}, the '
            f'entry rules and the management rules in one table. A trade that '
            f'broke several rules stands in each of their rows; Σ R and EV are '
            f'over the closed ones. The last row is the measure: what the trades '
            f'that kept every rule, at the entry and to the close, brought.</p></div>')


def playbook_page(playbook_id):
    if not store.safe_dir_name(playbook_id):
        return None
    try:
        p = store.load_playbook(ROOT, playbook_id).check()
    except (OSError, RecordError):
        return None
    j = journal()
    trades = playbook_trades(j, p.id)
    intro = paragraphs(p.intro)
    s = stats.summary(j, trades)
    figures = ""
    if s.trades:
        figures = (f'<p class="pb-meta">closed <b>{s.trades}</b> · WR <b>{s.wr:.0f}%</b>'
                   f' · Σ R <b class="{sum_class(s.sum_r)}">{s.sum_r:+.2f}</b>'
                   f' · EV <b>{s.average_r:+.2f}</b> · {amount(j, s.sum_pnl, signed=True)}</p>')
    head = (f'<div class="card"><div class="card-head">'
            f'<h1 class="pb-name">{esc(playbook_label(p))}</h1>{status_chip(p)}'
            f'</div>{playbook_meta(p)}{block_bar(p, len(trades))}'
            f'{block_notice(p, len(trades))}{figures}'
            f'{compliance_line(stats.compliance(trades))}'
            + (f'<div class="pb-intro">{intro}</div>' if intro else "")
            + '</div>')
    rules = f'<div class="card"><h2>Rules</h2>{playbook_rules(p)}</div>'
    limits = ""
    if p.limits:
        items = "".join(f'<div>{esc(label)}<b>{esc(value)}</b></div>'
                        for label, value in limit_lines(p))
        limits = f'<div class="card"><h2>Limits</h2><div class="limits">{items}</div></div>'
    rest = "".join(
        f'<div class="card"><h2>{esc(heading)}</h2>'
        f'<div class="pb-text">{paragraphs(text)}</div></div>'
        for heading, text in p.sections)
    base = playbook_shots_base(p.id)
    token = new_token()
    entries = (f'<div class="shots">{with_shots(p.review, base)}</div>'
               if p.review.strip() else
               '<p class="muted">No review yet. A block is reviewed here: what '
               'the trades said, what changes for the next block, with the '
               'charts that show it.</p>')
    review_form = (f'<form method="post" action="/playbook/{U(p.id)}/review" '
                   f'style="margin-top:12px">'
                   f'<input type="hidden" name="token" value="{esc(token)}">'
                   f'<label>add a review</label>'
                   f'<textarea name="review" placeholder="the block in a few '
                   f'lines: what held, what leaked, what the next version changes" '
                   f'required></textarea>'
                   f'{dropzone("review", "click here and press Ctrl+V to paste a screenshot")}'
                   f'<div class="actions"><button class="btn">Add</button></div>'
                   f'</form>')
    review = (f'<div class="card"><h2>Review</h2>{entries}{review_form}</div>'
              f'<script>{FORM_SCRIPT}</script>'
              f'<script>document.body.dataset.token = {json.dumps(token)};'
              f'init_zones();</script>')
    kept = store.playbook_versions(ROOT, p.id)
    versions = ""
    if kept:
        items = "".join(
            f'<li><a href="/playbook/{U(p.id)}/version/{U(v)}">{esc(v)}</a></li>'
            for v in kept)
        versions = (f'<div class="card"><h2>Earlier versions</h2>'
                    f'<ul class="versions">{items}</ul>'
                    f'<p class="caption">The rules as they were before each '
                    f'revision. A trade opened under one of them is shown these, '
                    f'not the current ones.</p></div>')
    buttons = (f'<a class="btn" href="/playbook/{U(p.id)}/edit">Edit</a>'
               f'<form method="post" action="/playbook/{U(p.id)}/delete" '
               f'style="display:inline" onsubmit="return confirm('
               f'\'Delete playbook {esc(p.id)}? The folder moves to .trash.\')">'
               f'<button class="btn danger">Delete</button></form>')
    return page(playbook_label(p),
                head + setups_card(j, p, trades) + rule_costs_card(j, p, trades)
                + rules + limits + rest + playbook_trades_card(j, trades)
                + review + versions,
                "playbooks", buttons)


def playbook_version_page(playbook_id, label):
    """One frozen version, read only."""
    if not (store.safe_dir_name(playbook_id) and store.safe_dir_name(label)):
        return None
    try:
        p = store.load_playbook_version(ROOT, playbook_id, label).check()
    except (OSError, RecordError):
        return None
    head = (f'<div class="card"><div class="card-head">'
            f'<h1 class="pb-name">{esc(playbook_label(p))}</h1>'
            f'<span class="chip retired">version {esc(p.version or label)}, kept</span>'
            f'</div>{playbook_meta(p)}'
            f'<p class="caption">An earlier version. '
            f'<a href="/playbook/{U(playbook_id)}">The current one</a> is what '
            f'the trade form offers.</p></div>')
    rules = f'<div class="card"><h2>Rules</h2>{playbook_rules(p)}</div>'
    return page(f"{playbook_label(p)} {label}", head + rules, "playbooks")


# --- the playbook form -------------------------------------------------------
# Rules are typed a line each into one field per setup; that is faster than a
# field per rule, and it is the shape the file has anyway.

def lines_of(text):
    """A field of lines -> the lines in it, the empty ones left out."""
    return [line.strip() for line in text.replace("\r", "").split("\n")
            if line.strip()]


def rule_pairs(data, name):
    """The rule rows of a field -> [(few words, whole rule)]. A box or a dash
    in front is allowed, so that a rule pasted from the file reads the same;
    a line break inside becomes a space, a rule is one line in the file. A
    row with the words empty and the rule written takes the rule as its
    words; a row with nothing is dropped."""
    shorts = data.get(name, [])
    details = data.get(name + "_detail", [])
    details += [""] * (len(shorts) - len(details))
    out = []
    for short, detail in zip(shorts, details):
        short = short.replace("**", "")     # the file marks the few words in bold
        short = " ".join(re.sub(r"^\s*[-*]?\s*(\[[ xX]?\])?\s*", "", short).split())
        detail = " ".join(detail.split())
        if not short and detail:
            short, detail = detail, ""
        if short:
            out.append((short, detail))
    return out


def rule_rows(name, rules):
    """A row per rule, numbered in the margin as on the page: the few words
    the checklist will show, then the whole rule. The numbers are put right
    by the script, through the whole form, once a rule is added or taken
    away. A row with nothing in it is dropped when the form is read."""
    rows = "".join(
        f'<div class="rule-row"><span class="n"></span>'
        f'<textarea name="{name}" rows="1" class="short" placeholder="in a few words">{esc(r.text)}</textarea>'
        f'<textarea name="{name}_detail" rows="1" placeholder="the whole rule, if the words need it">{esc(r.detail)}</textarea>'
        f'<button type="button" class="x" title="remove the rule" '
        f'onclick="drop_rule(this)">&times;</button></div>'
        for r in (rules or [Rule(0, "")]))
    return (f'<div class="rules-edit" data-name="{name}">{rows}'
            f'<button type="button" class="btn small" onclick="add_rule(this)">+ rule</button>'
            f'</div>')


def setup_form_block(n, name="", about="", rules=()):
    return f"""<div class="setup-form" data-n="{n}">
<div class="fields">
<div class="field"><label>setup</label>
<input type="text" name="setup_name_{n}" value="{esc(name)}" placeholder="A: reaction at a higher level" style="width:300px"></div>
<div class="field" style="flex:1;min-width:260px"><label>what it is</label>
<input type="text" name="setup_about_{n}" value="{esc(about)}" placeholder="a line on the idea behind it" style="width:100%"></div>
</div>
<label>rules: a few words for the checklist, then the whole rule</label>
{rule_rows(f"setup_rule_{n}", list(rules))}
</div>"""


def limit_row(what="", value=""):
    """One limit of the form: its kind from the list, or "other" with a name
    of its own, and the value."""
    kinds = {key for key, _, _ in LIMITS}
    other = bool(what) and what not in kinds
    options = "".join(
        f'<option value="{esc(key)}"{" selected" if key == what else ""}>{esc(label)}'
        f'{", " + esc(unit) if unit else ""}</option>' for key, label, unit in LIMITS)
    options += f'<option value="other"{" selected" if other else ""}>other</option>'
    return (f'<div class="limit-row">'
            f'<select name="limit_kind" onchange="pick_limit_kind(this)">{options}</select>'
            f'<input type="text" name="limit_name" value="{esc(what if other else "")}" '
            f'placeholder="what is capped"{"" if other else " hidden"}>'
            f'<input type="text" name="limit_value" value="{esc(value)}" '
            f'placeholder="value" style="width:110px">'
            f'<button type="button" class="x" title="remove the limit" '
            f'onclick="drop_limit(this)">&times;</button></div>')


def limit_rows(p):
    rows = "".join(limit_row(what, value) for what, value in p.limits)
    return (f'<div class="limits-edit" id="limits">{rows}'
            f'<template id="limit-template">{limit_row()}</template>'
            f'<button type="button" class="btn small" onclick="add_limit()">+ limit</button>'
            f'</div>')


def limit_lines(p):
    """The limits for the page: a known one with its label and unit, another
    as written."""
    names = {key: (label, unit) for key, label, unit in LIMITS}
    out = []
    for what, value in p.limits:
        if what in names:
            label, unit = names[what]
            out.append((label, f"{value} {unit}".strip()))
        else:
            out.append((what, value))
    return out


def notes_text(p):
    """The free sections back into one field: a `## heading` line starts each."""
    if len(p.sections) == 1 and p.sections[0][0] == "Notes":
        return p.sections[0][1]
    return "\n\n".join(f"## {h}\n\n{t}" for h, t in p.sections)


def playbook_form(p=None, token="", notice=""):
    editing = p is not None and p.id
    p = p or Playbook(id="", status="experiment", version="1.0", since=datetime.now())
    styles = "".join(
        f'<label class="caption" style="display:inline-block;margin-right:10px">'
        f'<input type="checkbox" name="styles" value="{esc(v)}"'
        f'{" checked" if v in p.styles else ""}> {esc(v)}</label>'
        for v in offered("styles", *p.styles))
    setups = "".join(
        setup_form_block(i, x.name, x.text, x.rules)
        for i, x in enumerate(p.setups, 1)) or setup_form_block(1)
    action = f"/playbook/{U(p.id)}/edit" if editing else "/playbook/new"
    warn = f'<div class="notice">{notice}</div>' if notice else ""
    return f"""{warn}<form method="post" action="{action}">
<input type="hidden" name="token" value="{esc(token)}">
<input type="hidden" name="setups" value="{max(1, len(p.setups))}" id="setups-count">
<div class="card"><h2>{"Edit playbook" if editing else "New playbook"}</h2>
<div class="fields">
<div class="field"><label>name</label>
<input type="text" name="name" value="{esc(p.name)}" placeholder="Pullback" style="width:200px" required></div>
<div class="field"><label>status</label>
{select("status", PLAYBOOK_STATUSES, p.status)}</div>
<div class="field"><label>version</label>
<input type="text" name="version" value="{esc(p.version)}" style="width:70px" required></div>
<div class="field"><label>counts from</label>
<input type="date" name="since" value="{f"{p.since:%Y-%m-%d}" if p.since else ""}"
 onclick="this.showPicker && this.showPicker()"></div>
<div class="field"><label>block, trades</label>
<input type="number" name="block" min="1" step="1" style="width:80px"
 value="{p.block or ""}" placeholder="40"></div>
</div>
<p class="caption" style="margin:8px 0 0">styles: {styles}</p>
<p class="caption">Experiment while the sample is being built, active once the
rules are trusted, retired when they are not offered any more. The block is
how many trades make one review; leave it empty if the rules are not reviewed
by blocks.</p>
<label style="margin-top:12px">what the playbook is</label>
<textarea name="intro" placeholder="a few lines: the idea behind the rules, and when they were written">{esc(p.intro)}</textarea>
</div>
<div class="card"><h2>Setups</h2>
<p class="caption" style="margin:0 0 12px">One way of entering per setup, with the
rules that have to be true for it. A playbook with one way of entering leaves
the setup name empty.</p>
<div id="setups">{setups}</div>
<template id="setup-template">{setup_form_block("__N__")}</template>
<p><button type="button" class="btn" onclick="add_setup()">+ setup</button></p>
</div>
<div class="card"><h2>Filters</h2>
<p class="caption" style="margin:0 0 8px">Checked before every trade, whatever the setup.</p>
{rule_rows("filter", p.filters)}
</div>
<div class="card"><h2>Management</h2>
<p class="caption" style="margin:0 0 8px">How the position is held: ticked when
the trade is closed, not when it is opened. Three to five is a list that gets
ticked; ten is one that gets skipped.</p>
{rule_rows("management", p.management)}
</div>
<div class="card"><h2>Limits</h2>
<p class="caption" style="margin:0 0 8px">What the playbook caps. A value is a
plain number, the unit is in the label, the loss per week is positive. The
first five kinds are counted above the checklist of a new trade; the longest
hold, the least RR and "other" are shown as written.</p>
{limit_rows(p)}
</div>
<div class="card"><h2>Notes</h2>
<textarea name="notes" placeholder="anything else: the markets, the math, what is still being decided">{esc(notes_text(p))}</textarea>
<p class="caption">Free text. A line starting with <code>## </code> begins a
section of its own on the page.</p>
</div>
<div class="actions"><button class="btn primary">{"Save" if editing else "Write the playbook"}</button>
<a class="btn" href="{f"/playbook/{U(p.id)}" if editing else "/playbooks"}">Cancel</a></div>
</form>
<script>{PLAYBOOK_FORM_SCRIPT}</script>"""


# The rule fields: one field per rule that grows with its text, Enter adds
# the next one, the numbers in the margin run through the whole form the way
# they run through the page.
PLAYBOOK_FORM_SCRIPT = """
function grow(t){ t.style.height = 'auto'; t.style.height = t.scrollHeight + 'px'; }
function renumber(){
  let n = 1;
  document.querySelectorAll('.rule-row .n').forEach(el => { el.textContent = n++; });
}
function rule_row(name){
  const div = document.createElement('div');
  div.className = 'rule-row';
  div.innerHTML = '<span class="n"></span>'
    + '<textarea name="' + name + '" rows="1" class="short" placeholder="in a few words"></textarea>'
    + '<textarea name="' + name + '_detail" rows="1" placeholder="the whole rule, if the words need it"></textarea>'
    + '<button type="button" class="x" title="remove the rule" onclick="drop_rule(this)">&times;</button>';
  return div;
}
function add_rule(button, after){
  const box = button.closest('.rules-edit');
  const row = rule_row(box.dataset.name);
  if (after) after.insertAdjacentElement('afterend', row);
  else box.insertBefore(row, button);
  renumber();
  row.querySelector('textarea').focus();
}
function drop_rule(x){
  const box = x.closest('.rules-edit'), row = x.closest('.rule-row');
  if (box.querySelectorAll('.rule-row').length === 1)
    row.querySelectorAll('textarea').forEach(t => { t.value = ''; grow(t); });
  else row.remove();
  renumber();
}
function pick_limit_kind(sel){
  const name = sel.parentElement.querySelector('[name="limit_name"]');
  name.hidden = sel.value !== 'other';
  if (!name.hidden) name.focus();
}
function add_limit(){
  const box = document.getElementById('limits');
  box.insertBefore(document.getElementById('limit-template').content.cloneNode(true),
                   box.querySelector('.btn'));
  const rows = box.querySelectorAll('.limit-row');
  rows[rows.length - 1].querySelector('select').focus();
}
function drop_limit(x){ x.closest('.limit-row').remove(); }
function add_setup(){
  const count = document.getElementById('setups-count');
  const n = parseInt(count.value, 10) + 1;
  count.value = n;
  const html = document.getElementById('setup-template').innerHTML.replaceAll('__N__', n);
  document.getElementById('setups').insertAdjacentHTML('beforeend', html);
  renumber();
  document.querySelector(`[name="setup_name_${n}"]`).focus();
}
document.addEventListener('input', e => {
  if (e.target.matches('.rule-row textarea')) grow(e.target);
});
document.addEventListener('keydown', e => {
  if (e.key !== 'Enter' || !e.target.matches('.rule-row textarea')) return;
  e.preventDefault();
  const row = e.target.closest('.rule-row');
  add_rule(row.closest('.rules-edit').querySelector('.btn'), row);
});
renumber();
document.querySelectorAll('.rule-row textarea').forEach(grow);
"""


class RulesChanged(ValueError):
    """The rules were rewritten under the same version number."""


def playbook_from_form(data, p):
    """The form -> the playbook, rules numbered afresh."""
    p.name = one(data, "name").strip()
    p.styles = [v for v in data.get("styles", []) if v]
    p.status = one(data, "status") or "active"
    p.version = one(data, "version").strip()
    since = one(data, "since")
    p.since = datetime.strptime(since, "%Y-%m-%d") if since else None
    block = one(data, "block").strip()
    p.block = int(block) if block else None
    p.intro = one(data, "intro").replace("\r", "").strip()
    no_reserved_heading(p.intro, "intro")
    p.setups, number = [], 1
    for n in range(1, int(one(data, "setups", "1") or 1) + 1):
        name = one(data, f"setup_name_{n}").strip()
        about = one(data, f"setup_about_{n}").strip()
        pairs = rule_pairs(data, f"setup_rule_{n}")
        if not (name or about or pairs):
            continue
        rules = [Rule(number + i, text, detail) for i, (text, detail) in enumerate(pairs)]
        number += len(rules)
        p.setups.append(Setup(name=name, text=about, rules=rules))
    p.filters = [Rule(number + i, text, detail)
                 for i, (text, detail) in enumerate(rule_pairs(data, "filter"))]
    number += len(p.filters)
    p.management = [Rule(number + i, text, detail)
                    for i, (text, detail) in enumerate(rule_pairs(data, "management"))]
    p.limits = []
    kinds, names, values = (data.get("limit_kind", []), data.get("limit_name", []),
                            data.get("limit_value", []))
    for i, kind in enumerate(kinds):
        what = (names[i] if kind == "other" and i < len(names) else kind).strip()
        value = (values[i] if i < len(values) else "").strip()
        if what and what != "other" and value:
            p.limits.append((what, value))
    p.sections = []
    notes = one(data, "notes").replace("\r", "").strip()
    no_reserved_heading(notes, "notes")
    if notes:
        parts = store._split_sections(notes if notes.startswith("## ")
                                      else "## Notes\n" + notes)
        p.sections = [(h, t) for h, t in parts.items() if t.strip()]
    return p


def add_review(p, data):
    """A dated entry at the end of the review, with its screenshots appended
    to the shots folder, the way an update is added to a plan: this form
    shows one zone, so the folder is never rewritten from it."""
    text = one(data, "review").replace("\r", "").strip()
    if not text:
        raise RecordError("a review without a word in it")
    if any(line.startswith("## ") for line in text.split("\n")):
        raise RecordError("a review takes no headings")
    token = one(data, "token")
    folder = store.playbook_dir(ROOT, p.id)
    shots = add_shots(folder, "review",
                      zone_sources(data, "review", folder, token)) if token else []
    entry = f"**{datetime.now():%d.%m.%Y}**: {text}"
    for name in shots:
        entry += f"\n![]({name})"
    p.review = (p.review + "\n\n" + entry) if p.review.strip() else entry
    store.save_playbook(ROOT, p)
    if token:
        drop_draft(token)
    return p


RESERVED = ("Setups", "Conditions", "Filters", "Management", "Limits", "Review")


def no_reserved_heading(text, where):
    """A `## ` line in free text that names one of the headings the file
    gives a meaning to would replace that part on the next load."""
    for line in text.split("\n"):
        if line.startswith("## ") and line[3:].strip() in RESERVED:
            raise RecordError(f"{where}: a heading cannot be called "
                              f"{line[3:].strip()}, that name belongs to the file")
        if where == "intro" and line.startswith("## "):
            raise RecordError("the introduction takes no headings; they go in the notes")


def rules_shape(p):
    return ([(x.name, [(r.text, r.detail) for r in x.rules]) for x in p.setups],
            [(r.text, r.detail) for r in p.filters],
            [(r.text, r.detail) for r in p.management])


def create_playbook(data):
    p = playbook_from_form(data, Playbook(id=""))
    p.id = store.new_playbook_id(ROOT, p.name)
    p.check()
    store.save_playbook(ROOT, p)
    return p


def trades_under(j, playbook_id, version):
    """The trades ticked against that version of the playbook. A trade tied
    to it later, with no ticks, holds nothing: there was no checklist."""
    return [t for t in j.trades
            if t.playbook == playbook_id and t.playbook_version == version
            and t.deviations is not None]


def edit_playbook(before, data):
    """Rules rewritten under the same number would leave every trade opened
    under that number pointing at rules it was never ticked against, so once
    such trades exist a change of the rules asks for a new number, and the
    old file is kept for them. Until the first trade the rules are a draft
    and are edited freely: nothing points at them yet. A trade tied to the
    playbook without a checklist does not count as pointing."""
    p = playbook_from_form(data, Playbook(id=before.id, extra=dict(before.extra),
                                          review=before.review))
    p.check()
    held = trades_under(journal(True), before.id, before.version)
    if held and rules_shape(p) != rules_shape(before) and p.version == before.version:
        raise RulesChanged(p)
    # a new number with the rules untouched is frozen as well: the next
    # change of the rules will have no ticked trade under the new number to
    # stop it, and the old trades would be left looking at the new rules
    if held and p.version != before.version:
        store.freeze_playbook(ROOT, before.id)
    store.save_playbook(ROOT, p)
    return p




# --- daily card ------------------------------------------------------------
# The paper Daily Report Card carried over as it is: the same fields in the same
# order. One file per day in journal/cards, next to the trades, under git.

GRADES = ["A", "B", "C", "D", "F"]
# The progress of the current focus, 1 to 10, each number with the word that
# says what it means. The words are here so that the same number stands for the
# same week in January and in June: a scale nobody wrote down drifts. 10 is a
# focus worked through, one you can retire and take the next.
PROGRESS = [(1, "not moved"),
            (2, "slipped back"),
            (3, "barely moved"),
            (4, "moved on the easy days"),
            (5, "halfway"),
            (6, "more forward than back"),
            (7, "a clear step"),
            (8, "nearly there"),
            (9, "one more week"),
            (10, "done, take a new focus")]
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


def running_trades(j, until):
    """The trades the period held but did not close: opened before it ended
    and still in the market then.

    A swing entered on Monday and closed a fortnight later was in the market
    all that week, and the week is reviewed with it in the market. It is not
    in the money of the card: a period is measured by the exit, and the R of
    that swing belongs to the week it closed in."""
    return [t for t in j.trades if t.opened and t.opened < until
            and (t.is_open or not t.closed or t.closed >= until)]


CLOSED_FORMS = (lambda t: f"{t.pair} {t.direction}, {t.closed:%d.%m}",
                lambda t: f"{t.pair} {t.direction}, {t.closed:%d.%m}, {t.account}",
                lambda t: f"{t.pair} {t.direction}, {t.closed:%d.%m %H:%M}, {t.account}",
                lambda t: f"{t.pair} {t.direction}, {t.closed:%d.%m}, {t.id}")
# A trade the period did not close is offered by the day it was entered, and
# says so in words: the two sets of labels cannot collide, because only these
# carry "open since".
OPEN_FORMS = (lambda t: f"{t.pair} {t.direction}, open since {t.opened:%d.%m}",
              lambda t: f"{t.pair} {t.direction}, open since {t.opened:%d.%m}, {t.account}",
              lambda t: f"{t.pair} {t.direction}, open since {t.opened:%d.%m}, {t.id}")


def _labels(trades, forms):
    def label(t):
        for form in forms:
            if sum(form(x) == form(t) for x in trades) == 1:
                return form(t)
        return forms[-1](t)
    return {t.id: label(t) for t in trades}


def trade_labels(closed, running=()):
    """How the trades of a period are offered to the assessment, by trade id.

    Pair, direction and the day of the close, which is what a reader wants to
    see. The account is added only when two trades share all three, which is
    what a trade duplicated on a second account does; the hour when they share
    the account too, and the id itself when the exits carry no hour. The label
    has to be unique or the result column would be filled from the wrong
    trade. The ones the period did not close are offered by their entry."""
    labels = _labels(list(closed), CLOSED_FORMS)
    labels.update(_labels(list(running), OPEN_FORMS))
    return labels


def outcome_of(j, t, period=None):
    """How a trade ended, as the result column of a card says it.

    One still in the market says so, and that is the whole answer for it: what
    it is worth today is a price the journal does not have. One that closed
    outside the period the card reviews carries the day it closed, so a swing
    run through this week and closed a fortnight later reads as what it made
    and when, on the card of the week it was run."""
    if t.is_open or not t.closed:
        return "open"
    r = j.r(t.id)
    text = t.result + ("" if r is None else f" {r:+.2f} R")
    if period and not (period[0] <= t.closed < period[1]):
        text += f", {t.closed:%d.%m}"
    return text


def outcomes(j, closed, running=(), period=None):
    """What the journal knows for the result column, by what the trade field
    may hold: the label the trade was offered under, and the bare pair when
    that pair was traded once in the period, because a pair alone is what
    gets typed."""
    labels = trade_labels(closed, running)
    known = {labels[t.id]: outcome_of(j, t, period)
             for t in list(closed) + list(running)}
    by_pair = {}
    for t in closed:
        by_pair.setdefault(t.pair, []).append(t)
    known.update({pair: outcome_of(j, ts[0], period)
                  for pair, ts in by_pair.items() if len(ts) == 1})
    return known


def results_by_id(j, rows, period=None):
    """The journal's answer for the rows that name a trade it still has, by
    trade id. A row that carries one is drawn from this and stores nothing:
    the result of a trade is computed, and computed again when it changes."""
    have = {t.id: t for t in j.trades}
    return {row.id: outcome_of(j, have[row.id], period)
            for row in rows if row.id and row.id in have}


# The result of a picked trade is filled in as it is picked, so that the card
# is complete on the first save. A result the owner typed is never touched; one
# the script filled follows the trade field if that is changed again.
ASSESSMENT_SCRIPT = """
document.querySelectorAll('table.assessment').forEach(table => {
  const known = JSON.parse(table.dataset.known || '{}');
  const ids = JSON.parse(table.dataset.ids || '{}');
  table.addEventListener('input', e => {
    if (e.target.name === 'assess_result') { delete e.target.dataset.auto; return; }
    if (e.target.name !== 'assess_trade') return;
    const row = e.target.closest('tr');
    const result = row.querySelector('[name=assess_result]');
    const text = e.target.value.trim();
    const hit = known[text] || known[text.toUpperCase()];
    // the line keeps the trade it was picked from, and lets it go when the
    // text is changed to something the journal does not know
    row.querySelector('[name=assess_id]').value = ids[text] || ids[text.toUpperCase()] || '';
    if (hit && (!result.value || result.dataset.auto)) {
      result.value = hit; result.dataset.auto = '1';
    }
  });
});
"""


# A trade of the period put into a text field, at the caret: the best trade is
# written in the owner's words, and what the journal can help with is the name,
# spelled the way the assessment spells it.
PICK_SCRIPT = """
document.querySelectorAll('.pick').forEach(pick => {
  pick.addEventListener('change', () => {
    const text = pick.value.trim();
    const box = document.querySelector('textarea[name="' + pick.dataset.into + '"]');
    if (!text || !box) return;
    const at = box.selectionStart === null ? box.value.length : box.selectionStart;
    box.value = box.value.slice(0, at) + text + ' ' + box.value.slice(at);
    pick.value = '';
    box.focus();
    box.setSelectionRange(at + text.length + 1, at + text.length + 1);
  });
});
"""


def trade_picker(field, hint, labels):
    """The list that offers the trades of the period to a text box.

    A drop-down and not a suggestion field: the trades of a week are few, and
    a list you can open is a list you can see. It writes nothing of its own,
    what you pick is inserted into the box named by `field` at the cursor and
    the picker goes back to empty, so the text stays one text."""
    options = "".join(f'<option value="{esc(label)}">{esc(label)}</option>'
                      for label in labels)
    return (f'<select class="pick" data-into="{field}" '
            f'style="width:100%;max-width:300px;margin-bottom:8px">'
            f'<option value="">{esc(hint)}</option>{options}</select>'
            f'<script>{PICK_SCRIPT}</script>')


def assessment_rows(j, k, closed, running=(), period=None):
    """The table of the paper: numbered lines of a trade, the mark it earned
    and how it ended. It offers the same trades the best trade field does,
    here as suggestions under the field and there as a drop-down.

    A card written by hand may carry more than the paper's rows, so every row
    it has is drawn; a row left empty is dropped when the form comes back. A
    row that names a trade the journal knows and has no result yet is shown
    with the journal's result, the way a new card is shown with the day's P&L:
    offered, and saved only when the card is.

    The trades the period did not close are offered too, so a swing that was
    run all week can be graded in the week it was run. Its line says "open"
    while it is open and says what it made once it closes, because the line
    keeps the trade and not the answer."""
    listed = list(k.assessment) + [Graded() for _ in range(ASSESSMENT_ROWS)]
    known = outcomes(j, closed, running, period)
    labels = trade_labels(closed, running)
    ids = {label: tid for tid, label in labels.items()}
    live = results_by_id(j, k.assessment, period)
    options = "".join(f'<option value="{esc(label)}">' for label in labels.values())

    def result_of(row):
        text = row.trade.strip()
        return (row.result or live.get(row.id) or known.get(text)
                or known.get(text.upper()) or "")
    body = "".join(
        f'<tr><td class="muted">{n}.</td>'
        f'<td><input type="text" name="assess_trade" list="assesstrades" '
        f'autocomplete="off" style="width:100%" value="{esc(row.trade)}">'
        f'<input type="hidden" name="assess_id" value="{esc(row.id)}"></td>'
        f'<td><input type="text" name="assess_grade" list="grades" '
        f'autocomplete="off" style="width:90px" value="{esc(row.grade)}"></td>'
        f'<td><input type="text" name="assess_result" '
        f'autocomplete="off" style="width:100%" value="{esc(result_of(row))}"></td></tr>'
        for n, row in enumerate(listed[:max(ASSESSMENT_ROWS, len(k.assessment))], 1))
    return (f'<h3>trades assessment</h3>'
            f'<datalist id="assesstrades">{options}</datalist>'
            f'<table class="assessment" data-known="{esc(json.dumps(known))}" '
            f'data-ids="{esc(json.dumps(ids))}">'
            f'<thead><tr><th style="width:24px"></th><th>trade</th>'
            f'<th style="width:110px">grade</th><th style="width:150px">result</th>'
            f'</tr></thead><tbody>{body}</tbody></table>'
            f'<script>{ASSESSMENT_SCRIPT}</script>')


def read_assessment(data):
    """The rows of the assessment table, the empty ones left out. A result
    without a trade is not a row: the result was offered for a trade that was
    then taken out."""
    grades = data.get("assess_grade", [])
    results = data.get("assess_result", [])
    ids = data.get("assess_id", [])
    rows = []
    for n, text in enumerate(data.get("assess_trade", [])):
        grade = grades[n] if n < len(grades) else ""
        result = results[n] if n < len(results) else ""
        tid = ids[n] if n < len(ids) else ""
        if text.strip() or grade.strip():
            rows.append(Graded(trade=text.strip(), grade=grade.strip(),
                               result=result.strip(), id=tid.strip()))
    return rows


def drop_computed(j, rows, period=None):
    """The result the journal would give anyway is not written into the card.

    The row keeps the trade it names, and the answer is worked out again every
    time the card is read, which is how a trade graded while it was open says
    what it made once it closes. A result the owner typed instead of the one
    offered is not touched, and stands."""
    live = results_by_id(j, rows, period)
    for row in rows:
        if row.id and row.result == live.get(row.id):
            row.result = ""


def trades_breakdown(j, closed, running=()):
    """The trades of a period as figures and colour, the way the winrate tile
    on the front page says its three: won, lost, flat, and the ones still in
    the market: for a card, when its period ended; for a report, open now.

    No labels, the colour is the word: green, red, amber, blue. A figure that
    is zero is left out, so an ordinary week reads `2 / 1` and not
    `2 / 1 / 0 / 0`; the tooltip spells it out for the one time it is needed."""
    s = stats.summary(j, list(closed))
    counted = [(s.wins, "win", "won"), (s.losses, "lose", "lost"),
               (s.be, "be", "break-even"), (len(running), "live", "still open")]
    shown = [(n, cls, word) for n, cls, word in counted if n]
    if not shown:
        return ""
    how = ", ".join(f"{n} {word}" for n, _, word in shown)
    figures = " / ".join(f'<span class="{cls}">{n}</span>' for n, cls, _ in shown)
    return f'<span class="breakdown" title="{esc(how)}">{figures}</span>'


def cards_page():
    """Both report cards, the days over the weeks: two tables on one tab.

    They are one kind of record kept in two rhythms, and they sit in one folder,
    so the tab that lists them shows them one under the other."""
    problems = []
    j = journal()
    cards = store.all_cards(ROOT, problems)
    weeks = store.all_weeks(ROOT, problems)

    def day_figures(k):
        return trades_breakdown(j, day_trades(j, k.day),
                                running_trades(j, day_period(k.day)[1])) or "-"

    def week_figures(k):
        counted = trades_breakdown(j, week_trades(j, k.week),
                                   running_trades(j, week_period(k.week)[1]))
        # a card from before the journal held those trades has nothing to
        # break down, and keeps the count it was written with
        return counted or ("-" if k.trades is None else str(k.trades))

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
                              (day_figures(k), "num"),
                              (esc(k.quality) or "-", ""),
                              (esc(first_line(k.overview or k.focus)), "muted")])
            + "</tr>" for k in cards)
        daily = (f'<table><thead><tr><th>date</th><th>process</th>'
                 f'<th class="num">P&amp;L {sign}</th><th class="num">trades</th>'
                 f'<th>opportunity</th>'
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
                              (week_figures(k), "num"),
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
    period = day_period(day)
    running = running_trades(j, period[1])
    is_new = k is None
    if is_new:
        k = Card(day=day, pnl=day_pnl(j, day) if closed else None)
    options = "".join(f'<option value="{g}">' for g in GRADES)
    labels = {name: label for name, _, label in CARD_SECTIONS}

    def section(name):
        # the best trade of the day names a trade: the day's are offered to it
        pick = (trade_picker(name, "pick a trade of the day",
                             trade_labels(closed, running).values())
                if name == "best" and (closed or running) else "")
        return (f'<h3>{esc(labels[name])}</h3>{pick}'
                f'<textarea name="{name}" style="min-height:'
                f'{SECTION_HEIGHT.get(name, 84)}px">{esc(getattr(k, name))}</textarea>')
    # laid out as the paper is: the best trade and the assessment side by
    # side, the overview across the width under them
    upper = "".join(section(name) for name in ("focus", "process", "learned", "errors"))
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
<div class="card">{upper}</div>
<div class="card twin"><div>{section("best")}</div>
<div>{assessment_rows(j, k, closed, running, period)}</div></div>
<div class="card">{section("overview")}</div>
<div class="actions"><button class="btn primary">Save card</button>
<a class="btn" href="/cards">Cancel</a>{delete}</div>
</form>"""
    return page(f"Card {day:%d.%m.%Y}", body, "cards")


def day_period(day):
    """The day a card reviews, from its first moment to the next day's."""
    start = datetime(day.year, day.month, day.day)
    return start, start + timedelta(days=1)


def save_card(data):
    day = day_from_url(one(data, "date"))
    previous = one(data, "previous")
    k = Card(day=day, grade=one(data, "grade"), quality=one(data, "quality"))
    pnl = one(data, "pnl")
    k.pnl = float(pnl.replace(",", ".")) if pnl else None
    for name, _, _ in CARD_SECTIONS:
        setattr(k, name, one(data, name))
    k.assessment = read_assessment(data)
    drop_computed(journal(), k.assessment, day_period(day))
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


def week_period(key):
    """The week a card reviews: Monday to the Monday after it."""
    monday = Week(week=key).monday
    return monday, monday + timedelta(days=7)


def week_page(key):
    j = journal()
    k = store.load_week(ROOT, key)
    closed = week_trades(j, key)
    period = week_period(key)
    running = running_trades(j, period[1])
    is_new = k is None
    if is_new:
        k = Week(week=key, pnl=sum(t.pnl or 0.0 for t in closed) if closed else None,
                 trades=len(closed) if closed else None)
    options = "".join(f'<option value="{g}">' for g in GRADES)
    progress = "".join(
        f'<option value="{n}"{" selected" if k.progress == n else ""}>'
        f'{n} · {esc(word)}</option>' for n, word in PROGRESS)
    sections = ""
    for name, _, label in WEEK_SECTIONS:
        # the best trade of the week names a trade: the week's are offered to it
        pick = (trade_picker(name, "pick a trade of the week",
                             trade_labels(closed, running).values())
                if name == "best" and (closed or running) else "")
        sections += (f'<h3>{esc(label)}</h3>{pick}'
                     f'<textarea name="{name}" style="min-height:'
                     f'{SECTION_HEIGHT.get(name, 84)}px">{esc(getattr(k, name))}'
                     f'</textarea>')
        if name == "focus":
            sections += (f'<div class="fields" style="margin-top:8px">'
                         f'<div class="field"><label>progress</label>'
                         f'<select name="progress" style="width:280px">'
                         f'<option value=""></option>{progress}</select>'
                         f'<p class="caption">How far the focus moved this week, '
                         f'out of 10. A 10 is a focus worked through: retire it '
                         f'and write the next one.</p>'
                         f'</div></div>')
    # the trades of the week under the field that counts them: won, lost and
    # the ones still in the market, by colour, the way the front page says it
    counted = trades_breakdown(j, closed, running)
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
 value="{"" if k.trades is None else k.trades}">
{counted and f'<p class="caption">{counted}</p>'}</div>
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
<div class="card">{assessment_rows(j, k, closed, running, period)}</div>
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
    drop_computed(journal(), k.assessment, week_period(key))
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
# A report is drawn from the journal as it stands. The file is what build()
# writes, the archive and the home of the conclusions. The page
# answers what a review asks, in the order it asks: how the period ended, what
# stood behind it, where the rules gave way, which two trades are worth
# reopening, and only then the tables. Every shape on it is one the front page
# already has: a tile, a bar, a ring, a table. Nothing is graded and no
# surface is coloured.

def tile(name, value, sub="", cls="", lead=False):
    """One tile of a strip: a caption, a figure, a line under it."""
    kind = "tile lead" if lead else "tile"
    under = f'<div class="sub">{sub}</div>' if sub else ""
    return (f'<div class="{kind}"><div class="name">{name}</div>'
            f'<div class="value {cls}">{value}</div>{under}</div>')


def r_text(x):
    return f"{x:+.2f} R"


def report_tiles(j, r):
    """The headline strip: the rows of the old summary table, one tile each,
    the period before as the last clause of the sub line, so every figure is
    still read against something without a second column to cross-read."""
    s, was = r.total, r.was
    then = esc(r.earlier_name)
    money = (f'<span class="{sum_class(s.sum_pnl)}">{amount(j, s.sum_pnl, signed=True)}'
             f'</span>' if s.trades else "")
    result = tile("result", r_text(s.sum_r) if s.trades else "-",
                  " · ".join(x for x in (
                      money or "no closed trades",
                      f'<span class="muted">{then}: '
                      f'{r_text(was.sum_r) if was.trades else "-"}</span>') if x),
                  sum_class(s.sum_r) if s.trades else "muted", lead=True)
    winrate = tile("winrate",
                   f"{s.wr:.1f}% {expectancy(s)}" if s.decided else "-",
                   " · ".join(x for x in (
                       trades_breakdown(j, r.trades, r.held),
                       f'<span class="muted">{then}: '
                       f'{f"{was.wr:.1f}%" if was.decided else "-"}</span>') if x),
                   "" if s.decided else "muted")
    fall = tile("deepest fall from a high",
                r_text(r.fall) if r.fall else ("0.00 R" if s.trades else "-"),
                " · ".join(x for x in (
                    "" if r.fall or not s.trades else "never below its high",
                    f'<span class="muted">{then}: '
                    f'{r_text(r.was_fall) if was.trades else "-"}</span>') if x),
                "" if s.trades else "muted")
    return ('<div class="tiles report">' + result + winrate + fall + mistakes_tile(r)
            + process_tile(r) + extremes_tile(j, r) + "</div>")


def mistakes_tile(r):
    """What the journal itself calls a mistake, counted and priced: a rule
    ticked as not met, at the entry or at the close, and a loss past the stop.
    The count stays ink, only the R under it carries colour: a number painted
    red is a grade, and a report does not grade. A trade never ticked says
    nothing either way, and the tile says so rather than reading as clean."""
    if not r.ticked and not r.past_stop:
        if not r.trades:
            return tile("mistakes", "-", "no closed trades", "muted")
        within = " · every loss stayed within the stop" if r.total.losses else ""
        if r.unticked:
            return tile("mistakes", "-", f"{r.unticked} under a playbook, none ticked{within}", "muted")
        return tile("mistakes", "-", f"no checklist ticked{within}", "muted")
    n = len(r.mistakes)
    bits = []
    broke = len({t.id for t in r.mistakes if stats.broke(t)})
    if broke:
        bits.append(f"{broke} broke a rule")
    if r.past_stop:
        bits.append(f"{len(r.past_stop)} past the stop")
    if n:
        bits.append(f'{"that trade" if n == 1 else "those trades"} '
                    f'<span class="{sum_class(r.mistakes_sum.sum_r)}">'
                    f'{r_text(r.mistakes_sum.sum_r)}</span>')
    else:
        bits.append("every ticked trade kept every rule")
        if r.total.losses:
            bits.append("every loss stayed within the stop")
    if r.unticked:
        bits.append(f'<span class="muted">{r.unticked} not ticked</span>')
    return tile("mistakes", str(n), " · ".join(bits), "" if n else "muted")


def process_tile(r):
    """Cards written against days traded, and the grades they carry."""
    if not r.cards and not r.days_traded:
        return tile("process", "-", "no days traded, no cards", "muted")
    value = f"{len(r.cards)} / {r.days_traded}"
    if not r.cards:
        return tile("process", value, "no cards written on the days traded", "muted")
    grades = " · ".join(f"{esc(g)} {n}" for g, n in r.grades)
    return tile("process", value, f"cards on days traded · {grades}")


def extremes_tile(j, r):
    """The two trades worth opening again, by R: a figure each, and the trade
    under it as the way in."""
    if not r.best:
        return tile("best / worst trade", "-", "no closed trades", "muted")

    def way(t):
        return (f'<a href="{trade_way(r, t)}">{esc(t.pair)} {esc(t.style)}, '
                f'{t.closed:%d.%m}</a>')
    best = j.r(r.best.id) or 0.0
    value = f'<span class="{sum_class(best)}">{r_text(best)}</span>'
    sub = way(r.best)
    if r.worst:
        worst = j.r(r.worst.id) or 0.0
        value += f'<span class="ev {sum_class(worst)}">{r_text(worst)}</span>'
        sub += f" · {way(r.worst)}"
    if r.worst:
        name = "best / worst trade"
    else:
        name = "the only trade" if len(r.trades) == 1 else "every trade the same R"
    return tile(name, value, sub)


def report_head(r):
    """The period at reading size, with its edges under it."""
    last = r.end - timedelta(days=1)
    bits = [f"{r.start:%d.%m} to {last:%d.%m.%Y}",
            f"{r.total.trades} trade{'' if r.total.trades == 1 else 's'} closed",
            f"read against {esc(r.earlier_name)}"]
    return (f'<div class="report-head"><div><h2>{esc(r.kind)}ly report</h2>'
            f'<h1 class="pb-name">{esc(r.name)}</h1>'
            f'<p class="pb-meta">{" · ".join(bits)}</p></div></div>')


def report_nav(r, ready):
    """The reports beside this one: the period before, the one after, and for
    a month its quarter, each a button only when that report exists."""
    parts = []
    before, after = reports.previous_period(r.period), reports.next_period(r.period)
    if before in ready:
        parts.append(f'<a class="btn" href="/report/{U(before)}">'
                     f'← {esc(reports.parse_period(before)[2])}</a>')
    parts.append('<a class="btn" href="/reports">All reports</a>')
    if r.kind == "month":
        quarter = stats.quarter(r.start)
        if quarter in ready:
            parts.append(f'<a class="btn" href="/report/{U(quarter)}">'
                         f'{esc(reports.parse_period(quarter)[2])}</a>')
    if after in ready:
        parts.append(f'<a class="btn" href="/report/{U(after)}">'
                     f'{esc(reports.parse_period(after)[2])} →</a>')
    return "".join(parts)


def conclusions_card(r, text, stamp):
    """The owner's words, in one place whatever their state: written, they
    are read as text with the form behind Edit; not yet, the field is open."""
    form = (f'<form method="post" action="/report/{U(r.period)}">'
            f'<textarea name="conclusions" placeholder="What you learned this period: '
            f'what to keep, what to stop">{esc(text)}</textarea>'
            f'<p class="actions"><button class="btn primary">Save conclusions</button></p>'
            f'</form>')
    stamp = stamp if isinstance(stamp, str) else ""
    try:
        stamp = datetime.strptime(stamp, "%Y-%m-%d %H:%M").strftime("%d.%m.%Y %H:%M")
    except ValueError:
        pass
    when = f", last built {esc(stamp)}" if stamp else ""
    note = (f'<p class="caption">This page is drawn from the journal as it is now. '
            f'Saving writes these figures with your text into '
            f'<code>journal/reports/{esc(r.period)}.md</code>{when}; the text is '
            f'never overwritten by a rebuild.</p>')
    if text:
        return (f'<div class="card conclusions"><h2>Conclusions</h2>'
                f'<div class="pb-text">{paragraphs(text)}</div>'
                f'<details class="fold" style="margin-top:12px"><summary>Edit</summary>'
                f'{form}{note}</details></div>')
    return f'<div class="card"><h2>Conclusions</h2>{form}{note}</div>'


def trade_way(r, t):
    """The address of a trade opened from a report: the report rides along, so
    the trade page can offer the way back."""
    return f"/trade/{U(t.id)}?report={U(r.period)}"


def report_tape(j, r):
    """The trades of the period one bar each, cut into weeks or months."""
    if not r.order:
        return NOTHING_TO_PLOT
    bars, marks, last = [], [], None
    for i, t in enumerate(r.order):
        key = stats.week(t.closed) if r.kind == "month" else f"{t.closed:%Y-%m}"
        if key != last:
            label = (f"W{int(key[6:])}" if r.kind == "month"
                     else reports.MONTH_NAMES[int(key[5:]) - 1][:3])
            marks.append((i, label))
            last = key
        rr = j.r(t.id) or 0.0
        words = (f"{t.closed:%d.%m.%Y} {t.pair} {t.direction} · {t.style} · "
                 f"{t.result} {rr:+.2f} R · {amount(j, t.pnl, t.account, signed=True)}")
        bars.append((rr, t.result, trade_way(r, t), words))
    return H.tape_svg(bars, marks, height=270)


def report_pictures(j, r):
    """The shape of the period: every trade by size, and the two rings."""
    word = "week" if r.kind == "month" else "month"
    caption = (f'<p class="caption">One bar per closed trade, in the order of the '
               f'exits, a line where a new {word} begins. A break-even is the amber '
               f'tick on the zero line; the dashed line is the stop, -1 R. A bar past '
               f'it means the size was too large. Each bar opens its trade.</p>')
    left = (f'<div class="card"><h2>Trade by trade</h2>{report_tape(j, r)}'
            f'{caption if r.order else ""}</div>')
    return f'<div class="pictures">{left}{r_rings(j, r.trades, compact=True)}</div>'


def rules_card(j, r):
    """Which rules gave way and what it cost, against the trades that kept them
    all; then the losses past the stop, each a way to its trade."""
    if not r.ticked:
        body = ('<p class="muted">No trade of the period went through a checklist, '
                'so nothing can be said about the rules.</p>')
    else:
        books = {label for label, _, _, _ in r.rules}
        rows = "".join(
            f'<tr><td><span class="n muted">'
            f'{esc(label + " " if len(books) > 1 else "")}{rule.number}</span> '
            f'{esc(rule.text)}</td><td class="num">{n}</td>'
            f'<td class="num {sum_class(s.sum_r)}">{s.sum_r:+.2f}</td>'
            f'<td class="num">{s.average_r:+.2f}</td></tr>'
            for label, rule, n, s in r.rules)
        kept = (f'<tr class="total"><td>kept every rule</td>'
                f'<td class="num">{r.kept.trades}</td>'
                f'<td class="num {sum_class(r.kept.sum_r)}">{r.kept.sum_r:+.2f}</td>'
                f'<td class="num">{r.kept.average_r:+.2f}</td></tr>')
        body = (f'<table><thead><tr><th>rule not met</th><th class="num">trades</th>'
                f'<th class="num">Σ R</th><th class="num">EV</th></tr></thead>'
                f'<tbody>{rows}{kept}</tbody></table>'
                f'<p class="caption">{r.ticked} ticked trade{"" if r.ticked == 1 else "s"}. '
                f'A trade that broke '
                f'several rules stands in each of their rows; the last row is the '
                f'measure, what the trades that kept every rule brought. Rules are '
                f'counted by number, so only trades ticked against the current version '
                f'of their playbook stand in the rows.</p>')
    if r.past_stop:
        lines = "".join(
            f'<tr>{link_cell(trade_way(r, t), f"{t.closed:%d.%m.%Y}")}'
            f'{link_cell(trade_way(r, t), H.pair(t.pair))}'
            f'{link_cell(trade_way(r, t), esc(t.style))}'
            f'{link_cell(trade_way(r, t), r_text(j.r(t.id) or 0.0), "num lose")}</tr>'
            for t in r.past_stop)
        body += (f'<h3>Past the stop</h3><table><tbody>{lines}</tbody></table>'
                 f'<p class="caption">The stop with commission and swap on top lands '
                 f'between -1 and -1.2 R; a loss past that means the size was too '
                 f'large.</p>')
    return f'<div class="card"><h2>Rules</h2>{body}</div>'


def process_card(r):
    """The cards of the period: how many days were reviewed, what grades they
    got, and the errors written on them in the owner's own words."""
    if not r.cards and not r.weeks:
        body = (f'<p class="muted">No cards written for this period, and '
                f'{r.days_traded} day{"" if r.days_traded == 1 else "s"} had trades.</p>')
        return f'<div class="card"><h2>Process</h2>{body}</div>'
    body = (f'<p class="pb-meta"><b>{len(r.cards)}</b> daily card'
            f'{"" if len(r.cards) == 1 else "s"} on <b>{r.days_traded}</b> day'
            f'{"" if r.days_traded == 1 else "s"} traded'
            + (f', <b>{len(r.weeks)}</b> weekly' if r.weeks else "") + "</p>")
    if r.grades:
        body += ('<p class="grades">' + "".join(
            f'<span class="chip">{esc(g)} <b>{n}</b></span>' for g, n in r.grades) + "</p>")
    poor = [k for k in r.cards if k.grade in ("D", "F")]
    if poor:
        body += ('<p class="caption days">D and F days: ' + " · ".join(
            f'<a href="/card/{U(k.id)}">{k.day:%d.%m}</a>' for k in poor) + "</p>")
    errors = [(f"/card/{U(k.id)}", f"{k.day:%d.%m}", k.errors) for k in r.cards
              if k.errors.strip()]
    errors += [(f"/week/{U(k.id)}", f"W{k.number}", k.errors) for k in r.weeks
               if k.errors.strip()]
    if errors:
        items = "".join(
            f'<li><a href="{href}">{esc(label)}</a>{inline(text.strip())}</li>'
            for href, label, text in errors)
        body += f'<h3>Errors written on the cards</h3><ul class="errors">{items}</ul>'
    return f'<div class="card"><h2>Process</h2>{body}</div>'


def accounts_card(j, r, link):
    """Each account before and after the period, then the figures by account."""
    tiles = ""
    for account, before, after in r.balances:
        name = j.accounts[account].name or account
        change = after - before
        tiles += tile(f'<a href="{link("By account", account)}">{esc(name)}</a>',
                      amount(j, after, account),
                      f'from {amount(j, before, account)} · '
                      f'<span class="{sum_class(change)}">'
                      f'{amount(j, change, account, signed=True)}</span>')
    rows = dict(r.slices).get("By account", [])
    table = slice_table(j, "By account", rows, link) if rows else ""
    return (f'<div class="card"><h2>Accounts</h2>'
            f'<div class="tiles narrow">{tiles}</div>{table}</div>')


def slice_rows(j, heading, rows, link, first=None):
    """The rows of one slice table, in the order the Statistics tab keeps
    them; Σ R is the one coloured column."""
    out = ""
    for value, s in rows:
        shown = first(value) if first else (H.pair(value) if heading == "By pair" else esc(value))
        href = link(heading, value) if link else None
        cell = f'<a href="{href}">{shown}</a>' if href else shown
        out += (f'<tr><td>{cell}</td><td class="num">{s.trades}</td>'
                f'<td class="num">{s.wr:.1f}%</td>'
                f'<td class="num {sum_class(s.sum_r)}">{s.sum_r:+.2f}</td>'
                f'<td class="num">{s.average_r:+.2f}</td>'
                f'<td class="num">{H.money(s.sum_pnl, signed=True)}</td></tr>')
    return out


def slice_table(j, heading, rows, link, first=None, caption=""):
    return (f'<table><thead><tr><th></th>{figures_head()}'
            f'<th class="num">Σ {H.sign(j.currency())}</th></tr></thead>'
            f'<tbody>{slice_rows(j, heading, rows, link, first)}</tbody></table>'
            + (f'<p class="caption">{caption}</p>' if caption else ""))


def slice_card(j, heading, rows, link, caption=""):
    if not rows:
        return ""
    return (f'<div class="card"><h2>{esc(heading)}</h2>'
            f'{slice_table(j, heading, rows, link, caption=caption)}</div>')


def months_card(j, r, ready):
    """A quarter by its months, in order, each the way to its own report."""
    if r.kind != "quarter" or not r.trades:
        return ""
    rows = stats.by_values(j, r.trades, lambda t: [f"{t.closed:%Y-%m}"])
    rows.sort(key=lambda x: x[0])

    def link(_, key):
        if key in ready:
            return f"/report/{U(key)}"
        return f"/?from={U(key)}&to={U(key)}&group=week"
    table = slice_table(j, "By month", rows, link,
                        first=lambda key: esc(reports.parse_period(key)[2]),
                        caption="A month with a report of its own opens it; one "
                                "without opens its trades in the journal.")
    return f'<div class="card"><h2>By month</h2>{table}</div>'


# Which filter of the journal a table of a report belongs to.
REPORT_LINKS = {"By style": "style", "By pair": "pair", "By account": "account",
                "By direction": "direction"}


def report_link(period):
    """A row of a report leads to the trades it was counted from: the same
    filter, narrowed to the months of the report."""
    since, until = reports.period_months(period)

    def link(section, value):
        field = REPORT_LINKS.get(section)
        if not field or not value:
            return None
        return (f"/?{field}={U(value)}&from={U(since)}&to={U(until)}"
                f"&group={'month' if 'Q' in period else 'week'}")
    return link


def report_page(period):
    if not reports.is_period(period):
        return None
    head, body = reports.read(ROOT, period)
    if body is None:
        return None
    j = journal()
    r = reports.compose(ROOT, j, period)
    ready = set(reports.existing(ROOT))
    text = reports.previous_conclusions(ROOT, period)
    link = report_link(period)
    slices = dict(r.slices)
    left = (months_card(j, r, ready)
            + slice_card(j, "By pair", slices.get("By pair"), link)
            + slice_card(j, "By style", slices.get("By style"), link))
    right = (accounts_card(j, r, link)
             + slice_card(j, "By direction", slices.get("By direction"), link)
             + slice_card(j, "By entry TF", slices.get("By entry TF"), link)
             + slice_card(j, "By execution", slices.get("By execution"), link,
                          caption="A trade entered on two formats stands in both rows."))
    story = (report_head(r) + report_tiles(j, r) + report_pictures(j, r)
             + (f'<div class="twin books">{by_playbook_card(j, r.trades)}{rules_card(j, r)}</div>'
                if r.playbooks else (rules_card(j, r) if r.past_stop else ""))
             + f'<div class="twin">{process_card(r)}'
             f'{conclusions_card(r, text, head.get("updated", ""))}</div>')
    tables = (f'<div class="twin"><div>{left}</div><div>{right}</div></div>'
              if left and right else left + right)
    appendix = (tables
                + '<p class="caption">A pair, a style, an account or a direction opens '
                'the journal filtered to it over the same months. A period counts the '
                'trades that closed inside '
                'it; WR is wins against wins and losses, EV is Σ R over every closed '
                'trade, break-evens included.</p>')
    return page(r.name, story + appendix, "reports", report_nav(r, ready))


# --- the shelf of reports ---------------------------------------------------

def build_button(period, ready, lead=False):
    """Build, or rebuild, the file of a period: the same form as ever, one
    per row instead of two selects at the top."""
    kind = reports.kind_of(period)
    word = "rebuild" if period in ready else "Build"
    cls = "quiet" if period in ready else "btn small primary" if lead else "btn small"
    return (f'<form method="post" action="/report/build" class="inline">'
            f'<input type="hidden" name="what" value="{kind}">'
            f'<input type="hidden" name="period_{kind}" value="{esc(period)}">'
            f'<button class="{cls}">{word}</button></form>')


def shelf_cells(j, r):
    """The figures of one period on the shelf, live from the journal."""
    s = r.total
    if not s.trades:
        return ('<td class="num muted">-</td><td></td><td class="num muted">-</td>'
                '<td class="num muted">-</td><td class="num muted">-</td>'
                '<td class="num muted">-</td><td class="num muted">-</td>')
    cards = f"{len(r.cards)} / {r.days_traded}"
    return (f'<td class="num">{s.trades}</td><td>{trades_breakdown(j, r.trades, r.held)}</td>'
            f'<td class="num">{f"{s.wr:.1f}%" if s.decided else "-"}</td>'
            f'<td class="num {sum_class(s.sum_r)}">{s.sum_r:+.2f}</td>'
            f'<td class="num">{s.average_r:+.2f}</td>'
            f'<td class="num">{amount(j, s.sum_pnl, signed=True)}</td>'
            f'<td class="num{"" if r.cards else " muted"}">{cards}</td>')


def report_cell(period, ready, lead):
    """Whether the report stands: the way to it, or the button that makes it."""
    if period in ready:
        head, _ = reports.read(ROOT, period)
        written = bool(reports.previous_conclusions(ROOT, period))
        built = (head or {}).get("updated", "")
        built = built[:10] if isinstance(built, str) else ""
        try:
            built = datetime.strptime(built, "%Y-%m-%d").strftime("%d.%m.%Y")
        except ValueError:
            pass
        note = (f'<span class="caption">'
                + ('<span class="dot" title="conclusions written"></span>' if written else "")
                + f'built {esc(built)}</span>')
        return f'<td class="report">{note}{build_button(period, ready)}</td>'
    return f'<td class="report">{build_button(period, ready, lead)}</td>'


def reports_page():
    """Every month and quarter since the first closed trade, on one shelf,
    with its figures whether a report was built for it or not: the report
    that is missing is seen as clearly as the one that stands."""
    j = journal()
    now = datetime.now()
    ready = set(reports.existing(ROOT))
    months = set(reports.periods(j, "month")) | {p for p in ready if reports.kind_of(p) == "month"}
    if not months:
        body = ('<div class="card"><h2>Reports</h2><p class="muted">No closed trades '
                'yet, nothing to report.</p></div>')
        return page("Reports", body, "reports")
    quarters = set(reports.periods(j, "quarter")) | {p for p in ready if reports.kind_of(p) == "quarter"}
    quarters |= {stats.quarter(reports.parse_period(m)[0]) for m in months}
    composed = {p: reports.compose(ROOT, j, p) for p in months | quarters}
    this_month, this_quarter = reports.period_of(now, "month"), reports.period_of(now, "quarter")
    # the one Build that is primary: the newest finished period with trades
    # and no report, which is the report that is due. A quarter ends with its
    # last month; when both are due the month comes first, the quarter reads
    # its months
    due = max((p for p in months | quarters if p not in ready
               and p not in (this_month, this_quarter) and composed[p].trades),
              key=lambda p: (reports.parse_period(p)[1], reports.kind_of(p) == "month"),
              default=None)

    def name_cell(p, bold=False):
        title = reports.parse_period(p)[2]
        if p in ready:
            shown = f'<a href="/report/{U(p)}">{esc(title)}</a>'
        else:
            shown = f'<span class="{"" if composed[p].trades else "muted"}">{esc(title)}</span>'
        if p in (this_month, this_quarter):
            shown += ' <span class="chip">running</span>'
        return shown

    years = sorted({q[:4] for q in quarters}, reverse=True)
    rows = ""
    for year in years:
        if len(years) > 1:
            rows += (f'<tr class="group"><td colspan="9"><span class="label">{year}</span>'
                     f'</td></tr>')
        for q in sorted((q for q in quarters if q.startswith(year)), reverse=True):
            start, end, _ = reports.parse_period(q)
            span = (f"{reports.MONTH_NAMES[start.month - 1][:3]} to "
                    f"{reports.MONTH_NAMES[end.month - 2][:3]}")
            cell = (report_cell(q, ready, q == due)
                    if composed[q].trades or q in ready else "<td></td>")
            rows += (f'<tr class="quarter"><td>{name_cell(q)}'
                     f'<span class="muted" style="margin-left:8px">{span}</span></td>'
                     f'{shelf_cells(j, composed[q])}{cell}</tr>')
            for m in sorted((m for m in months if stats.quarter(reports.parse_period(m)[0]) == q),
                            reverse=True):
                cell = (report_cell(m, ready, m == due)
                        if composed[m].trades or m in ready else "<td></td>")
                rows += (f'<tr class="sub"><td>{name_cell(m)}</td>'
                         f'{shelf_cells(j, composed[m])}{cell}</tr>')
    table = (f'<table class="shelf"><thead><tr><th>period</th><th class="num">trades</th>'
             f'<th></th><th class="num">WR</th><th class="num">Σ R</th>'
             f'<th class="num">EV</th><th class="num">Σ {H.sign(j.currency())}</th>'
             f'<th class="num">cards</th><th>report</th></tr></thead><tbody>{rows}</tbody>'
             f'</table>')
    body = (f'<div class="card"><h2>Reports</h2>{table}'
            f'<p class="caption">Every quarter and month since the first closed trade, '
            f'with the figures the journal holds for it now, whether a report was '
            f'built or not. A period counts the trades that closed inside it; the '
            f'coloured figures beside a count are won, lost, break-even and, on the '
            f'running period, the positions open now in blue; cards are the daily cards '
            f'written against the days traded. Building a report writes the figures '
            f'into a file under <code>journal/reports</code> with a place for your '
            f'conclusions, marked with a dot here once written; rebuilding never '
            f'touches them.</p></div>')
    return page("Reports", body, "reports")


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
        f'<td>{esc(c.comment) or EMPTY_CELL}</td>'
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
    # folded: the list grows with every deleted record and is wanted rarely,
    # so the card shows the count and opens on a click
    n = len(trashed)
    trash = (f'<div class="card"><h2>Trash</h2>'
             f'<details class="fold"><summary>{n} record{"" if n == 1 else "s"}'
             f'<span class="caption">everything deleted, put back from here</span></summary>'
             + (f'<table><thead><tr><th>what</th><th>id</th><th>deleted</th>'
                f'<th></th></tr></thead><tbody>{trash_rows}</tbody></table>'
                if trashed else
                '<p class="muted">Nothing has been deleted.</p>')
             + f'<p class="caption">Everything deleted lands in <code>.trash</code> '
             f'next to the journal and is put back from here, screenshots and '
             f'all. A record written again under the same id since is not '
             f'overwritten: the one in the trash stays there.</p></details></div>')

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
        if path == "/playbooks":
            return self._send(playbooks_page())
        if path == "/playbook/new":
            return self._send(page("New playbook", playbook_form(None, new_token()),
                                   "playbooks"))
        if len(parts) == 2 and parts[0] == "playbook":
            shown = playbook_page(parts[1])
            return self._send(shown or "no such playbook", 200 if shown else 404)
        if len(parts) == 3 and parts[0] == "playbook" and parts[2] == "edit":
            if not store.safe_dir_name(parts[1]):
                return self._send("bad playbook id", 400)
            try:
                p = store.load_playbook(ROOT, parts[1])
            except OSError:
                return self._send("no such playbook", 404)
            return self._send(page("Edit playbook", playbook_form(p, new_token()),
                                   "playbooks"))
        if len(parts) == 3 and parts[0] == "playbook-shot":
            if not store.safe_dir_name(parts[1]):
                return self._send("bad playbook id", 400, "text/plain; charset=utf-8")
            return self._file(os.path.join(store.playbook_dir(ROOT, parts[1]),
                                           store.SHOTS, os.path.basename(parts[2])))
        if len(parts) == 4 and parts[0] == "playbook" and parts[2] == "version":
            shown = playbook_version_page(parts[1], parts[3])
            return self._send(shown or "no such version", 200 if shown else 404)
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
            shown = trade_page(parts[1], (q.get("report") or [""])[0])
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
            if path == "/playbook/new":
                p = create_playbook(data)
                return self._go(f"/playbook/{U(p.id)}", "Playbook written")
            if len(parts) == 3 and parts[0] == "playbook":
                if not store.safe_dir_name(parts[1]):
                    return self._send("bad playbook id", 400)
                if parts[2] == "delete":
                    if store.delete_playbook(ROOT, parts[1]) is None:
                        return self._send("no such playbook", 404)
                    return self._go("/playbooks", "Playbook moved to the trash")
                if parts[2] not in ("edit", "review"):
                    return self._send("no such page", 404)
                try:
                    before = store.load_playbook(ROOT, parts[1])
                except OSError:
                    return self._send("no such playbook", 404)
                if parts[2] == "review":
                    add_review(before, data)
                    return self._go(f"/playbook/{U(before.id)}", "Review added")
                try:
                    p = edit_playbook(before, data)
                except RulesChanged as e:
                    return self._send(page(
                        "Edit playbook",
                        playbook_form(e.args[0], new_token(),
                                      "The rules changed, and trades were opened "
                                      f"under version {esc(before.version) or 'this one'}. "
                                      "Give the new rules a new number: those "
                                      "trades keep the rules they were ticked "
                                      "against."),
                        "playbooks"), 400)
                return self._go(f"/playbook/{U(p.id)}", "Playbook saved")
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
                had = bool(reports.previous_conclusions(ROOT, parts[1]))
                reports.build(ROOT, journal(True), parts[1], conclusions=conclusions)
                return self._go(f"/report/{U(parts[1])}",
                                "Conclusions saved" if conclusions
                                else "Conclusions cleared" if had else "Report rebuilt")
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
