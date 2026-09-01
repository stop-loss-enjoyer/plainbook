#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The local journal server. 127.0.0.1 only, port 8778 (PLAINBOOK_PORT changes it).

Run:   python3 -m plainbook.server
Open:  http://127.0.0.1:8778
"""
import http.server
import json
import os
import re
import shutil
import time
import urllib.parse
from datetime import datetime, timedelta

from . import html as H
from . import reports, stats, store
from .balances import Journal
from .model import (Trade, Account, IdeaBlock, Card, RecordError,
                    DIRECTIONS, RESULTS, NEW_STYLES, CARD_SECTIONS,
                    PAIR_NOT_SET)

PORT = int(os.environ.get("PLAINBOOK_PORT") or 8778)
# the journal root can be overridden; the tests and a split data folder use it
ROOT = os.path.abspath(os.environ.get("PLAINBOOK_ROOT") or
                       os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DRAFTS = os.path.join(ROOT, ".drafts")
TIMEFRAMES = ["M15", "H1", "H4", "D1"]
EXECUTION = ["Market Entry", "IDM", "SNR", "FVG"]
esc = H.esc

_cache = {"journal": None, "time": 0.0}


def journal(fresh=False):
    """The journal is re-read from disk: the files are the source of truth."""
    if fresh or _cache["journal"] is None or time.time() - _cache["time"] > 2:
        _cache["journal"] = Journal.load(ROOT)
        _cache["time"] = time.time()
    return _cache["journal"]


def drop_cache():
    _cache["journal"] = None


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
            '<th>result</th><th class="num">PnL $</th><th class="num">R</th>'
            '</tr></thead><tbody>']
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
        sub += f" · {H.money(s.sum_pnl, signed=True)} $"
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
        balance = j.balance(a)
        growth = balance - account.start_balance
        colour = H.GOOD if growth >= 0 else H.BAD
        parts.append(
            f'<div class="tile"><div class="name">{esc(account.name or a)}</div>'
            f'<div class="value">{H.money(balance)} $</div>'
            f'<div class="sub">start {H.money(account.start_balance)} $ · '
            f'<span style="color:{colour}">{H.money(growth, signed=True)} $</span>'
            f'</div></div>')
    return '<div class="tiles narrow">' + "".join(parts) + "</div>"


def open_positions(j):
    open_trades = j.open_trades()
    if not open_trades:
        return ""
    rows = "".join(
        "<tr>" + "".join(
            link_cell(f"/trade/{U(t.id)}", inner, cls) for inner, cls in
            [(f"{t.opened:%d.%m.%Y %H:%M}", ""), (esc(t.account), ""),
             (H.pair(t.pair), ""), (esc(t.direction), ""), (esc(t.style), ""),
             (f"{t.risk:g}%", "num"),
             (f"{H.money(j.computed[t.id].risk_money)} $", "num")])
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
    s = stats.summary(j, [t for t in trades if t.style in styles])
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


def home_page(q):
    j = journal()
    trades = apply_filters(j, q)
    group = (q.get("group") or [""])[0]
    if group not in dict(GROUPS):
        group = "week"
    s = stats.summary(j, trades)
    tiles = (f'<div class="tiles">'
             + period_tile(j, trades, group)
             + f'<div class="tile"><div class="name">selection</div>'
             f'<div class="value">{s.trades}</div><div class="sub">trades</div></div>'
             + winrate_tile("winrate overall", NEW_STYLES, j, trades)
             + winrate_tile("winrate EMT", ("EMT",), j, trades)
             + winrate_tile("winrate EMT prop", ("EMT prop",), j, trades)
             # There is deliberately no total in money here: it would add up the
             # dollars of a prop account and of your own, and those are different
             # kinds of money. The total of a selection is honestly said in R.
             + f'<div class="tile"><div class="name">total R</div>'
             f'<div class="value">{s.sum_r:+.2f}</div>'
             f'<div class="sub">average {s.average_r:+.2f} R</div></div></div>')
    today = datetime.now().strftime("%Y-%m-%d")
    right = ('<a class="btn primary" href="/new">+ Trade</a>'
             f'<a class="btn" href="/card/{today}">+ Card</a>'
             '<a class="btn" href="/reports">Build report</a>')
    head = (f'<div class="card-head"><h2>Trades</h2>'
            f'<span class="right">{filters_box(j, q)}'
            f'{group_switch(q, group)}</span></div>')
    body = (account_tiles(j) + open_positions(j) + tiles +
            '<div class="card">' + head +
            trades_table(j, trades, group) + "</div>")
    return H.page("Journal", body, "journal", right)


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
              ("risk", f"{t.risk:g}% = {H.money(computed.risk_money)} $"),
              ("balance at entry", f"{H.money(computed.balance_at_entry)} $"),
              ("entry", f"{t.opened:%d.%m.%Y %H:%M}" if t.opened_time
               else f"{t.opened:%d.%m.%Y}"),
              ("exit", f"{t.closed:%d.%m.%Y}" if t.closed else "-"),
              ("result", t.result or "position open"),
              ("PnL", f"{H.money(t.pnl, signed=True)} $" if t.pnl is not None else "-"),
              ("R", f"{r:+.2f}" if r is not None else "-")]
    table = "".join(f'<tr><td class="muted">{esc(k)}</td><td>{esc(v)}</td></tr>'
                    for k, v in fields)
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
    return H.page(t.id, body, "journal", buttons)


# --- statistics ------------------------------------------------------------

def account_tabs(j, q, selected):
    """The account switch above the chart. It reuses the account filter, so the
    choice also applies to the tables below."""
    parts = []
    for code, name in [("", "All accounts")] + [(a, j.accounts[a].name or a)
                                                for a in sorted(j.accounts)]:
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


def stats_page(q):
    j = journal()
    trades = apply_filters(j, q)
    selected = (q.get("account") or [""])[0]

    # One account gets a large chart with its own scale: you see the swings, not
    # a flat line. All accounts get a picture each: their magnitudes differ, and
    # on one scale the small moves of a small account vanish next to a 100k prop.
    if selected and selected in j.accounts:
        points = stats.equity(j, selected, trades)
        name = j.accounts[selected].name or selected
        charts = (f'<div class="card"><h2>Equity: {esc(name)}</h2>'
                  f'{account_tabs(j, q, selected)}'
                  f'{H.equity_svg([(name, H.SERIES[0], points)], height=300, cid="acc")}'
                  f'</div>')
    else:
        cards = ""
        for i, a in enumerate(sorted(j.accounts)):
            points = stats.equity(j, a, trades)
            if not points:
                continue
            name = j.accounts[a].name or a
            cards += (f'<h3>{esc(name)}</h3>'
                      f'{H.equity_svg([(name, H.SERIES[i % len(H.SERIES)], points)], height=190, cid=f"acc-{i}")}')
        charts = (f'<div class="card"><h2>Equity by account</h2>'
                  f'{account_tabs(j, q, "")}'
                  f'{cards or "<p class=\'muted\'>Nothing to plot yet.</p>"}'
                  f'<p class="caption">Each account has its own scale, which is '
                  f'why they are drawn separately.</p></div>')

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
                   f'<th class="num">Σ $</th></tr></thead><tbody>{rows}</tbody>'
                   f'</table>'
                   f'<p class="caption">WR is wins against wins + losses; '
                   f'break-even trades are not in it, their weight is in R. '
                   f'"trades" and average R count every closed trade.</p>'
                   f'</div>')

    body = (filter_form(j, q).replace('action="/"', 'action="/stats"')
            + charts
            + f'<div class="card"><h2>R distribution</h2>'
            f'{H.histogram_svg(stats.r_distribution(j, trades))}'
            f'<p class="caption">Losses on the left, profits on the right. Under each '
            f'bar is the R value of that step.</p></div>' + slices)
    return H.page("Statistics", body, "stats")


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


def select(name, values, current="", empty=None):
    options = f'<option value="">{esc(empty)}</option>' if empty else ""
    options += "".join(
        f'<option value="{esc(v)}"{" selected" if v == current else ""}>'
        f'{esc(v)}</option>' for v in values)
    return f'<select name="{name}">{options}</select>'


def shot_in_zone(trade_id, path, field):
    """A thumbnail of an already saved screenshot, with a cross.

    The cross simply removes the node from the form, and together with the
    hidden field that is what keeps the screenshot in the trade."""
    return (f'<span class="shot">'
            f'<img src="/shot/{U(trade_id)}/{U(os.path.basename(path))}" '
            f'alt="screenshot">'
            f'<button type="button" class="remove" title="remove screenshot">'
            f'&times;</button>'
            f'<input type="hidden" name="{field}" value="{esc(path)}"></span>')


def dropzone(name, hint, shots=()):
    return (f'<div class="dropzone" data-zone="{esc(name)}">{"".join(shots)}'
            f'<div class="hint">{esc(hint)}</div></div>')


def idea_form_block(n, tf="", text="", existing=(), trade_id=None):
    return ('<div class="form-block card">'
            + block_inside(n, tf, text, existing, trade_id) + "</div>")


def block_inside(n, tf="", text="", existing=(), trade_id=None):
    old = [shot_in_zone(trade_id, s, f"have_idea-{n}") for s in existing]
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
        f'{" checked" if v in chosen else ""}> {esc(v)}</label>' for v in EXECUTION)
    pair_list = "".join(f'<option value="{esc(p)}">' for p in pairs)

    if editing and t.idea:
        blocks = ""
        for i, b in enumerate(t.idea, 1):
            blocks += idea_form_block(i, b.tf, b.text, b.images, t.id)
        count = len(t.idea)
    else:
        blocks = idea_form_block(1)
        count = 1

    action = f"/edit/{U(t.id)}" if editing else "/new"
    title = "Edit trade" if editing else "New trade"
    # For a closed trade the exit and the conclusions are edited here too,
    # or editing the idea would wipe their screenshots: the shots folder is
    # rewritten from whatever the form sent.
    closing = ""
    if editing and not t.is_open:
        closing = f"""<input type="hidden" name="closed" value="1">
