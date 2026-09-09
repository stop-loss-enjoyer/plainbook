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
from urllib.parse import quote as _quote
from datetime import timedelta

from . import __version__, flags

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


def mark(size=20, ink=INK, accent=ACCENT):
    """The sign of the journal: three lines of plain text and one candle
    standing where the cursor would be.

    The lines are the record, the candle is what the record is about. The
    body runs from the first line to the last, so the two read as one block.
    Drawn in two colours of the palette and nothing else, so it sits in the
    header without asking for attention."""
    return (f'<svg class="mark" viewBox="0 0 20 20" width="{size}" height="{size}" '
            f'fill="none" stroke-width="1.6" stroke-linejoin="round" '
            f'stroke-linecap="round" aria-hidden="true">'
            f'<path d="M3 5h7M3 10h7M3 15h4" stroke="{ink}"/>'
            f'<path d="M14.6 2.3v2.5M14.6 15.2v2.5" stroke="{accent}" stroke-width="1.3"/>'
            f'<rect x="12.6" y="4.8" width="4" height="10.4" rx=".8" fill="{accent}"/>'
            f'</svg>')


# the tab icon is the same sign on the page ground, inlined as a data URL:
# a favicon fetched from a file would be the one request the page makes
FAVICON = "data:image/svg+xml," + _quote(
    mark(32).replace('class="mark" ', "").replace("<svg ", f'<svg style="background:{GROUND}" ', 1))

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
/* the header is sticky and 49px tall, so an address ending in an anchor would
   otherwise land with the heading it names hidden underneath it */
html{{scroll-padding-top:57px}}

/* header: the sign, the name, the tabs; 48px tall, and the table heads
   below know that number */
header{{display:flex;align-items:stretch;gap:18px;flex-wrap:wrap;
 position:sticky;top:0;z-index:8;background:{GROUND};
 border-bottom:1px solid {EDGE};min-height:49px;margin-bottom:18px}}
header .logo{{display:inline-flex;align-items:center;gap:10px;color:{INK};
 font:600 18px/1 {MONO};letter-spacing:-.02em;padding-right:4px}}
header .logo .mark{{display:block}}
/* the version, beside the name and in the way of nobody: a person asking
   for help can say which one they have the moment the page opens */
header .logo .ver{{font:500 10px/1 {MONO};color:{DIM};letter-spacing:0;
 margin-top:5px}}
header .logo:hover{{color:{INK}}}
header .logo:hover .mark path,header .logo:hover .mark rect{{stroke:{ACCENT}}}
header .logo:hover .mark rect{{fill:{ACCENT}}}
header .logo:hover .mark path[stroke="{ACCENT}"]{{stroke:{ACCENT}}}
header nav{{display:flex;gap:2px;align-items:stretch}}
header nav a{{display:inline-flex;align-items:center;color:{DIM};padding:0 10px;
 font-size:12px;letter-spacing:.02em;border-bottom:2px solid transparent;
 margin-bottom:-1px}}
header nav a:hover{{color:{INK2}}}
header nav a.current{{color:{INK};border-bottom-color:{ACCENT}}}
/* A tab that asks for the owner: amber, the colour the journal already
   uses for a warning tile. It is on while there is no playbook and while a
   block waits for its review, and off the rest of the time, so that when it
   is on it is seen. A colour that is always on is not seen after a week. */
header nav a.attention{{color:{WARN}}}
header nav a.attention::after{{content:"";display:inline-block;width:5px;height:5px;
 border-radius:50%;background:{WARN};margin-left:6px;vertical-align:1px}}
header nav a.attention.current{{color:{INK};border-bottom-color:{WARN}}}
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

/* tiles. Each tile draws its own right and bottom line and hangs 1px over
   the neighbour, so the frame clips the last ones: a place in the grid with
   no tile in it is plain surface, not a grey block */
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(184px,1fr));
 background:{SURFACE};border:1px solid {EDGE};border-radius:5px;
 overflow:hidden;margin-bottom:16px}}
/* accounts are not stretched across the screen: there are two of them, and a
   full-width strip would read as an empty table */
.tiles.narrow{{display:flex;flex-wrap:wrap;width:fit-content;max-width:100%}}
.tiles.narrow .tile{{min-width:236px;flex:0 0 auto}}
.tile{{background:{SURFACE};padding:12px 15px 13px;
 border-right:1px solid {EDGE};border-bottom:1px solid {EDGE};
 margin:0 -1px -1px 0}}
.tile .name{{color:{DIM};font-size:10px;text-transform:uppercase;
 letter-spacing:.09em}}
/* the name of an account leads to its statistics: it keeps the quiet look of
   a caption and lights up under the pointer, so the tile stays a tile */
.tile .name a{{color:inherit}}
.tile .name a:hover{{color:{INK};text-decoration:underline;text-underline-offset:3px}}
.tile .value{{font:600 22px/1.15 {MONO};margin-top:5px;
 font-variant-numeric:tabular-nums;letter-spacing:-.01em}}
