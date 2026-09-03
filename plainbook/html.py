#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Page rendering. Everything is offline: no external file, styles and scripts inline.

A strict dark theme: a near-black ground, one blue accent, muted green and red
for money only. The series colours on the charts come from a palette that has
been checked for colour blindness on a dark surface.
"""
import html as _html
import json
import math
from datetime import timedelta

from . import flags

# --- palette ---------------------------------------------------------------
GROUND = "#0a0a0b"         # page background
SURFACE = "#121214"        # cards and tables
RAISED = "#191a1d"         # table head, group rows
INK = "#ececee"
INK2 = "#a3a3a9"
DIM = "#6a6a71"
GRID = "#1e1f22"
AXIS = "#2b2c30"
EDGE = "rgba(255,255,255,0.07)"
ACCENT = "#6f9dff"
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500"]
GOOD = "#48ac7a"
BAD = "#d05c55"
WARN = "#d9a441"
# The rings of the R distribution. One hue per ring with steps that get
# brighter as R grows, so the order of the buckets is visible in the colour
# itself and not only in the legend. Checked against the card surface: every
# step clears 3:1 contrast and stays colourful enough not to read as grey.
LOSS_STEPS = ["#9c4741", "#c56158", "#ef8b81", "#ffb7aa"]
WIN_STEPS = ["#2a7d55", "#37996a", "#4ab882", "#66d29c", "#93e6bd"]

MONO = ('ui-monospace,"JetBrains Mono","CaskaydiaMono Nerd Font",'
        'SFMono-Regular,Menlo,Consolas,monospace')

CSS = f"""
*{{box-sizing:border-box}}
/* the date picker and the select drop-downs are drawn by the browser itself:
   only color-scheme makes them dark, no stylesheet can reach them */
:root{{color-scheme:dark}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:{GROUND};color:{INK};
 font:13px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
 -webkit-font-smoothing:antialiased}}
