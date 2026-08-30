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

/* period switch — segments inside one frame */
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
/* there are many links in the table — they are painted as text, and the accent
   is kept for hovering */
td a{{color:{INK}}}
td a:hover{{color:{ACCENT}}}
tbody tr:hover td{{background:rgba(255,255,255,.028)}}
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
input[type=datetime-local],textarea{{background:{GROUND};color:{INK};
 border:1px solid {AXIS};border-radius:4px;padding:6px 8px;
 font:13px system-ui,sans-serif}}
input[type=number],input[type=date],input[type=datetime-local]{{
 font-family:{MONO};font-size:12px}}
select:hover,input:hover{{border-color:{DIM}}}
input[type=checkbox]{{accent-color:{ACCENT};vertical-align:-2px}}
select:focus,input:focus,textarea:focus{{outline:none;border-color:{ACCENT};
 box-shadow:0 0 0 2px rgba(111,157,255,.18)}}
textarea{{width:100%;min-height:78px;resize:vertical;line-height:1.55}}
.fields{{display:flex;gap:14px;flex-wrap:wrap}}
.field{{min-width:150px}}
.actions{{display:flex;gap:8px;align-items:center;margin:16px 0 0}}
.actions .right{{margin-left:auto}}

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
.caption a{{color:{INK2}}}

/* charts */
.legend{{display:flex;gap:16px;flex-wrap:wrap;margin:8px 0 0;font-size:11px;
 color:{INK2}}}
.legend i{{display:inline-block;width:8px;height:8px;border-radius:2px;
 margin-right:6px}}
.tip{{position:fixed;pointer-events:none;background:{RAISED};
 border:1px solid {AXIS};border-radius:4px;padding:6px 9px;font-size:11px;
 color:{INK};display:none;z-index:9;white-space:pre;
 font-family:{MONO};font-variant-numeric:tabular-nums}}
"""


def esc(s):
    return _html.escape("" if s is None else str(s), quote=True)


def money(x, signed=False):
    if x is None:
        return "—"
    text = f"{x:+,.0f}" if signed else f"{x:,.0f}"
    return text.replace(",", " ")


def page(title, body, tab="journal", header_right=""):
    links = [("journal", "/", "Journal"), ("cards", "/cards", "Cards"),
             ("stats", "/stats", "Statistics"),
             ("reports", "/reports", "Reports"), ("accounts", "/accounts", "Accounts")]
    nav = "".join(
        f'<a href="{href}" class="{"current" if code == tab else ""}">{name}</a>'
        for code, href, name in links)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{"TradingJournal" if title == "Journal"
          else "TradingJournal — " + esc(title)}</title><style>{CSS}</style>
<script>{HOVER}{PAGE_SCRIPT}</script></head><body>
<div class="wrap">
<header><span class="logo">TradingJournal</span><nav>{nav}</nav>
<span class="right">{header_right}</span></header>
{body}
</div>
<div class="tip" id="tip"></div>
</body></html>"""


# Small things shared by every page. The script sits in the head and hooks
# listeners onto document — before the markup, but document is already there.
PAGE_SCRIPT = """
function close_popovers(except){
  document.querySelectorAll('details.filters-box[open]').forEach(box => {
    if (!except || !box.contains(except)) box.open = false;
  });
}
document.addEventListener('click', e => close_popovers(e.target));
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') close_popovers(null);
});
"""


# --- charts ----------------------------------------------------------------

def equity_svg(series, width=980, height=260, cid="equity"):
    """Equity lines with hovering. series: [(name, colour, [(date, value)])].

    Only like quantities share a picture: accounts go on one chart, the total
    on its own. There are never two scales in one image.
    """
    series = [(name, colour, pts) for name, colour, pts in series if len(pts) > 1]
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
    # over a short stretch the month and the year would repeat — show days there
    fmt = "%d.%m" if (x1 - x0).days < 150 else "%m.%Y"
    for i in range(4):
        d = x0 + (x1 - x0) * (i / 3)
        parts.append(f'<text x="{X(d):.1f}" y="{height-8}" fill="{DIM}" '
                     f'font-size="10" text-anchor="middle">{d.strftime(fmt)}</text>')

    data = []
    for name, colour, pts in series:
        d = " ".join(f"{'M' if k == 0 else 'L'}{X(dt):.1f},{Y(v):.1f}"
                     for k, (dt, v) in enumerate(pts))
        parts.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="2" '
                     f'stroke-linejoin="round"/>')
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
  // the tip lives at the end of body — look it up while hovering, not at build
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
      // chart. Cutting by distance will not do — with sparse points the gaps
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


def histogram_svg(buckets, width=980, height=220):
    """R distribution. buckets: [(left, right, count)].

    Under every bar stands its R value with a sign — otherwise it is not clear
    which result the bar describes.
    """
    if not buckets:
        return '<p class="muted">Nothing to plot yet.</p>'
    pad = (34, 14, 34, 14)
    pw, ph = width - pad[0] - pad[3], height - pad[1] - pad[2]
    top = max(n for _, _, n in buckets) or 1
    step = pw / len(buckets)
    parts = [f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>']
    base = pad[1] + ph
    for i, (left, right, n) in enumerate(buckets):
        h = ph * n / top
        x = pad[0] + i * step + 1
        w = step - 2                               # a 2px gap between bars
        colour = BAD if right <= 0 else GOOD
        if n:
            r = min(4, w / 2, h)
            d = (f"M{x:.1f},{base:.1f} V{base-h+r:.1f} Q{x:.1f},{base-h:.1f} "
                 f"{x+r:.1f},{base-h:.1f} H{x+w-r:.1f} Q{x+w:.1f},{base-h:.1f} "
                 f"{x+w:.1f},{base-h+r:.1f} V{base:.1f} Z")
            parts.append(f'<path d="{d}" fill="{colour}">'
                         f'<title>R from {left:+.1f} to {right:+.1f}: {n} trades</title>'
                         f'</path>')
            parts.append(f'<text x="{x+w/2:.1f}" y="{base-h-4:.1f}" fill="{INK2}" '
                         f'font-size="10" text-anchor="middle">{n}</text>')
        # a label under every bar: the R range of that step, in one line
        parts.append(f'<text x="{x+w/2:.1f}" y="{base+16:.1f}" fill="{INK2}" '
                     f'font-size="10" text-anchor="middle">'
                     f'{left:+.1f}…{right:+.1f}</text>')
    parts.append(f'<line x1="{pad[0]}" y1="{base}" x2="{width-pad[3]}" y2="{base}" '
                 f'stroke="{AXIS}" stroke-width="1"/>')
    return (f'<svg viewBox="0 0 {width} {height}" width="100%" '
            f'preserveAspectRatio="xMidYMid meet" role="img">' + "".join(parts) + "</svg>")


def legend(pairs):
    return '<div class="legend">' + "".join(
        f'<span><i style="background:{colour}"></i>{esc(name)}</span>'
        for name, colour in pairs) + "</div>"