.tile .sub{{color:{INK2};font-size:11px;margin-top:4px}}
/* a figure and its R move to the next line together, never parted */
.tile .sub .rest{{white-space:nowrap}}
/* the EV shares the line with the winrate, a size down, and says by colour
   which side of zero it is on; it drops to its own line if the tile is narrow */
.tile .value .ev{{font-size:13px;margin-left:8px;white-space:nowrap}}
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
/* figures that say what they are by colour alone and take no labels: the
   winrate tile, and the trades of a report card. Blue is a position that was
   still in the market when the period ended */
.be{{color:{WARN}}} .live{{color:{ACCENT}}}
.breakdown{{font-family:{MONO};font-size:12px}}
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
/* the paper puts the best trade beside the trades assessment: two columns, the
   text field stretching to the height of the table */
.twin{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}
.twin>div{{display:flex;flex-direction:column;min-width:0}}
.twin textarea{{flex:1}}
@media (max-width:900px){{.twin{{grid-template-columns:1fr}}}}
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
.example{{display:flex;align-items:center;gap:10px;margin:4px 0}}
.is-open{{border-left:2px solid {WARN}}}
.props{{max-width:660px}}

/* playbooks: the rules on paper, a line each with its number in the margin */
.pb-name{{font:600 20px/1.2 system-ui,sans-serif;color:{INK};margin:0}}
.chip{{display:inline-block;font:600 10px/1 {MONO};text-transform:uppercase;
 letter-spacing:.07em;padding:4px 6px;border-radius:3px;border:1px solid {AXIS};
 color:{INK2};vertical-align:2px}}
.chip.experiment{{color:{WARN};border-color:rgba(217,164,65,.45)}}
.chip.active{{color:{GOOD};border-color:rgba(72,172,122,.45)}}
.chip.retired{{color:{DIM}}}
.chip.breakeven{{color:{GOOD};border-color:rgba(72,172,122,.45)}}
.pb-meta{{color:{DIM};font-size:12px;margin:6px 0 0}}
.pb-meta b{{color:{INK2};font-weight:500}}
.pb-intro{{max-width:760px;color:{INK2};font-size:13px;line-height:1.55;margin:12px 0 0}}
.pb-intro p{{margin:0 0 8px}}
.setup{{margin-top:20px}}
.setup:first-child{{margin-top:0}}
.setup h3{{margin:0 0 4px}}
.setup .about{{max-width:760px;color:{INK2};font-size:13px;line-height:1.5;margin:0 0 4px}}
.rules{{list-style:none;margin:6px 0 0;padding:0;max-width:760px}}
.rules li{{display:flex;gap:12px;align-items:baseline;padding:8px 0;
 border-top:1px solid {GRID};font-size:13px;line-height:1.5}}
.rules li:first-child{{border-top:0}}
.rules .n{{flex:0 0 40px;font:600 11px/1.6 {MONO};color:{DIM};text-align:right;
 white-space:nowrap}}
.rules .n::before{{content:"";display:inline-block;width:9px;height:9px;
 border:1px solid {AXIS};border-radius:2px;margin-right:7px;vertical-align:-1px}}
.block-bar{{height:4px;background:{GRID};border-radius:2px;max-width:320px;margin-top:8px}}
.block-bar i{{display:block;height:100%;background:{ACCENT};border-radius:2px}}
.limits{{display:flex;flex-wrap:wrap;gap:10px 26px;margin:0}}
.limits div{{font-size:12px;color:{DIM}}}
.limits b{{font:600 13px/1 {MONO};color:{INK};margin-left:7px}}
.pb-text{{max-width:760px;font-size:13px;line-height:1.55;color:{INK2}}}
.pb-text p{{margin:0 0 8px}}
.pb-text ul{{margin:0 0 8px;padding-left:20px}}
.pb-text li{{margin:2px 0}}
.pb-text h3{{margin-top:12px}}
.setup-form{{border-left:2px solid {AXIS};padding-left:12px;margin-bottom:16px}}
.setup-form .fields{{margin-bottom:8px}}
textarea.lines{{font-family:{MONO};font-size:12px}}
.rules-edit{{max-width:860px}}
.rule-row{{display:flex;gap:10px;align-items:flex-start;padding:3px 0}}
.rule-row .n{{flex:0 0 26px;font:600 11px/1 {MONO};color:{DIM};text-align:right;
 padding-top:9px}}
.rule-row textarea{{flex:1;width:auto;min-height:0;height:auto;resize:none;
 overflow:hidden;line-height:1.45;padding:6px 9px}}
.rule-row textarea.short{{flex:0 0 300px;color:{INK};font-weight:500}}
.rules .detail{{display:block;color:{DIM};font-size:12px;line-height:1.45;margin-top:2px}}
.rule-row .x{{background:transparent;border:0;color:{DIM};cursor:pointer;
 font-size:17px;line-height:1;padding:6px 6px}}