<div class="card"><h2>Exit moment</h2>
{dropzone("exit", "click here and press Ctrl+V",
          [shot_in_zone(t.id, s, "have_exit") for s in t.exit_images])}</div>
<div class="card"><h2>Conclusions</h2>
<textarea name="conclusions">{esc(conclusions_text(t.conclusions))}</textarea>
{dropzone("concl", "screenshots for conclusions, Ctrl+V here",
          [shot_in_zone(t.id, s, "have_concl")
           for s in conclusion_images(t.conclusions)])}</div>"""
    return f"""<form method="post" action="{action}">
<input type="hidden" name="token" value="{esc(token)}">
<input type="hidden" name="blocks" value="{count}">
<div class="card"><h2>{title}</h2>
<div class="fields">
<div class="field"><label>account</label>
{select("account", accounts, t.account if editing else "")}</div>
<div class="field"><label>pair</label>
<input type="text" name="pair" list="pairs" value="{esc(t.pair if editing else "")}"
 placeholder="EURUSD" required><datalist id="pairs">{pair_list}</datalist></div>
<div class="field"><label>direction</label>
{select("direction", DIRECTIONS, t.direction if editing else "")}</div>
<div class="field"><label>style</label>
{select("style", NEW_STYLES if not editing else sorted({*NEW_STYLES, t.style}),
        t.style if editing else "")}</div>