a{{color:{ACCENT};text-decoration:none}}
a:hover{{color:#9ab9ff}}
.wrap{{max-width:1460px;margin:0 auto;padding:0 20px 56px}}

/* header */
header{{display:flex;align-items:center;gap:22px;flex-wrap:wrap;
 position:sticky;top:0;z-index:8;background:{GROUND};
 border-bottom:1px solid {EDGE};padding:12px 0 10px;margin-bottom:18px}}
header .logo{{font-weight:600;letter-spacing:.04em;font-size:13px;
 text-transform:uppercase;color:{INK}}}
header .logo:hover{{color:{ACCENT}}}
header nav{{display:flex;gap:2px}}
header nav a{{color:{DIM};padding:4px 9px;border-radius:4px;
 font-size:12px;letter-spacing:.02em}}
header nav a:hover{{color:{INK2};background:{SURFACE}}}
header nav a.current{{color:{INK};background:{RAISED}}}
header .right{{margin-left:auto;display:flex;gap:7px;align-items:center}}

/* buttons */
.btn{{display:inline-block;background:transparent;border:1px solid {AXIS};
 color:{INK2};padding:5px 11px;border-radius:4px;cursor:pointer;
 font:12px/1.4 system-ui,sans-serif;letter-spacing:.01em;white-space:nowrap}}
.btn:hover{{border-color:{DIM};color:{INK};text-decoration:none}}
.btn.primary{{background:{ACCENT};border-color:{ACCENT};color:#07080c;
 font-weight:600}}
.btn.primary:hover{{background:#8ab0ff;border-color:#8ab0ff;color:#07080c}}
.btn.danger{{border-color:rgba(208,92,85,.45);color:{BAD}}}
.btn.danger:hover{{border-color:{BAD};color:#fff;background:rgba(208,92,85,.16)}}

/* filters behind a funnel button */
.filters-box{{display:inline-block}}
.filters-box > summary{{list-style:none;display:inline-flex;align-items:center;gap:6px}}
.filters-box > summary::-webkit-details-marker{{display:none}}
.filters-box > summary::marker{{content:""}}
.btn.icon{{padding:5px 9px;line-height:0}}
.btn.active,.filters-box[open] > summary{{border-color:{ACCENT};color:{INK}}}
.badge{{font:600 10px/1 {MONO};color:#07080c;background:{ACCENT};
 border-radius:7px;padding:2px 5px}}
/* The popover hangs off the card head, not off the button: measured from the
   button it ran to the right and slid past the left edge of a narrow window.
   From the head it is exactly as wide as the list and always fits. */
.popover{{position:absolute;left:0;right:0;top:calc(100% + 2px);z-index:6;
 background:{RAISED};border:1px solid {AXIS};border-radius:5px;padding:13px 15px;
 box-shadow:0 10px 28px rgba(0,0,0,.5)}}

/* period switch: segments inside one frame */
.switch{{display:inline-flex;border:1px solid {AXIS};border-radius:4px;
 overflow:hidden}}
.switch a{{padding:4px 12px;font-size:12px;color:{DIM};
 border-right:1px solid {AXIS};letter-spacing:.02em}}
.switch a:last-child{{border-right:none}}
.switch a:hover{{color:{INK};background:{SURFACE}}}
.switch a.current{{color:{INK};background:{RAISED};font-weight:600}}

/* tiles */
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(184px,1fr));
 gap:1px;background:{EDGE};border:1px solid {EDGE};border-radius:5px;
 overflow:hidden;margin-bottom:16px}}
/* accounts are not stretched across the screen: there are two of them, and a
   full-width strip would read as an empty table */
.tiles.narrow{{display:flex;flex-wrap:wrap;width:fit-content;max-width:100%}}
.tiles.narrow .tile{{min-width:236px;flex:0 0 auto}}
.tile{{background:{SURFACE};padding:11px 14px 12px}}
.tile .name{{color:{DIM};font-size:10px;text-transform:uppercase;
 letter-spacing:.09em}}
.tile .value{{font:600 22px/1.15 {MONO};margin-top:5px;
 font-variant-numeric:tabular-nums;letter-spacing:-.01em}}
.tile .sub{{color:{INK2};font-size:11px;margin-top:4px}}
/* a tile that asks for attention: the daily limit of a prop account is close */
.tile.warn{{box-shadow:inset 3px 0 0 {WARN}}}
.tile.warn .value{{color:{WARN}}}
.tile.over{{box-shadow:inset 3px 0 0 {BAD}}}
.tile.over .value{{color:{BAD}}}

/* records that could not be read: said once, at the top of every page */
.notice{{background:rgba(217,164,65,.08);border:1px solid rgba(217,164,65,.4);
 border-radius:5px;padding:10px 14px;margin-bottom:16px;font-size:12px}}
.notice b{{color:{WARN}}}
.notice ul{{margin:6px 0 0;padding-left:18px}}
.notice code{{font-family:{MONO};font-size:11px;color:{INK2}}}

/* cards */
.card{{background:{SURFACE};border:1px solid {EDGE};border-radius:5px;
 padding:14px 16px;margin-bottom:16px}}
h2{{font-size:10px;margin:0 0 12px;color:{DIM};font-weight:600;
 text-transform:uppercase;letter-spacing:.11em}}
h3{{font-size:10px;margin:16px 0 6px;color:{DIM};font-weight:600;
 text-transform:uppercase;letter-spacing:.09em}}
.card > h3:first-child{{margin-top:0}}
.card-head{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;
 margin-bottom:12px;position:relative}}
.card-head h2{{margin:0}}
.card-head .right{{margin-left:auto}}

/* tables */
table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}
th{{text-align:left;color:{DIM};font-weight:500;font-size:10px;
 text-transform:uppercase;letter-spacing:.09em;padding:7px 10px;
 background:{SURFACE};border-bottom:1px solid {AXIS};
 position:sticky;top:49px;z-index:2}}
td{{padding:6px 10px;border-bottom:1px solid {GRID}}}
/* there are many links in the table, so they are painted as text and the accent
   is kept for hovering */
td a{{color:{INK}}}
td a:hover{{color:{ACCENT}}}
tbody tr:hover td{{background:rgba(255,255,255,.028)}}
/* a row of the journal is one big link: the cell keeps the colour it was given
   and hands its padding to the link, so the whole row answers a click */
td.cell{{padding:0}}
td.cell>a{{display:block;padding:6px 10px;color:inherit}}
td.cell>a:hover{{color:inherit}}
td.num,th.num{{text-align:right;white-space:nowrap}}
td.num{{font-family:{MONO};font-size:12px}}
tr.group td{{background:{RAISED};color:{INK2};
 border-top:1px solid {AXIS};border-bottom:1px solid {AXIS};
 padding:7px 10px;font-size:11px;white-space:nowrap}}
tr.group:hover td{{background:{RAISED}}}
/* colour of the weekly total: the class alone loses to the group row rule */
tr.group td.win{{color:{GOOD}}}
tr.group td.lose{{color:{BAD}}}
tr.group .label{{color:{INK};font-weight:600;letter-spacing:.04em}}
tr.group .dates{{color:{DIM};margin-left:8px}}
.win{{color:{GOOD}}} .lose{{color:{BAD}}} .flat{{color:{INK2}}}
/* in the winrate tile the three numbers say what they are by colour alone */
.be{{color:{WARN}}}
.tile .sub .breakdown{{font-family:{MONO};font-size:12px}}
.muted{{color:{DIM}}}

/* forms */
form.filters{{display:flex;gap:9px;flex-wrap:wrap;align-items:flex-end}}
label{{display:block;color:{DIM};font-size:10px;margin-bottom:4px;
 text-transform:uppercase;letter-spacing:.09em}}
select,input[type=text],input[type=number],input[type=date],
input[type=week],input[type=datetime-local],textarea{{background:{GROUND};color:{INK};
 border:1px solid {AXIS};border-radius:4px;padding:6px 8px;
 font:13px system-ui,sans-serif}}
input[type=number],input[type=date],input[type=week],
input[type=datetime-local]{{font-family:{MONO};font-size:12px}}
select:hover,input:hover{{border-color:{DIM}}}
input[type=checkbox]{{accent-color:{ACCENT};vertical-align:-2px}}
select:focus,input:focus,textarea:focus{{outline:none;border-color:{ACCENT};
 box-shadow:0 0 0 2px rgba(111,157,255,.18)}}
textarea{{width:100%;min-height:78px;resize:vertical;line-height:1.55}}
.fields{{display:flex;gap:14px;flex-wrap:wrap}}
.field{{min-width:150px}}
.actions{{display:flex;gap:8px;align-items:center;margin:16px 0 0}}
.actions .right{{margin-left:auto}}

/* what the journal answers after a form: in the middle, and gone by itself.
   Pure CSS, because a message that needs a script is a message that can fail */
.toast{{position:fixed;left:50%;top:50%;z-index:40;pointer-events:none;
 background:{RAISED};border:1px solid {AXIS};border-left:2px solid {ACCENT};
 border-radius:6px;padding:13px 22px;color:{INK};font-size:14px;
 letter-spacing:.02em;white-space:nowrap;
 box-shadow:0 18px 46px rgba(0,0,0,.66);
 animation:said 1.15s cubic-bezier(.2,.8,.2,1) forwards}}
@keyframes said{{
 0%{{opacity:0;transform:translate(-50%,calc(-50% + 8px)) scale(.94)}}
 14%{{opacity:1;transform:translate(-50%,-50%) scale(1)}}
 68%{{opacity:1;transform:translate(-50%,-50%) scale(1)}}
 100%{{opacity:0;transform:translate(-50%,calc(-50% - 12px)) scale(.98)}}}}
/* a message that flies is still a message: with motion turned off it simply
   stands and goes */
@media (prefers-reduced-motion: reduce){{
 .toast{{animation:said-plain 1.15s steps(1) forwards;
  transform:translate(-50%,-50%)}}
 @keyframes said-plain{{0%{{opacity:1}} 92%{{opacity:1}} 100%{{opacity:0}}}}}}

/* screenshot drop zones */
.dropzone{{border:1px dashed {AXIS};border-radius:5px;padding:10px;min-height:62px;
 color:{DIM};font-size:11px;margin-top:8px;
 display:flex;flex-wrap:wrap;gap:8px;align-items:flex-start}}
.dropzone:focus{{outline:none;border-color:{ACCENT};color:{INK2}}}
.dropzone .hint{{flex-basis:100%;order:9;letter-spacing:.02em}}
.shot{{position:relative;display:inline-block;line-height:0}}
.shot img{{max-width:186px;max-height:118px;border:1px solid {AXIS};
 border-radius:4px;display:block}}
.shot .remove{{position:absolute;top:4px;right:4px;width:19px;height:19px;
 border:none;border-radius:3px;background:rgba(10,10,11,.82);color:{INK2};
 font:14px/1 system-ui,sans-serif;cursor:pointer;padding:0;
 display:flex;align-items:center;justify-content:center}}
.shot .remove:hover{{background:{BAD};color:#fff}}

/* trade page */
.shots img{{max-width:100%;border:1px solid {EDGE};border-radius:5px;
 margin:8px 0;display:block}}
.idea-block{{border-left:2px solid {AXIS};padding-left:12px;margin-bottom:16px}}
.idea-block:last-child{{margin-bottom:0}}
.is-open{{border-left:2px solid {WARN}}}
.props{{max-width:660px}}
.props td:first-child{{width:190px;color:{DIM}}}
.caption{{color:{DIM};font-size:11px}}
mark{{background:rgba(111,157,255,.28);color:inherit;border-radius:2px}}
.caption a{{color:{INK2}}}

/* trading pairs: two round flags before the name, as a terminal draws them */
.sprite{{position:absolute;width:0;height:0;overflow:hidden}}
.pair{{display:inline-flex;align-items:center;gap:7px;white-space:nowrap}}
.pair .pi{{flex:none;display:block}}

/* charts */
.legend{{display:flex;gap:16px;flex-wrap:wrap;margin:8px 0 0;font-size:11px;
 color:{INK2}}}
.legend i{{display:inline-block;width:8px;height:8px;border-radius:2px;
 margin-right:6px}}

/* a field with its own list of options: the flags cannot live in the list the
   browser draws */
.picker{{position:relative}}
.picker .options{{position:absolute;z-index:7;top:calc(100% + 3px);left:0;
 min-width:100%;max-height:280px;overflow-y:auto;background:{RAISED};
 border:1px solid {AXIS};border-radius:5px;padding:3px;
 box-shadow:0 10px 26px rgba(0,0,0,.5)}}
.picker .option{{display:block;width:100%;text-align:left;background:none;
 border:none;color:{INK};padding:5px 8px;border-radius:4px;cursor:pointer;
 font:13px/1.4 system-ui,sans-serif;white-space:nowrap}}
.picker .option:hover,.picker .option.at{{background:{SURFACE};color:{INK}}}

/* a block that opens on a click: the forms are needed rarely, the page is
   read often */
.fold{{margin-bottom:12px}}
.fold:last-of-type{{margin-bottom:0}}
.fold>summary{{display:flex;align-items:center;gap:10px;cursor:pointer;
 list-style:none;border:1px solid {AXIS};border-radius:4px;padding:7px 12px;
 color:{INK2};font-size:12px;user-select:none}}
.fold>summary:hover{{border-color:{DIM};color:{INK}}}
.fold[open]>summary{{border-color:{DIM};color:{INK};margin-bottom:12px}}
.fold>summary::-webkit-details-marker{{display:none}}
.fold>summary::before{{content:"+";color:{DIM};font-size:14px;line-height:1}}
.fold[open]>summary::before{{content:"−"}}
.fold>summary .caption{{margin-left:auto}}

/* the two rings of the R distribution */
.rings{{display:flex;flex-wrap:wrap;gap:14px}}
.ring{{flex:1 1 380px;min-width:300px;background:{GROUND};
 border:1px solid {EDGE};border-radius:8px;padding:14px 16px}}
.ring h3{{margin:0 0 10px;color:{DIM};font-size:10px;font-weight:500;
 text-transform:uppercase;letter-spacing:.09em}}
.ring-body{{display:flex;align-items:center;gap:18px;flex-wrap:wrap}}
.donut-legend{{flex:1 1 190px;width:auto;font-size:12px}}
.donut-legend td{{border-bottom:none;padding:3px 0 3px 10px}}
.donut-legend td:first-child{{padding-left:0;white-space:nowrap;color:{INK2}}}
.donut-legend i{{display:inline-block;width:9px;height:9px;border-radius:2px;
 margin-right:7px;vertical-align:baseline}}
.donut-legend tr{{cursor:default}}
.ring [data-slice]{{transition:opacity .12s ease}}
.ring.lit [data-slice]:not(.on){{opacity:.22}}
.ring.lit tr.on td{{background:rgba(255,255,255,.06)}}
.ring.lit tr.on td:first-child{{color:{INK}}}
.tip{{position:fixed;pointer-events:none;background:{RAISED};
 border:1px solid {AXIS};border-radius:4px;padding:6px 9px;font-size:11px;
 color:{INK};display:none;z-index:9;white-space:pre;
 font-family:{MONO};font-variant-numeric:tabular-nums}}
"""


class Safe(str):
    """Markup that is already built and must not be escaped again.

    It exists so that a value carrying an icon can travel through the same
    table-building code as a plain string."""


def esc(s):
    if isinstance(s, Safe):
        return s
    return _html.escape("" if s is None else str(s), quote=True)


def pair(name):
    """A trading pair with its coins: the icon plus the name."""
    icon = flags.icon(name)
    if not icon:
        return Safe(f'<span class="pair">{esc(name)}</span>')
    return Safe(f'<span class="pair">{icon}{esc(name)}</span>')


# the currencies that have a sign of their own; any other is written by its code
SIGNS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CHF": "₣", "RUB": "₽",
         "USDT": "$", "USDC": "$"}


def sign(currency):
    return SIGNS.get((currency or "").upper(), currency or "")


def money(x, signed=False):
    if x is None:
        return "-"
    text = f"{x:+,.0f}" if signed else f"{x:,.0f}"
    return text.replace(",", " ")


def page(title, body, tab="journal", header_right="", notice="", said=""):
    links = [("journal", "/", "Journal"), ("plans", "/plans", "Plans"),
             ("cards", "/cards", "Cards"), ("stats", "/stats", "Statistics"),
             ("reports", "/reports", "Reports"), ("accounts", "/accounts", "Accounts"),
             ("search", "/search", "Search")]
    nav = "".join(
        f'<a href="{href}" class="{"current" if code == tab else ""}">{name}</a>'
        for code, href, name in links)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{"Plainbook" if title == "Journal"
          else "Plainbook: " + esc(title)}</title><style>{CSS}</style>
<script>{HOVER}{PAGE_SCRIPT}</script></head><body>
{flags.SPRITE}{said}
<div class="wrap">
<header><a href="/" class="logo" title="the journal">Plainbook</a><nav>{nav}</nav>
<span class="right">{header_right}</span></header>
{notice}{body}
</div>
<div class="tip" id="tip"></div>
</body></html>"""


# Small things shared by every page. The script sits in the head and hooks
# listeners onto document, before the markup, but document is already there.
PAGE_SCRIPT = """
function close_popovers(except){
  document.querySelectorAll('details.filters-box[open]').forEach(box => {
    if (!except || !box.contains(except)) box.open = false;
  });
}
// A slice and its line in the legend light each other up. Five steps of one
// colour cannot be told apart by eye alone, and they should not have to be:
// pointing at either half of the pair says which is which.
function light_slice(ring, which){
  ring.classList.toggle('lit', which !== null);
  ring.querySelectorAll('[data-slice]').forEach(el => {
    el.classList.toggle('on', el.dataset.slice === which);
  });
}
document.addEventListener('mouseover', e => {
  if (!e.target.closest) return;
  const ring = e.target.closest('.ring');
  if (!ring) return;
  const part = e.target.closest('[data-slice]');
  light_slice(ring, part ? part.dataset.slice : null);
});
document.addEventListener('mouseout', e => {
  if (!e.target.closest) return;
  const ring = e.target.closest('.ring');
  if (ring && !ring.contains(e.relatedTarget)) light_slice(ring, null);
});
// A field with our own list under it. The browser's own list cannot show the
// flags and will not close on a second click on the field, which is the whole
// reason this exists.
function close_pickers(except){
  document.querySelectorAll('.picker').forEach(picker => {
    if (picker !== except) picker.querySelector('.options').hidden = true;
  });
}
function filter_picker(picker){
  const typed = picker.querySelector('input').value.trim().toUpperCase();
  let shown = 0;
  picker.querySelectorAll('.option').forEach(option => {
    const fits = !typed || option.dataset.value.includes(typed);
    option.hidden = !fits;
    if (fits) shown++;
  });
  return shown;
}
function open_picker(picker, open){
  const list = picker.querySelector('.options');
  list.hidden = !open || !filter_picker(picker);
  if (!list.hidden) { close_pickers(picker); list.scrollTop = 0; }
}
document.addEventListener('mousedown', e => {
  if (!e.target.closest) return;
  const picker = e.target.closest('.picker');
  close_pickers(picker);
  if (!picker) return;
  // a second click on the field shuts the list; the click itself is left
  // alone, so the caret still lands where it was aimed
  if (e.target.closest('input'))
    open_picker(picker, picker.querySelector('.options').hidden);
});
document.addEventListener('click', e => {
  if (!e.target.closest) return;
  const option = e.target.closest('.picker .option');
  if (!option) return;
  const picker = option.closest('.picker');
  picker.querySelector('input').value = option.dataset.value;
  open_picker(picker, false);
});
document.addEventListener('input', e => {
  const picker = e.target.closest && e.target.closest('.picker');
  if (picker) open_picker(picker, true);
});
document.addEventListener('keydown', e => {
  const picker = e.target.closest && e.target.closest('.picker');
  if (!picker) return;
  if (e.key === 'Escape') { open_picker(picker, false); return; }
  const shown = [...picker.querySelectorAll('.option')].filter(o => !o.hidden);
  const here = shown.indexOf(picker.querySelector('.option.at'));
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    open_picker(picker, true);
    const next = shown[Math.max(0, Math.min(shown.length - 1,
                                here + (e.key === 'ArrowDown' ? 1 : -1)))];
    shown.forEach(o => o.classList.toggle('at', o === next));
    if (next) next.scrollIntoView({block: 'nearest'});
  } else if (e.key === 'Enter' && here >= 0 &&
             !picker.querySelector('.options').hidden) {
    e.preventDefault();
    picker.querySelector('input').value = shown[here].dataset.value;
    open_picker(picker, false);
  }
});
document.addEventListener('click', e => close_popovers(e.target));
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') close_popovers(null);
});
"""


# --- charts ----------------------------------------------------------------

def smooth_path(points):
    """A soft line through the points, without inventing a high or a low.

    Straight segments between every close make an equity curve read as a saw:
    the corners are sharper than the data is. The curve here is a monotone
    cubic (Fritsch and Carlson), which is the one kind of smoothing that never
    overshoots a point, so a peak on the picture is a peak that happened. Two
    closes on the same day keep their vertical step: there is nothing to
    interpolate across an x of zero width.
    """
    if len(points) < 2:
        return ""
    n = len(points)
    slope = []                                   # secant of every segment
    for i in range(n - 1):
        dx = points[i + 1][0] - points[i][0]
        slope.append((points[i + 1][1] - points[i][1]) / dx if dx > 1e-9 else None)
    tangent = []
    for i in range(n):
        before = slope[i - 1] if i > 0 else None
        after = slope[i] if i < n - 1 else None
        if before is None or after is None:
            tangent.append(after if before is None else before)
        elif before * after <= 0:                # a turning point stays a corner
            tangent.append(0.0)
        else:                                    # harmonic mean keeps it monotone
            tangent.append(2 * before * after / (before + after))
        if tangent[-1] is None:
            tangent[-1] = 0.0

    d = [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
    for i in range(n - 1):
        (x0, y0), (x1, y1) = points[i], points[i + 1]
        dx = x1 - x0
        if dx <= 1e-9 or slope[i] is None:
            d.append(f"L{x1:.1f},{y1:.1f}")
            continue
        c1 = (x0 + dx / 3.0, y0 + tangent[i] * dx / 3.0)
        c2 = (x1 - dx / 3.0, y1 - tangent[i + 1] * dx / 3.0)
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} "
                 f"{x1:.1f},{y1:.1f}")
    return " ".join(d)


def spread_days(points):
    """Points that share a date get their own place inside that day.

    A journal records the date of a close, not the hour, so two trades closed
    on the same day land on the same x and the line between them is a vertical
    wall that no curve can be bent through. They are laid out evenly across
    their day instead, in the order they were closed. The balances are
    untouched and the day is unchanged; only the hour, which was never
    recorded, is made up, and a day is a few pixels wide.
    """
    out, i = [], 0
    while i < len(points):
        j = i
        while j + 1 < len(points) and points[j + 1][0].date() == points[i][0].date():
            j += 1
        run = j - i + 1
        for k in range(run):
            day, value = points[i + k]
            out.append((day + timedelta(days=(k + 1) / (run + 1)) if run > 1
                        else day, value))
        i = j + 1
    return out


def equity_svg(series, width=980, height=260, cid="equity"):
    """Equity lines with hovering. series: [(name, colour, [(date, value)])].

    Only like quantities share a picture: accounts go on one chart, the total
    on its own. There are never two scales in one image.
    """
    series = [(name, colour, spread_days(pts))
              for name, colour, pts in series if len(pts) > 1]
    if not series:
        return '<p class="muted">Nothing to plot yet.</p>'
    pad = (56, 14, 26, 92)                        # left, top, bottom, right
    every = [(d, v) for _, _, pts in series for d, v in pts]
    x0, x1 = min(d for d, _ in every), max(d for d, _ in every)
    y0, y1 = min(v for _, v in every), max(v for _, v in every)
    if y1 == y0:
        y1 = y0 + 1
    gap = (y1 - y0) * 0.06
    y0, y1 = y0 - gap, y1 + gap
    pw, ph = width - pad[0] - pad[3], height - pad[1] - pad[2]
    span = max((x1 - x0).total_seconds(), 1)

    def X(d):
        return pad[0] + pw * (d - x0).total_seconds() / span

    def Y(v):
        return pad[1] + ph * (1 - (v - y0) / (y1 - y0))

    parts = [f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>']
    for i in range(5):                            # the grid stays in the back
        v = y0 + (y1 - y0) * i / 4
        y = Y(v)
        parts.append(f'<line x1="{pad[0]}" y1="{y:.1f}" x2="{width-pad[3]}" '
                     f'y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{pad[0]-6}" y="{y+3:.1f}" fill="{DIM}" '
                     f'font-size="10" text-anchor="end">{money(v)}</text>')
    # over a short stretch the month and the year would repeat, so show days
    fmt = "%d.%m" if (x1 - x0).days < 150 else "%m.%Y"
    for i in range(4):
        d = x0 + (x1 - x0) * (i / 3)
        parts.append(f'<text x="{X(d):.1f}" y="{height-8}" fill="{DIM}" '
                     f'font-size="10" text-anchor="middle">{d.strftime(fmt)}</text>')

    data = []
    for k, (name, colour, pts) in enumerate(series):
        screen = [(X(dt), Y(v)) for dt, v in pts]
        d = smooth_path(screen)
        # a wash under the line instead of a second line: it gives the curve a
        # body without adding a colour or a border to look at
        fade = f"{cid}-fade-{k}"
        parts.append(
            f'<defs><linearGradient id="{fade}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{colour}" stop-opacity="0.20"/>'
            f'<stop offset="1" stop-color="{colour}" stop-opacity="0"/>'
            f'</linearGradient></defs>')
        parts.append(f'<path d="{d} L{screen[-1][0]:.1f},{pad[1]+ph:.1f} '
                     f'L{screen[0][0]:.1f},{pad[1]+ph:.1f} Z" '
                     f'fill="url(#{fade})" stroke="none"/>')
        parts.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="2" '
                     f'stroke-linejoin="round" stroke-linecap="round" '
                     f'shape-rendering="geometricPrecision"/>')
        dt, v = pts[-1]
        parts.append(f'<circle cx="{X(dt):.1f}" cy="{Y(v):.1f}" r="3" fill="{colour}"/>')
        parts.append(f'<text x="{X(dt)+7:.1f}" y="{Y(v)+3:.1f}" fill="{INK2}" '
                     f'font-size="10">{esc(name)}</text>')
        data.append({"name": name, "colour": colour,
                     "points": [[round(X(dt), 1), round(Y(v), 1),
                                 dt.strftime("%d.%m.%Y"), round(v)]
                                for dt, v in pts]})

    parts.append(f'<line id="{cid}-ray" x1="0" y1="{pad[1]}" x2="0" '
                 f'y2="{pad[1]+ph}" stroke="{AXIS}" stroke-width="1" '
                 f'visibility="hidden"/>')
    parts.append(f'<g id="{cid}-dots"></g>')
    parts.append(f'<rect id="{cid}-catcher" x="{pad[0]}" y="{pad[1]}" '
                 f'width="{pw}" height="{ph}" fill="transparent"/>')
    svg = (f'<svg id="{cid}" viewBox="0 0 {width} {height}" width="100%" '
           f'preserveAspectRatio="xMidYMid meet" role="img" '
           f'data-series=\'{json.dumps(data, ensure_ascii=False)}\'>'
           + "".join(parts) + "</svg>")
    return svg + f'<script>hover_chart("{cid}");</script>'


HOVER = """
function hover_chart(cid){
  const svg = document.getElementById(cid);
  if (!svg) return;
  const series = JSON.parse(svg.dataset.series);
  const ray = document.getElementById(cid + '-ray');
  const dots = document.getElementById(cid + '-dots');
  const catcher = document.getElementById(cid + '-catcher');
  // the tip lives at the end of body, so look it up while hovering, not at build
  const tip = () => document.getElementById('tip');
  const NS = 'http://www.w3.org/2000/svg';
  catcher.addEventListener('mousemove', e => {
    const box = svg.getBoundingClientRect();
    const vb = svg.viewBox.baseVal;
    const x = (e.clientX - box.left) * vb.width / box.width;
    let lines = [], at = null;
    dots.replaceChildren();
    for (const s of series) {
      // An account is shown only while the cursor is inside its own stretch of
      // time: before its first trade and after its last one it is not on the
      // chart. Cutting by distance will not do: with sparse points the gaps
      // are large.
      const first = s.points[0], last = s.points[s.points.length - 1];
      if (!first || x < first[0] - 6 || x > last[0] + 6) continue;
      let best = null, d = 1e9;
      for (const p of s.points) { const dd = Math.abs(p[0] - x);
        if (dd < d) { d = dd; best = p; } }
      if (!best) continue;
      lines.push(s.name + ': ' +
        String(best[3]).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ' ') + ' $');
      at = best;
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', best[0]); c.setAttribute('cy', best[1]);
      c.setAttribute('r', 4); c.setAttribute('fill', s.colour);
      c.setAttribute('stroke', '#121214'); c.setAttribute('stroke-width', '2');
      dots.appendChild(c);
    }
    if (!at) return;
    ray.setAttribute('x1', at[0]); ray.setAttribute('x2', at[0]);
    ray.setAttribute('visibility', 'visible');
    const t = tip();
    if (!t) return;
    t.textContent = at[2] + '\\n' + lines.join('\\n');
    t.style.display = 'block';
    t.style.left = Math.min(e.clientX + 14, innerWidth - 190) + 'px';
    t.style.top = (e.clientY + 14) + 'px';
  });
  catcher.addEventListener('mouseleave', () => {
    ray.setAttribute('visibility', 'hidden');
    dots.replaceChildren();
    const t = tip();
    if (t) t.style.display = 'none';
  });
}
"""


def donut_svg(segments, size=188, thickness=30, middle="", under=""):
    """A ring of ordered slices. segments: [(label, count, colour)].

    The slices are separated by a gap of the card colour rather than by a
    stroke: a ring read at a glance should not have a second colour in it.
    """
    total = sum(n for _, n, _ in segments)
    if not total:
        return '<p class="muted">Nothing to plot yet.</p>'
    r = (size - thickness) / 2
    c = size / 2
    circumference = 2 * math.pi * r
    gap = 3 if sum(1 for _, n, _ in segments if n) > 1 else 0
    parts, offset = [], 0.0
    for i, (label, n, colour) in enumerate(segments):
        if not n:
            continue
        length = circumference * n / total
        drawn = max(length - gap, 1.0)
        parts.append(
            f'<circle data-slice="{i}" cx="{c}" cy="{c}" r="{r:.2f}" fill="none" '
            f'stroke="{colour}" stroke-width="{thickness}" '
            f'stroke-dasharray="{drawn:.2f} {circumference - drawn:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}">'
            f'<title>{esc(label)}: {n} trades, {100.0 * n / total:.0f}%</title>'
            f'</circle>')
        offset += length
    text = ""
    if middle:
        text += (f'<text x="{c}" y="{c - 1}" fill="{INK}" font-size="30" '
                 f'font-family="{MONO}" text-anchor="middle">{esc(middle)}</text>')
    if under:
        text += (f'<text x="{c}" y="{c + 17}" fill="{DIM}" font-size="11" '
                 f'text-anchor="middle">{esc(under)}</text>')
    # only the ring turns, so that the reading starts at twelve o'clock; the
    # text in the middle stays upright
    return (f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
            f'role="img"><g transform="rotate(-90 {c} {c})">'
            + "".join(parts) + f'</g>{text}</svg>')


def donut_legend(rows, total):
    """The slices in words: a chip, the bucket, how many and what share.

    A ring alone leaves the reader guessing at the sizes, so the numbers stand
    next to it and the colour only carries the order."""
    lines = "".join(
        f'<tr data-slice="{i}"><td><i style="background:{colour}"></i>{esc(label)}</td>'
        f'<td class="num">{n}</td>'
        f'<td class="num muted">{100.0 * n / total:.0f}%</td>'
        f'<td class="num {"win" if sum_r > 0 else "lose" if sum_r < 0 else "muted"}">'
        f'{sum_r:+.1f} R</td></tr>'
        for i, (label, n, sum_r, colour) in enumerate(rows) if n)
    return f'<table class="donut-legend"><tbody>{lines}</tbody></table>'


def legend(pairs):
    return '<div class="legend">' + "".join(
        f'<span><i style="background:{colour}"></i>{esc(name)}</span>'
        for name, colour in pairs) + "</div>"