.rule-row .x:hover{{color:{BAD}}}
.btn.small{{padding:3px 9px;font-size:11px;margin-top:4px}}
/* the checklist in the trade form: a row per rule, the whole rule behind ? */
.checklist h3{{margin-top:0}}
.checklist .setups{{display:flex;gap:16px;flex-wrap:wrap;margin:0 0 10px}}
.checklist .radio{{display:inline-flex;align-items:center;gap:6px;margin:0;
 text-transform:none;letter-spacing:0;font-size:13px;color:{INK}}}
.checklist .filter-rules h3{{margin-top:14px}}
.check{{display:flex;align-items:baseline;gap:8px;padding:6px 0;
 border-top:1px solid {GRID};max-width:760px}}
.check:first-child,.setups + .setup-rules .check:first-child{{border-top:0}}
.check input[type=checkbox]{{flex:0 0 auto;margin:0;vertical-align:0}}
.check label{{display:inline;margin:0;text-transform:none;letter-spacing:0;
 font-size:13px;color:{INK};cursor:pointer}}
.check label .n{{font:600 11px/1 {MONO};color:{DIM};margin-right:8px}}
.check .why{{background:transparent;border:1px solid {AXIS};color:{DIM};
 border-radius:50%;width:18px;height:18px;line-height:1;font-size:11px;
 cursor:pointer;padding:0;flex:0 0 auto}}
.check .why:hover{{color:{INK};border-color:{DIM}}}
.check .detail{{flex-basis:100%;color:{DIM};font-size:12px;line-height:1.45;
 padding-left:26px}}
.check{{flex-wrap:wrap}}
.check .why-in{{flex-basis:100%;margin-left:26px;width:auto;font-size:12px;
 padding:4px 8px;border-color:rgba(217,164,65,.45)}}
.rules .reason{{display:block;color:{WARN};font-size:12px;line-height:1.45;margin-top:2px}}
.reasons{{font-size:12px;margin-top:8px}}
.reasons b{{font:600 11px/1 {MONO};color:{DIM};margin-right:6px}}
.reasons ul{{margin:4px 0 0;padding-left:26px;color:{INK2}}}
.reasons li{{margin:2px 0}}
.reasons li a{{font-family:{MONO};font-size:11px;margin-right:6px}}
.tally{{margin:10px 0 0}}
.frame{{display:flex;gap:6px 22px;flex-wrap:wrap;margin:0 0 12px;font-size:12px;color:{DIM}}}
.frame b{{font:600 12px/1 {MONO};color:{INK}}}
.frame .over,.frame .over b{{color:{BAD}}}
.pb-meta.over,.pb-meta.over b{{color:{WARN}}}
.over{{color:{BAD}}}
/* the same rules on the page of a trade, met or not */
.rules.ticked li.ok .n::before{{content:"✓";color:{GOOD};border-color:transparent;
 width:auto;height:auto;font-size:12px}}
.rules.ticked li.no .n::before{{content:"✗";color:{BAD};border-color:transparent;
 width:auto;height:auto;font-size:12px}}
.rules.ticked li.no > span:last-child{{color:{BAD}}}
tr.total td{{border-top:1px solid {AXIS};color:{INK};font-weight:500}}
tr.sub td:first-child{{padding-left:28px;color:{INK2}}}
tr.sub td{{color:{INK2}}}
.limit-row{{display:flex;gap:8px;align-items:center;padding:3px 0}}
.limit-row input[name="limit_name"]{{width:240px}}
.limit-row .x{{background:transparent;border:0;color:{DIM};cursor:pointer;
 font-size:17px;line-height:1;padding:4px 6px}}
.limit-row .x:hover{{color:{BAD}}}
.versions{{list-style:none;margin:0;padding:0;font-size:12px}}
.versions li{{padding:4px 0}}
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

/* reports: the period at reading size, the strip of tiles under it, two
   pictures side by side, the tables after the story */
/* the head of a page that is not a card: what is being looked at on the left,
   what changes it on the right. Relative, because the filter popover hangs
   off it the way it hangs off the head of a card */
.page-head{{display:flex;align-items:flex-end;gap:14px;flex-wrap:wrap;
 margin:0 0 14px;position:relative}}
.page-head h2{{margin:0 0 4px}}
.page-head .pb-meta{{margin:0 0 2px}}
.page-head .right{{margin-left:auto;display:flex;gap:7px;align-items:center}}
/* the cut is written out in the title and every part of it drops itself:
   text, lit under the pointer, like the name of an account over a balance */
.page-head h1 a{{color:{INK}}}
.page-head h1 a:hover{{color:{ACCENT}}}
.page-head .pb-meta a{{color:{INK2}}}
.page-head .pb-meta a:hover{{color:{ACCENT}}}
.tile.lead .value{{font-size:28px;white-space:nowrap}}
.tile .value .ev{{font-weight:500}}
/* a trade named in a tile is a way in, drawn as quietly as the name of an
   account over a balance: text, lit under the pointer */
.tile .sub a{{color:{INK2}}}
.tile .sub a:hover{{color:{ACCENT}}}
.pictures{{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,3fr);gap:16px;
 margin-bottom:16px}}