<div class="field"><label>entry TF</label>
{select("entry_tf", TIMEFRAMES, t.entry_tf if editing else "", empty="-")}</div>
<div class="field"><label>risk, %</label>
<input type="number" name="risk" step="0.05" min="0.05" style="width:90px"
 value="{t.risk if editing else 1}"></div>
<div class="field"><label>entry</label>
<input type="datetime-local" name="entry" value="{entry}"
 onclick="this.showPicker && this.showPicker()"></div>
</div>
<p class="caption" style="margin:8px 0 0">execution: {checkboxes}</p>
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


def close_form(t, token):
    exit_shots = [shot_in_zone(t.id, s, "have_exit") for s in t.exit_images]
    concl_shots = [shot_in_zone(t.id, s, "have_concl")
                   for s in conclusion_images(t.conclusions)]
    return f"""<form method="post" action="/close/{U(t.id)}">
<input type="hidden" name="token" value="{esc(token)}">
<div class="card"><h2>Close trade {esc(t.id)}</h2>
<div class="fields">
<div class="field"><label>result</label>
{select("result", RESULTS, t.result or "")}</div>
<div class="field"><label>PnL, $</label>
<input type="number" name="pnl" step="0.01" style="width:130px"
 value="{t.pnl if t.pnl is not None else ""}" required></div>
<div class="field"><label>exit date</label>
<input type="date" name="exit" value="{(t.closed or datetime.now()):%Y-%m-%d}"
 onclick="this.showPicker && this.showPicker()"></div>
</div>
<p class="caption">Risk was {t.risk:g}% = {H.money(journal().computed[t.id].risk_money)} $.
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


def zone_sources(data, zone, t, token):
    """Image paths for a zone: the old ones kept plus the new ones pasted."""
    removed = set(data.get("remove", []))
    paths = []
    for s in data.get("have_" + zone, []):
        if s in removed:
            continue
        paths.append(os.path.join(store.trade_dir(ROOT, t.id), s))
    for name in data.get("file_" + zone, []):
        if _FILE_NAME.match(name):
            paths.append(os.path.join(draft_dir(token), name))
    return [p for p in paths if os.path.exists(p)]


def apply_shots(t, zones):
    """Rewrites the shots folder whole, so no leftovers from editing stay behind."""
    folder = store.shots_dir(ROOT, t.id)
    fresh = folder + ".new"
    shutil.rmtree(fresh, ignore_errors=True)
    os.makedirs(fresh, exist_ok=True)
    result = {}
    for zone, sources in zones.items():
        prefix = ("exit" if zone == "exit" else "conclusions" if zone == "concl"
                  else f"idea-{int(zone.split('-')[1]):02d}")
        names = []
        for i, src in enumerate(sources, 1):
            name = f"{prefix}-{i:02d}{os.path.splitext(src)[1] or '.png'}"
            shutil.copyfile(src, os.path.join(fresh, name))
            names.append(os.path.join(store.SHOTS, name))
        result[zone] = names
    shutil.rmtree(folder, ignore_errors=True)
    os.replace(fresh, folder)
    return result


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
    t.pair = one(data, "pair") or PAIR_NOT_SET
    t.direction = one(data, "direction")
    t.style = one(data, "style")
    t.entry_tf = one(data, "entry_tf")
    t.execution = data.get("execution", [])
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


def create_trade(data):
    token = one(data, "token")
    entry = datetime.strptime(one(data, "entry"), "%Y-%m-%dT%H:%M")
    pair = one(data, "pair") or PAIR_NOT_SET
    t = Trade(id=store.new_id(ROOT, entry, pair), account="")
    apply_fields(t, data)
    zones, t.idea = {}, []
    for n, block in blocks_from_form(data):
        paths = [os.path.join(draft_dir(token), name)
                 for name in data.get(f"file_idea-{n}", []) if _FILE_NAME.match(name)]
        if not (block.text.strip() or paths):
            continue
        zones[f"idea-{len(t.idea)+1}"] = [p for p in paths if os.path.exists(p)]
        t.idea.append(block)
    t.check()
    names = apply_shots(t, zones)
    for i, block in enumerate(t.idea, 1):
        block.images = names.get(f"idea-{i}", [])
    store.save_trade(ROOT, t)
    drop_draft(token)
    drop_cache()
    return t


def edit_trade(t, data):
    token = one(data, "token")
    apply_fields(t, data)
    zones, kept = {}, []
    for n, block in blocks_from_form(data):
        paths = zone_sources(data, f"idea-{n}", t, token)
        if not (block.text.strip() or paths):
            continue
        zones[f"idea-{len(kept)+1}"] = paths
        kept.append(block)
    # The exit and the conclusions only come from the form of a closed trade.
    # If they were not in the form, keep them as they are: empty zones would
    # wipe the screenshots off the disk.
    editing_close = one(data, "closed") == "1"
    if editing_close:
        zones["exit"] = zone_sources(data, "exit", t, token)
        zones["concl"] = zone_sources(data, "concl", t, token)
    else:
        own = os.path.join(store.trade_dir(ROOT, t.id), "{}")
        zones["exit"] = [own.format(s) for s in t.exit_images]
        zones["concl"] = [own.format(s)
                          for s in conclusion_images(t.conclusions)]
    t.idea = kept
    t.check()
    names = apply_shots(t, zones)
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


def close_trade(t, data):
    token = one(data, "token")
    t.result = one(data, "result")
    t.pnl = float(one(data, "pnl", "0").replace(",", "."))
    t.closed = datetime.strptime(one(data, "exit"), "%Y-%m-%d")
    conclusions = one(data, "conclusions")
    zones = {f"idea-{i}": [os.path.join(store.trade_dir(ROOT, t.id), s)
                           for s in b.images] for i, b in enumerate(t.idea, 1)}
    zones["exit"] = zone_sources(data, "exit", t, token)
    zones["concl"] = zone_sources(data, "concl", t, token)
    t.check()
    names = apply_shots(t, zones)
    for i, block in enumerate(t.idea, 1):
        block.images = names.get(f"idea-{i}", [])
    t.exit_images = names.get("exit", [])
    t.conclusions = build_conclusions(conclusions, names.get("concl", []))
    store.save_trade(ROOT, t)
    drop_draft(token)
    drop_cache()
    return t


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


def day_pnl(j, day):
    """What the day gave by closed trades, offered in a new card."""
    return sum(t.pnl or 0.0 for t in j.trades
               if not t.is_open and t.closed and t.closed.date() == day.date())


def cards_page():
    cards = store.all_cards(ROOT)
    today = datetime.now().strftime("%Y-%m-%d")
    right = f'<a class="btn primary" href="/card/{today}">+ Card</a>'
    if not cards:
        body = ('<div class="card"><h2>Daily report cards</h2>'
                '<p class="muted">No cards yet. The button above opens '
                'today&rsquo;s card.</p></div>')
        return H.page("Cards", body, "cards", right)
    rows = "".join(
        f'<tr><td><a href="/card/{U(k.id)}">{k.day:%d.%m.%Y}</a></td>'
        f'<td>{esc(k.grade) or "-"}</td>'
        f'<td class="num {sum_class(k.pnl or 0)}">'
        f'{H.money(k.pnl, signed=True) if k.pnl is not None else "-"}</td>'
        f'<td>{esc(k.quality) or "-"}</td>'
        f'<td class="muted">{esc(first_line(k.overview or k.focus))}</td></tr>'
        for k in cards)
    body = (f'<div class="card"><h2>Daily report cards</h2>'
            f'<table><thead><tr><th>date</th><th>process</th>'
            f'<th class="num">P&amp;L $</th><th>opportunity</th><th>overview</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>')
    return H.page("Cards", body, "cards", right)


def first_line(text, limit=90):
    line = (text or "").strip().split("\n")[0]
    return line if len(line) <= limit else line[:limit - 1] + "…"


def card_page(day):
    j = journal()
    k = store.load_card(ROOT, day)
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
<div class="field"><label>P&amp;L, $</label>
<input type="number" name="pnl" step="0.01" style="width:130px"
 value="{"" if k.pnl is None else f"{k.pnl:g}"}"></div>
<div class="field"><label>opportunity quality</label>
<input type="text" name="quality" list="grades" value="{esc(k.quality)}"
 placeholder="B" style="width:150px"></div>
</div>
<p class="caption">P&amp;L for the day by closed trades:
{H.money(day_pnl(j, day), signed=True)} $. The field is yours to override.</p>
</div>
<div class="card">{sections}</div>
<div class="actions"><button class="btn primary">Save card</button>
<a class="btn" href="/cards">Cancel</a>{delete}</div>
</form>"""
    return H.page(f"Card {day:%d.%m.%Y}", body, "cards")