.pictures>.card{{margin-bottom:0;min-width:0}}
@media (max-width:1100px){{.pictures{{grid-template-columns:1fr}}}}
/* the curves of the accounts in one row, each drawn at the width of its
   cell; the count of columns is written on the element by the page, since
   it is the number of accounts and not a property of the theme */
.charts{{display:grid;gap:4px 16px}}
.charts>div{{min-width:0}}
.charts h3{{margin-top:0}}
@media (max-width:900px){{.charts{{grid-template-columns:1fr !important}}}}
.twin>.card{{margin-bottom:16px}}
/* six figures in one row; on a narrower screen two rows of three, so the
   strip never leaves an empty corner and the names stay on one line. Two
   names for one strip: a test pins the report's, and "report" is not what
   the strip of the statistics is */
.tiles.report,.tiles.strip{{grid-template-columns:repeat(6,1fr)}}
@media (max-width:1250px){{.tiles.report,.tiles.strip{{
 grid-template-columns:repeat(3,1fr)}}}}
@media (max-width:700px){{.tiles.report,.tiles.strip{{
 grid-template-columns:repeat(2,1fr)}}}}
.twin .tiles.narrow .tile{{flex:1 0 236px}}
/* the playbook table is eight columns wide and does not fit half a page */
@media (max-width:1150px){{.twin.books{{grid-template-columns:1fr}}}}
.tape a rect:hover{{fill-opacity:1}}
.rings.compact .ring{{flex:1 1 200px;min-width:0;padding:10px 12px}}
.rings.compact .ring-body{{flex-direction:column;align-items:flex-start;gap:6px}}
.rings.compact .donut-legend{{flex:none;width:100%}}
/* the name of a bucket wraps rather than pushing its figures out of the box:
   the legend stands in half a column here and the window can be narrower */
.rings.compact .donut-legend td:first-child{{white-space:normal}}
.grades{{margin:8px 0 0;display:flex;gap:6px;flex-wrap:wrap}}
.grades .chip b{{color:{INK};font-weight:600;margin-left:4px}}
ul.errors{{margin:6px 0 0;padding-left:0;list-style:none;max-width:760px}}
ul.errors li{{padding:6px 0;border-top:1px solid {GRID};font-size:13px;line-height:1.5;
 color:{INK2}}}
ul.errors li a{{font-family:{MONO};font-size:11px;color:{DIM};margin-right:8px}}
ul.errors li a:hover{{color:{ACCENT}}}
.days a{{color:{INK2}}}
form.inline{{display:inline-block;margin:0}}
table.shelf td.report{{white-space:nowrap}}
table.shelf td.report .caption{{margin-right:8px}}
table.shelf .btn.small{{margin-top:0}}
table.shelf tr.quarter td:first-child{{font-weight:600}}
table.shelf tr.quarter td:first-child .muted{{font-weight:400}}
/* rebuilding a file that already stands is the rare action, so it is a word */
form.inline .quiet{{background:none;border:0;padding:0;color:{DIM};cursor:pointer;
 font:11px/1.4 system-ui,sans-serif}}
form.inline .quiet:hover{{color:{INK};text-decoration:underline;text-underline-offset:3px}}
.dot{{display:inline-block;width:6px;height:6px;border-radius:50%;background:{ACCENT};
 vertical-align:1px;margin-right:5px}}
.card.conclusions .pb-text{{color:{INK}}}

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


def page(title, body, tab="journal", header_right="", notice="", said="",
         attention=(), home="/"):
    """`attention` names the tabs that ask for the owner, see the CSS. `home`
    is where the Journal tab leads: a trade opened from a filtered list sends
    the reader back to the same list."""
    links = [("journal", home, "Journal"), ("playbooks", "/playbooks", "Playbooks"),
             ("plans", "/plans", "Plans"), ("notes", "/notes", "Notes"),
             ("cards", "/cards", "Cards"), ("stats", "/stats", "Statistics"),
             ("reports", "/reports", "Reports"), ("accounts", "/accounts", "Accounts"),
             ("search", "/search", "Search")]
    nav = "".join(
        f'<a href="{href}" class="{" ".join(["current"] * (code == tab) + ["attention"] * (code in attention))}">{name}</a>'
        for code, href, name in links)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{"Plainbook" if title == "Journal"
          else "Plainbook: " + esc(title)}</title>
<link rel="icon" href="{FAVICON}"><style>{CSS}</style>
<script>{HOVER}{PAGE_SCRIPT}</script></head><body>
{flags.SPRITE}{said}
<div class="wrap">
<header><a href="{home}" class="logo" title="the journal">{mark(26)}plainbook<span class="ver">{__version__}</span></a><nav>{nav}</nav>
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


def nice_step(span, target=5):
    """A round step for the ticks of an axis: 1, 2, 2.5 or 5 times a power
    of ten, the largest that gives about `target` steps over the span."""
    if span <= 0:
        return 1.0
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= raw:
            return m * mag
    return 10 * mag


def count_step(n, target=6):
    """The same for a count of trades, where 2.5 makes no sense."""
    if n <= 0:
        return 1
    raw = n / target
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if m * mag >= raw:
            return max(1, int(m * mag))
    return max(1, int(10 * mag))


def _next_month(d):
    return (d.replace(day=1) + timedelta(days=32)).replace(day=1)


def date_ticks(x0, x1):
    """Where the calendar puts the ticks of a time axis: every day over a few
    days, Mondays over a few weeks, the first of the month otherwise, and no
    more than eight of them.

    Returns [(datetime, label)]. The labels are dates with no year while the
    ticks are days, and month and year once they are months."""
    days = (x1 - x0).days
    midnight = x0.replace(hour=0, minute=0, second=0, microsecond=0)
    if days <= 10:
        d = midnight if midnight >= x0 else midnight + timedelta(days=1)
        step = timedelta(days=1)
    elif days <= 70:
        d = midnight + timedelta(days=(7 - midnight.weekday()) % 7)
        step = timedelta(days=7)
    else:
        d = midnight.replace(day=1)
        if d < x0:
            d = _next_month(d)
        months = []
        while d <= x1:
            months.append(d)
            d = _next_month(d)
        k = max(1, math.ceil(len(months) / 8))
        return [(m, m.strftime("%m.%Y")) for i, m in enumerate(months) if i % k == 0]
    ticks = []
    while d <= x1:
        ticks.append((d, d.strftime("%d.%m")))
        d += step
    if len(ticks) > 8:
        k = math.ceil(len(ticks) / 8)
        ticks = [t for i, t in enumerate(ticks) if i % k == 0]
    return ticks


def _what(tag):
    """The words for a point that is not a trade: what moved the money."""
    if tag in (None, "start", "since"):
        return ""
    amount = getattr(tag, "amount", 0.0)
    return f"{getattr(tag, 'kind', 'adjustment')} {money(amount, signed=True)}"