def save_card(data):
    day = day_from_url(one(data, "date"))
    previous = one(data, "previous")
    k = Card(day=day, grade=one(data, "grade"), quality=one(data, "quality"))
    pnl = one(data, "pnl")
    k.pnl = float(pnl.replace(",", ".")) if pnl else None
    for name, _, _ in CARD_SECTIONS:
        setattr(k, name, one(data, name))
    old = store.load_card(ROOT, day)
    if old is not None:
        k.extra = old.extra
    store.save_card(ROOT, k)
    # the date was changed in the form, which is a rename, not a second card
    if previous and previous != k.id:
        store.delete_card(ROOT, day_from_url(previous))
    return k


# --- reports ---------------------------------------------------------------

def md_to_html(text):
    """A tiny renderer: we generate the reports ourselves, their markup is simple."""
    parts, in_table, section = [], False, ""
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if not in_table:
                parts.append("<table><tbody>")
                in_table = True
            # under "By pair" the first column holds symbols, so they get their
            # icons here, the same as everywhere else
            show = H.pair if section == "By pair" else esc
            parts.append("<tr>" + "".join(
                f'<td class="{"num" if i else ""}">{(esc if i else show)(c)}</td>'
                for i, c in enumerate(cells)) + "</tr>")
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
    return H.page("Reports", body, "reports")