def equity_svg(series, width=980, height=260, cid="equity", sign="$",
               base=None, base_word="from start", axis="date"):
    """An equity line with hovering. series: [(name, colour, points)], a point
    being (date, value) or (date, value, what) as `stats.equity_events` gives
    them. `sign` is the currency the tip names next to a balance.

    `base` is the balance the account started from (or entered the period
    with): a dashed line across the picture, and the wash under the curve is
    green above it and red below it, so which side of the start the account
    is on is read before a single number is. Money that moved outside a
    trade moves the line with it: a deposit steps it up, a withdrawal steps
    it down, so the wash and the figure at the end of the curve are what the
    trading did and a withdrawal does not paint the account red. Without a
    base the first point serves as one.

    `axis` is "date" or "trade": on the calendar, or one step per closed
    trade, which is how an equity curve is usually read. Money that moved
    outside a trade takes no step of its own there and stands as a vertical
    edge, marked with a hollow dot in both modes.

    Only like quantities share a picture: accounts go on one chart, the total
    on its own. There are never two scales in one image.
    """
    drawn = []
    for name, colour, pts in series:
        pts = [(p[0], p[1], p[2] if len(p) > 2 else None) for p in pts]
        if len(pts) < 2:
            continue
        if axis == "trade":
            # an adjustment moves the balance, not the count: it shares the x
            # of the trade before it, and the step is upright
            xs, n = [], 0
            for day, value, what in pts:
                if what is None:
                    n += 1
                xs.append(n)
        else:
            spread = spread_days([(d, v) for d, v, _ in pts])
            xs = [d for d, _ in spread]
        drawn.append((name, colour, pts, xs))
    if not drawn:
        return '<p class="muted">Nothing to plot yet.</p>'
    if base is None:
        base = drawn[0][2][0][1]

    # the base of every point: the start, plus what was put in or taken out
    # by then, so that the distance from it is what the trading did
    bases = []
    for _, _, pts, _ in drawn:
        b, per_point = base, []
        for _, _, what in pts:
            b += getattr(what, "amount", 0.0) if _what(what) else 0.0
            per_point.append(b)
        bases.append(per_point)

    # the labels at the end of the line decide how much room the right keeps
    last_value = drawn[-1][2][-1][1]
    end_labels = [money(last_value), money(last_value - bases[-1][-1], signed=True)]
    pad_right = max(60, int(max(len(t) for t in end_labels) * 6.4) + 16)
    pad = (56, 14, 26, pad_right)                 # left, top, bottom, right
    every = ([v for _, _, pts, _ in drawn for _, v, _ in pts]
             + [b for per_point in bases for b in per_point])
    y0, y1 = min(every), max(every)
    if y1 == y0:
        y1 = y0 + 1
    gap = (y1 - y0) * 0.06
    y0, y1 = y0 - gap, y1 + gap
    all_x = [x for _, _, _, xs in drawn for x in xs]
    x0, x1 = min(all_x), max(all_x)
    pw, ph = width - pad[0] - pad[3], height - pad[1] - pad[2]

    if axis == "trade":
        span = max(x1 - x0, 1)

        def X(x):
            return pad[0] + pw * (x - x0) / span
    else:
        span = max((x1 - x0).total_seconds(), 1)

        def X(d):
            return pad[0] + pw * (d - x0).total_seconds() / span

    def Y(v):
        return pad[1] + ph * (1 - (v - y0) / (y1 - y0))

    top, bottom = pad[1], pad[1] + ph
    parts = [f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>']
    # the grid stays in the back, on round numbers
    step = nice_step(y1 - y0)
    v = math.ceil(y0 / step) * step
    while v <= y1:
        y = Y(v)
        parts.append(f'<line x1="{pad[0]}" y1="{y:.1f}" x2="{width-pad[3]}" '
                     f'y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{pad[0]-6}" y="{y+3:.1f}" fill="{DIM}" '
                     f'font-size="10" text-anchor="end">{money(v)}</text>')
        v += step
    if axis == "trade":
        step = count_step(x1 - x0)
        ticks = [(n, str(n)) for n in range(math.ceil(x0 / step) * step,
                                            int(x1) + 1, step)]
    else:
        ticks = date_ticks(x0, x1)
    for at, label in ticks:
        x = X(at)
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" '
                     f'stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{height-8}" fill="{DIM}" '
                     f'font-size="10" text-anchor="middle">{label}</text>')

    data = []
    left, right = pad[0], width - pad[3]
    for k, (name, colour, pts, xs) in enumerate(drawn):
        screen = [(X(x), Y(v)) for x, (_, v, _) in zip(xs, pts)]
        d = smooth_path(screen)
        # the base line, stepping where money moved: the steps as (x, from, to)
        steps = [(screen[i][0], Y(bases[k][i - 1]), Y(bases[k][i]))
                 for i in range(1, len(pts)) if bases[k][i] != bases[k][i - 1]]
        by_first, by_last = Y(bases[k][0]), Y(bases[k][-1])
        back = "".join(f"L{x:.1f},{to:.1f} L{x:.1f},{frm:.1f} "
                       for x, frm, to in reversed(steps))
        # The wash between the curve and the base line, in the colour of the
        # side it is on. The same area is painted twice and each coat is
        # clipped to its half of the picture, above the base or below it; the
        # coat fades towards the base, so the further the account has gone
        # from where it started, the more of the colour there is.
        area = (f"{d} L{screen[-1][0]:.1f},{by_last:.1f} {back}"
                f"L{screen[0][0]:.1f},{by_first:.1f} Z")
        above = (f"M{left},{top} L{right},{top} L{right},{by_last:.1f} {back}"
                 f"L{left},{by_first:.1f} Z")
        below = (f"M{left},{bottom} L{right},{bottom} L{right},{by_last:.1f} {back}"
                 f"L{left},{by_first:.1f} Z")
        parts.append(
            f'<defs>'
            f'<linearGradient id="{cid}-up-{k}" gradientUnits="userSpaceOnUse" '
            f'x1="0" y1="{top}" x2="0" y2="{by_last:.1f}">'
            f'<stop offset="0" stop-color="{GOOD}" stop-opacity="0.26"/>'
            f'<stop offset="1" stop-color="{GOOD}" stop-opacity="0.04"/>'
            f'</linearGradient>'
            f'<linearGradient id="{cid}-down-{k}" gradientUnits="userSpaceOnUse" '
            f'x1="0" y1="{by_last:.1f}" x2="0" y2="{bottom}">'
            f'<stop offset="0" stop-color="{BAD}" stop-opacity="0.04"/>'
            f'<stop offset="1" stop-color="{BAD}" stop-opacity="0.26"/>'
            f'</linearGradient>'
            f'<clipPath id="{cid}-above-{k}"><path d="{above}"/></clipPath>'
            f'<clipPath id="{cid}-below-{k}"><path d="{below}"/></clipPath>'
            f'</defs>')
        parts.append(f'<path d="{area}" fill="url(#{cid}-up-{k})" stroke="none" '
                     f'clip-path="url(#{cid}-above-{k})"/>')
        parts.append(f'<path d="{area}" fill="url(#{cid}-down-{k})" stroke="none" '
                     f'clip-path="url(#{cid}-below-{k})"/>')
        # the base line goes over the wash and under the curve
        forward = "".join(f"L{x:.1f},{frm:.1f} L{x:.1f},{to:.1f} "
                          for x, frm, to in steps)
        parts.append(f'<path d="M{left},{by_first:.1f} {forward}L{right},{by_last:.1f}" '
                     f'fill="none" stroke="{DIM}" stroke-width="1" '
                     f'stroke-dasharray="3 4"/>')
        parts.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="2" '
                     f'stroke-linejoin="round" stroke-linecap="round" '
                     f'shape-rendering="geometricPrecision"/>')
        # money that moved outside a trade: a hollow dot, so a deposit is not
        # read as a big win
        for (sx, sy), (_, _, what) in zip(screen, pts):
            if _what(what):
                parts.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="3.5" '
                             f'fill="{SURFACE}" stroke="{INK2}" stroke-width="1.5">'
                             f'<title>{esc(_what(what))}</title></circle>')
        ex, ey = screen[-1]
        parts.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3" fill="{colour}"/>')
        delta = pts[-1][1] - bases[k][-1]
        parts.append(f'<text x="{ex+8:.1f}" y="{ey+3:.1f}" fill="{INK2}" '
                     f'font-size="10" font-family="{MONO}">{money(pts[-1][1])}</text>')
        parts.append(f'<text x="{ex+8:.1f}" y="{ey+15:.1f}" '
                     f'fill="{GOOD if delta > 0 else BAD if delta < 0 else INK2}" '
                     f'font-size="10" font-family="{MONO}">'
                     f'{money(delta, signed=True)}</text>')
        data.append({"name": name, "colour": colour, "sign": sign,
                     "base_word": base_word,
                     "points": [[round(sx, 1), round(sy, 1),
                                 (f"trade {x} · " if axis == "trade" and what is None
                                  else "") + day.strftime("%d.%m.%Y"),
                                 round(v), _what(what), round(v - b)]
                                for (sx, sy), x, (day, v, what), b
                                in zip(screen, xs, pts, bases[k])]})

    parts.append(f'<line id="{cid}-ray" x1="0" y1="{top}" x2="0" '
                 f'y2="{bottom}" stroke="{AXIS}" stroke-width="1" '
                 f'visibility="hidden"/>')
    parts.append(f'<g id="{cid}-dots"></g>')
    parts.append(f'<rect id="{cid}-catcher" x="{pad[0]}" y="{top}" '
                 f'width="{pw}" height="{ph}" fill="transparent"/>')
    svg = (f'<svg id="{cid}" viewBox="0 0 {width} {height}" width="100%" '
           f'preserveAspectRatio="xMidYMid meet" role="img" '
           f'data-series=\'{json.dumps(data, ensure_ascii=False)}\'>'
           + "".join(parts) + "</svg>")
    return svg + f'<script>hover_chart("{cid}");</script>'