def report_kind(period):
    return "quarter" if "Q" in period else "month"


def report_page(period):
    head, body = reports.read(ROOT, period)
    if body is None:
        return None
    conclusions = reports.previous_conclusions(ROOT, period)
    without = re.split(r"^## Conclusions\s*$", body, maxsplit=1, flags=re.M)[0]
    form = f"""<form method="post" action="/report/{U(period)}">
<textarea name="conclusions" placeholder="What you learned this period">{esc(conclusions)}</textarea>
<p><button class="btn primary">Save conclusions</button>
<button class="btn" name="rebuild" value="1">Recalculate</button></p></form>"""
    html = (f'<div class="card">{md_to_html(without)}'
            f'<p class="caption">updated {esc(head.get("updated", ""))}</p></div>'
            f'<div class="card"><h2>Conclusions</h2>{form}</div>')
    return H.page(period, html, "reports",
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
        rows.append(
            f'<tr><td>{esc(account.name or a)}<div class="caption">{esc(a)}</div></td>'
            f'<td class="num">{H.money(account.start_balance)} $</td>'
            f'<td class="num">{H.money(j.balance(a))} $</td>'
            f'<td class="num">{trades}</td>'
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

    top = (f'<div class="card"><p>{esc(message)}</p></div>' if message else "")
    body = f"""{top}
<div class="card"><h2>Accounts</h2>
<table><thead><tr><th>account</th><th class="num">start</th><th class="num">current</th>
<th class="num">trades</th><th>status</th><th></th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<p class="caption">An account with trades cannot be deleted, archive it instead.
Archived accounts stay in history and statistics but are not offered when opening
a trade.</p></div>

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
<div><button class="btn primary">Create account</button></div>
</form>
<p class="caption">id is used in file names: latin letters, digits and dashes.</p></div>

<div class="card"><h2>Trading pairs</h2>
<form method="post" action="/pair/new" class="filters">
<div><label>pair</label><input type="text" name="pair" placeholder="EURJPY"
 required style="width:130px"></div>
<div><button class="btn primary">Add pair</button></div>
</form>
<table><thead><tr><th>pair</th><th>source</th><th></th></tr></thead>
<tbody>{pair_rows}</tbody></table>
<p class="caption">Removing a pair only takes it out of the suggestion list;
trades already recorded with it are not touched.</p></div>"""
    return H.page("Accounts", body, "accounts")


def create_account(data):
    account_id = one(data, "id").lower()
    if not _ACCOUNT_ID.match(account_id):
        raise RecordError("account id: latin letters, digits and dashes only")
    if account_id in journal(True).accounts:
        raise RecordError(f"account {account_id} already exists")
    store.save_account(ROOT, Account(
        id=account_id, name=one(data, "name") or account_id,
        start_balance=float(one(data, "start", "0").replace(",", ".")),
        currency=one(data, "currency", "USD") or "USD"))
    drop_cache()
    return f"Account {account_id} created."


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
    return f"Account {account_id} deleted."


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


# --- HTTP ------------------------------------------------------------------

def U(s):
    return urllib.parse.quote(str(s), safe="")


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "Plainbook"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass                                   # quiet: a server log is not needed

    # --- responses ---
    def _send(self, text, code=200, kind="text/html; charset=utf-8"):
        data = text.encode("utf-8") if isinstance(text, str) else text
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _go(self, where):
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
        return not origin or origin.startswith(f"http://127.0.0.1:{PORT}") \
            or origin.startswith(f"http://localhost:{PORT}")

    # --- routes ---
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        q = urllib.parse.parse_qs(parsed.query)
        parts = [c for c in path.split("/") if c]

        if path == "/":
            return self._send(home_page(q))
        if path == "/stats":
            return self._send(stats_page(q))
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
        if path == "/accounts":
            return self._send(accounts_page((q.get("m") or [""])[0]))
        if path == "/open-count":
            return self._send(str(len(journal().open_trades())), 200,
                              "text/plain; charset=utf-8")
        if len(parts) == 2 and parts[0] == "trade":
            page = trade_page(parts[1])
            return self._send(page or "no such trade", 200 if page else 404)
        if len(parts) == 2 and parts[0] == "report":
            page = report_page(parts[1])
            return self._send(page or "no such report", 200 if page else 404)
        if path == "/new":
            return self._send(H.page("New trade", trade_form(None, new_token()),
                                     "journal"))
        if len(parts) == 2 and parts[0] in ("edit", "close"):
            t = next((x for x in journal().trades if x.id == parts[1]), None)
            if t is None:
                return self._send("no such trade", 404)
            token = new_token()
            body = (trade_form(t, token) if parts[0] == "edit"
                    else close_form(t, token))
            return self._send(H.page(t.id, body, "journal"))
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
                return self._go(f"/trade/{U(t.id)}")
            if len(parts) == 2 and parts[0] == "edit":
                t = next((x for x in journal(True).trades if x.id == parts[1]), None)
                if t is None:
                    return self._send("no such trade", 404)
                edit_trade(t, data)
                return self._go(f"/trade/{U(t.id)}")
            if path == "/card/save":
                k = save_card(data)
                return self._go(f"/card/{U(k.id)}")
            if len(parts) == 3 and parts[0] == "card" and parts[2] == "delete":
                store.delete_card(ROOT, day_from_url(parts[1]))
                return self._go("/cards")
            if len(parts) == 3 and parts[0] == "trade" and parts[2] == "delete":
                if next((x for x in journal(True).trades if x.id == parts[1]),
                        None) is None:
                    return self._send("no such trade", 404)
                store.delete_trade(ROOT, parts[1])
                drop_cache()
                return self._go("/")
            if len(parts) == 2 and parts[0] == "close":
                t = next((x for x in journal(True).trades if x.id == parts[1]), None)
                if t is None:
                    return self._send("no such trade", 404)
                close_trade(t, data)
                return self._go(f"/trade/{U(t.id)}")
            for route, action in (("/account/new", create_account),
                                  ("/account/archive", toggle_archive),
                                  ("/account/delete", delete_account),
                                  ("/pair/new", add_pair),
                                  ("/pair/delete", remove_pair)):
                if path == route:
                    # Accounts and pairs report back on their own page rather
                    # than on a separate error page: you stay where you were.
                    try:
                        message = action(data)
                    except (RecordError, ValueError) as e:
                        message = str(e)
                    return self._go("/accounts?m=" + U(message))
            if path == "/report/build":
                what = one(data, "what", "month")
                period = one(data, f"period_{what}")
                if not period:
                    return self._go("/reports")
                reports.build(ROOT, journal(True), period)
                return self._go(f"/report/{U(period)}")
            if len(parts) == 2 and parts[0] == "report":
                conclusions = one(data, "conclusions")
                reports.build(ROOT, journal(True), parts[1], conclusions=conclusions)
                return self._go(f"/report/{U(parts[1])}")
        except (RecordError, ValueError) as e:
            return self._send(H.page("Error", f'<div class="card">'
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