def tape_svg(bars, marks, width=980, height=230, stop=1.0, bar_max=18.0,
             labels=()):
    """The trades of a period one bar each, in the order they closed.

    bars: [(r, result, href, words)], words being the title of the bar. marks:
    [(index, label)] where a new week or month begins, drawn as a thin line
    before that bar with the label under it. labels: one short name per bar,
    written under it when a slot is wide enough to carry three letters;
    fifteen months read as months only if each bar says which one it is.
    A bar whose href is empty is drawn without a link.

    An r of None keeps its place in the row and draws nothing: a period that
    closed no trade is part of the picture, and a chart with the gaps squeezed
    out would draw a year of trading as if it had been continuous.

    `stop=None` draws no stop line and lets the axis follow the data: -1 R is
    the stop of one trade and means nothing under a sum of them, where the
    forced floor would flatten a good year. `bar_max` lets a dozen bars stand
    as columns instead of sticks; the width of a slot still governs when there
    are many.

    A win stands up from zero in green, a loss hangs down in red, a break-even
    is an amber tick on the line: the same three colours the front page counts
    a week in. The dashed line at -1 R is the stop as designed; a bar that
    reaches past it lost more than the risk allowed, and it shows without a
    word. Every bar
    opens its trade."""
    values = [r for r, _, _, _ in bars if r is not None]
    if not values:
        return '<p class="muted">No closed trades in this period.</p>'
    low = min(-1.5 if stop else 0.0, math.floor(min(values) * 2) / 2)
    high = max(1.0 if stop else 0.0, math.ceil(max(values) * 2) / 2)
    if high - low < 1e-9:              # one flat bar carries no scale of its own
        high = low + 1.0
    # the right margin held the word "stop" and is not needed without it;
    # the bottom one holds a second row when every bar carries its name
    slot = (width - 44 - (44 if stop else 16)) / len(bars)
    named = bool(labels) and slot >= 30
    pad = (44, 12, 44 if named else 30, 44 if stop else 16)  # left, top, bottom, right
    pw, ph = width - pad[0] - pad[3], height - pad[1] - pad[2]
    left, right = pad[0], width - pad[3]
    top, bottom = pad[1], pad[1] + ph
    bar_w = max(2.0, min(slot * 0.62, bar_max))

    def Y(v):
        return top + ph * (high - v) / (high - low)

    parts = [f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>']
    step = nice_step(high - low, target=5)
    v = math.ceil(low / step) * step
    while v <= high + 1e-9:
        y = Y(v)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" '
                     f'stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{left - 6}" y="{y + 3:.1f}" fill="{DIM}" '
                     f'font-size="10" font-family="{MONO}" text-anchor="end">'
                     f'{r_label(v, step)}</text>')
        v += step
    # where a week or a month begins: a line before the bar, a word under it
    edges = [i for i, _ in marks] + [len(bars)]
    for k, (i, label) in enumerate(marks):
        x = left + slot * i
        if i:
            parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" '
                         f'stroke="{AXIS}" stroke-width="1"/>')
        span = slot * (edges[k + 1] - i)
        if span >= 26:
            parts.append(f'<text x="{x + span / 2:.1f}" y="{height - 9}" fill="{DIM}" '
                         f'font-size="10" letter-spacing=".08em" text-anchor="middle">'
                         f'{esc(label)}</text>')
    if named:
        for i, label in enumerate(labels):
            parts.append(f'<text x="{left + slot * (i + 0.5):.1f}" y="{height - 24}" '
                         f'fill="{DIM}" font-size="10" letter-spacing=".04em" '
                         f'text-anchor="middle">{esc(label)}</text>')
    zero = Y(0.0)
    if stop:
        stop_y = Y(-stop)
        parts.append(f'<line x1="{left}" y1="{stop_y:.1f}" x2="{right}" '
                     f'y2="{stop_y:.1f}" stroke="{DIM}" stroke-width="1" '
                     f'stroke-dasharray="3 4"/>')
        parts.append(f'<text x="{right + 6}" y="{stop_y + 3:.1f}" fill="{DIM}" '
                     f'font-size="10">stop</text>')
    parts.append(f'<line x1="{left}" y1="{zero:.1f}" x2="{right}" y2="{zero:.1f}" '
                 f'stroke="{AXIS}" stroke-width="1"/>')
    for i, (r, result, href, words) in enumerate(bars):
        if r is None:
            continue
        x = left + slot * (i + 0.5) - bar_w / 2
        title = f"<title>{esc(words)}</title>"
        if result == "BE":
            rect = (f'<rect x="{x:.1f}" y="{zero - 1.5:.1f}" width="{bar_w:.1f}" '
                    f'height="3" fill="{WARN}">{title}</rect>')
        else:
            y = Y(r)
            colour = GOOD if result == "Win" else BAD
            y0, y1 = min(y, zero), max(y, zero)
            rect = (f'<rect x="{x:.1f}" y="{y0:.1f}" width="{bar_w:.1f}" '
                    f'height="{max(y1 - y0, 1.0):.1f}" fill="{colour}" '
                    f'fill-opacity=".82">{title}</rect>')
        parts.append(f'<a href="{esc(href)}">{rect}</a>' if href else rect)
    return (f'<svg class="tape" viewBox="0 0 {width} {height}" width="100%" '
            f'preserveAspectRatio="xMidYMid meet" role="img">' + "".join(parts) + "</svg>")


def r_label(v, step):
    """A figure on an R axis: whole numbers while the step is whole, the
    decimals of the step otherwise, so +2.5 is not written as +2."""
    decimals = 0
    while decimals < 2 and abs(step * 10 ** decimals - round(step * 10 ** decimals)) > 1e-9:
        decimals += 1
    return f"{v:+.{decimals}f}" if abs(v) > 1e-9 else "0"


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
      const fmt = n => String(n).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ' ');
      lines.push(s.name + ': ' + fmt(best[3]) + ' ' + s.sign);
      const away = best[5];
      lines.push((away < 0 ? '-' : '+') + fmt(Math.abs(away)) + ' ' + s.sign +
                 ' ' + s.base_word);
      if (best[4]) lines.push(best[4]);
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
    # the figures in the middle follow the ring: 30px in a ring of 188
    text, big = "", size * 30 / 188
    if middle:
        text += (f'<text x="{c}" y="{c - 1}" fill="{INK}" font-size="{big:g}" '
                 f'font-family="{MONO}" text-anchor="middle">{esc(middle)}</text>')
    if under:
        text += (f'<text x="{c}" y="{c + big * 17 / 30:g}" fill="{DIM}" font-size="11" '
                 f'text-anchor="middle">{esc(under)}</text>')
    # only the ring turns, so that the reading starts at twelve o'clock; the
    # text in the middle stays upright
    return (f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
            f'role="img"><g transform="rotate(-90 {c} {c})">'
            + "".join(parts) + f'</g>{text}</svg>')


def donut_legend(rows, total):
    """The slices in words: a chip, the bucket, how many and what share.

    A ring alone leaves the reader guessing at the sizes, so the numbers stand
    next to it and the colour only carries the order. The R is not repeated
    on every row: the middle of the ring carries the unit, and the row is
    read beside it."""
    lines = "".join(
        f'<tr data-slice="{i}"><td><i style="background:{colour}"></i>{esc(label)}</td>'
        f'<td class="num">{n}</td>'
        f'<td class="num muted">{100.0 * n / total:.0f}%</td>'
        f'<td class="num {"win" if sum_r > 0 else "lose" if sum_r < 0 else "muted"}">'
        f'{sum_r:+.1f}</td></tr>'
        for i, (label, n, sum_r, colour) in enumerate(rows) if n)
    return f'<table class="donut-legend"><tbody>{lines}</tbody></table>'


def legend(pairs):
    return '<div class="legend">' + "".join(
        f'<span><i style="background:{colour}"></i>{esc(name)}</span>'
        for name, colour in pairs) + "</div>"
