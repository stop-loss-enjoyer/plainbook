#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Round icons for trading symbols, the way a terminal draws them: EURUSD is two
overlapping coins, the euro behind and the dollar in front.

The flags are drawn here rather than downloaded: nothing in this project comes
from a network (invariant 7), and a flag squeezed into 24 px is a handful of
rectangles anyway. They are deliberately coarse: at 18 px on the screen a coat
of arms is a smudge, so emblems are left out and only what identifies the flag
at a glance is kept.

The drawings go into the page once, as <symbol>s (SPRITE); every place that
shows a pair only refers to them by id.
"""
import math
import re

# --- drawing helpers -------------------------------------------------------

# Everything is drawn inside a 24x24 box and clipped to a circle by CLIP, so
# the corners are never seen: what matters must sit near the middle.


def _bands(colours, vertical=False):
    size = 24 / len(colours)
    out = []
    for i, colour in enumerate(colours):
        at = i * size
        out.append(f'<rect x="{at:.2f}" y="0" width="{size:.2f}" height="24" '
                   f'fill="{colour}"/>' if vertical else
                   f'<rect x="0" y="{at:.2f}" width="24" height="{size:.2f}" '
                   f'fill="{colour}"/>')
    return "".join(out)


def _cross(bg, cross, inner=None, x=9.2, width=4.4, arm=None):
    """A Nordic cross: the bar sits left of the middle and runs to the edges.

    With arm the cross is cut short instead. That is the Swiss one, and the
    short arms are what tell it apart from Denmark's."""
    span = (f"M{x} {12-arm}V{12+arm}M{12-arm} 12H{12+arm}" if arm
            else f"M{x} 0V24M0 12H24")
    out = [f'<rect width="24" height="24" fill="{bg}"/>',
           f'<path d="{span}" stroke="{cross}" stroke-width="{width}" fill="none"/>']
    if inner:
        out.append(f'<path d="{span}" stroke="{inner}" '
                   f'stroke-width="{width*0.45:.2f}" fill="none"/>')
    return "".join(out)


def _star(cx, cy, r, fill="#fff", turn=-90):
    points = []
    for i in range(10):
        radius = r if i % 2 == 0 else r * 0.382
        angle = math.radians(turn + i * 36)
        points.append(f"{cx + radius*math.cos(angle):.2f},"
                      f"{cy + radius*math.sin(angle):.2f}")
    return f'<polygon points="{" ".join(points)}" fill="{fill}"/>'


class _Coin(str):
    """A drawing that has a second version for when another coin sits on it."""

    def __new__(cls, body, back):
        self = super().__new__(cls, body)
        self.back = back
        return self


def _lettered(bg, fg, text, size, x):
    return (f'<rect width="24" height="24" fill="{bg}"/>'
            f'<text x="{x}" y="12.4" fill="{fg}" font-size="{size}" '
            f'font-weight="700" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="system-ui,-apple-system,sans-serif">{text}</text>')


def _disc(bg, fg, text, size=10.5):
    """A lettered coin, for metals and coins, which have no flag.

    The coin behind in a pair is covered from its middle to the right edge by
    the one in front, so it also gets a version with the letters moved into
    the part that stays in view, smaller, and cut to two letters when longer
    than three: the crypto base is nearly always the coin behind."""
    short = text[:2] if len(text) > 3 else text
    room = 12.4                                 # the width left of the bite
    fit = size if len(short) == 1 else min(size, room / (0.66 * len(short)))
    return _Coin(_lettered(bg, fg, text, size, 12),
                 _lettered(bg, fg, short, round(fit, 1), 7.2))


def _union_jack(scale=1.0):
    """The jack, full size for Britain and quartered for the flags built on it."""
    body = ('<rect width="24" height="24" fill="#012169"/>'
            '<path d="M0 0L24 24M24 0L0 24" stroke="#fff" stroke-width="5.2"/>'
            '<path d="M0 0L24 24M24 0L0 24" stroke="#c8102e" stroke-width="2.6"/>'
            '<path d="M12 0V24M0 12H24" stroke="#fff" stroke-width="8"/>'
            '<path d="M12 0V24M0 12H24" stroke="#c8102e" stroke-width="4.4"/>')
    if scale == 1.0:
        return body
    return f'<g transform="scale({scale})">{body}</g>'


def _usd():
    stripe = 24 / 13
    out = ['<rect width="24" height="24" fill="#fff"/>']
    for i in range(0, 13, 2):
        out.append(f'<rect y="{i*stripe:.2f}" width="24" height="{stripe:.2f}" '
                   f'fill="#b22234"/>')
    out.append(f'<rect width="11" height="{7*stripe:.2f}" fill="#3c3b6e"/>')
    # dots, not stars: fifty stars at this size are grey mush either way
    for row in range(4):
        for col in range(5):
            out.append(f'<circle cx="{1.2 + col*2.15:.2f}" '
                       f'cy="{1.3 + row*1.9:.2f}" r=".6" fill="#fff"/>')
    return "".join(out)


def _eur():
    out = ['<rect width="24" height="24" fill="#039"/>']
    for i in range(12):
        angle = math.radians(i * 30 - 90)
        out.append(_star(12 + 7.2*math.cos(angle), 12 + 7.2*math.sin(angle),
                         1.5, "#fc0"))
    return "".join(out)


def _cad():
    leaf = ("M12 5.1l1.05 2.35 2.2-.52-.5 2.2 1.3.3-2.2 1.85.5 1.15 2.4-.5"
            "-.3 1.25 2.05 1.7-.7.55.3 1.4-2.85-.5-.35 1.1-1.75-.35.2 3.1h-.9"
            "l.2-3.1-1.75.35-.35-1.1-2.85.5.3-1.4-.7-.55 2.05-1.7-.3-1.25"
            "2.4.5.5-1.15-2.2-1.85 1.3-.3-.5-2.2 2.2.52z")
    return ('<rect width="24" height="24" fill="#fff"/>'
            '<rect width="6" height="24" fill="#d80621"/>'
            '<rect x="18" width="6" height="24" fill="#d80621"/>'
            f'<path d="{leaf}" fill="#d80621"/>')


def _au():
    return ('<rect width="24" height="24" fill="#012169"/>' + _union_jack(0.5) +
            _star(6, 18.4, 2.4) + _star(18.6, 6.4, 1.5) +
            _star(21.2, 12.4, 1.5) + _star(17.4, 17, 1.6) +
            _star(21, 19.4, 1.1) + _star(16.4, 11.4, .85))


def _nz():
    out = ['<rect width="24" height="24" fill="#012169"/>', _union_jack(0.5)]
    for cx, cy, r in ((21, 8.6, 1.6), (17.2, 12, 1.5), (21.4, 15.8, 1.5),
                      (18.6, 19.6, 1.4)):
        out.append(_star(cx, cy, r + .5, "#fff"))
        out.append(_star(cx, cy, r - .35, "#c8102e"))
    return "".join(out)


def _cn():
    out = ['<rect width="24" height="24" fill="#de2910"/>', _star(6, 6.6, 3.4, "#fc0")]
    for cx, cy in ((11.6, 2.6), (13.6, 5.4), (13.4, 9), (11.2, 11.4)):
        out.append(_star(cx, cy, 1.3, "#fc0"))
    return "".join(out)


def _tr():
    return ('<rect width="24" height="24" fill="#e30a17"/>'
            '<circle cx="10.4" cy="12" r="6" fill="#fff"/>'
            '<circle cx="12.2" cy="12" r="4.8" fill="#e30a17"/>'
            + _star(17.4, 12, 2.9))


def _za():
    return ('<rect width="24" height="24" fill="#002395"/>'
            '<rect width="24" height="12" fill="#de3831"/>'
            '<g fill="none" stroke="#fff" stroke-width="9">'
            '<path d="M-3 -4L11 12H26"/><path d="M-3 28L11 12H26"/></g>'
            '<g fill="none" stroke="#007a4d" stroke-width="5">'
            '<path d="M-3 -4L11 12H26"/><path d="M-3 28L11 12H26"/></g>'
            '<path d="M-1 -2L10.6 12L-1 26Z" fill="#ffb612"/>'
            '<path d="M-1 2L8 12L-1 22Z" fill="#000"/>')


def _kr():
    return ('<rect width="24" height="24" fill="#fff"/>'
            '<circle cx="12" cy="12" r="5.8" fill="#0047a0"/>'
            '<path d="M6.2 12A2.9 2.9 0 0 1 12 12A2.9 2.9 0 0 0 17.8 12'
            'A5.8 5.8 0 0 0 6.2 12Z" fill="#cd2e3a"/>')


def _hk():
    petals = "".join(
        f'<ellipse cx="{12 + 4.2*math.cos(math.radians(i*72 - 90)):.2f}" '
        f'cy="{12 + 4.2*math.sin(math.radians(i*72 - 90)):.2f}" '
        f'rx="2.5" ry="1.7" fill="#fff" '
        f'transform="rotate({i*72} {12 + 4.2*math.cos(math.radians(i*72 - 90)):.2f} '
        f'{12 + 4.2*math.sin(math.radians(i*72 - 90)):.2f})"/>' for i in range(5))
    return f'<rect width="24" height="24" fill="#de2910"/>{petals}'


def _sg():
    stars = "".join(_star(cx, cy, 1.15) for cx, cy in
                    ((10.2, 3.2), (12.6, 4.9), (11.7, 7.7), (8.7, 7.7), (7.8, 4.9)))
    return ('<rect width="24" height="24" fill="#fff"/>'
            '<rect width="24" height="12" fill="#ed2939"/>'
            '<circle cx="4.6" cy="5.6" r="4.4" fill="#fff"/>'
            '<circle cx="6.6" cy="5.6" r="3.6" fill="#ed2939"/>' + stars)


def _il():
    triangle = ('<path d="M12 7.2L16.2 14.4H7.8Z" fill="none" stroke="#0038b8" '
                'stroke-width="1.1"/>')
    return ('<rect width="24" height="24" fill="#fff"/>'
            '<rect y="2.4" width="24" height="3" fill="#0038b8"/>'
            '<rect y="18.6" width="24" height="3" fill="#0038b8"/>'
            + triangle + triangle.replace('M12 7.2L16.2 14.4H7.8Z',
                                          'M12 16.8L7.8 9.6H16.2Z'))


def _in():
    return (_bands(["#ff9933", "#fff", "#138808"]) +
            '<circle cx="12" cy="12" r="2.9" fill="none" stroke="#000080" '
            'stroke-width="1"/>')


def _br():
    return ('<rect width="24" height="24" fill="#009b3a"/>'
            '<path d="M12 2.6L21.4 12L12 21.4L2.6 12Z" fill="#fedf00"/>'
            '<circle cx="12" cy="12" r="4.2" fill="#002776"/>'
            '<path d="M8 11.1A5.4 5.4 0 0 1 16 11.6" fill="none" stroke="#fff" '
            'stroke-width="1.1"/>')


def _oil():
    def drop(shift):
        return ('<rect width="24" height="24" fill="#343841"/>'
                f'<g transform="translate({shift} 0)">'
                '<path d="M12 4.4C15.6 9 17.6 11.6 17.6 14.4a5.6 5.6 0 0 1-11.2 0'
                'C6.4 11.6 8.4 9 12 4.4Z" fill="#e0b13c"/></g>')
    return _Coin(drop(0), drop(-4.6))


def _field(colour):
    return f'<rect width="24" height="24" fill="{colour}"/>'


def _rect(x, y, w, h, colour):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{colour}"/>'


def _pentagram(cx, cy, r, stroke, width=1.3):
    """An outlined five-pointed star, the way Morocco draws it."""
    points = " ".join(
        f"{cx + r*math.cos(math.radians(-90 + i*144)):.2f},"
        f"{cy + r*math.sin(math.radians(-90 + i*144)):.2f}" for i in range(5))
    return (f'<polygon points="{points}" fill="none" stroke="{stroke}" '
            f'stroke-width="{width}" stroke-linejoin="round"/>')


def _teeth(base, tip, count, colour):
    """A strip down the hoist with a saw edge: Qatar's and Bahrain's white."""
    step = 24 / count
    edge = "".join(f"L{tip} {i*step + step/2:.2f}L{base} {(i+1)*step:.2f}"
                   for i in range(count))
    return f'<path d="M0 0H{base}{edge}H0Z" fill="{colour}"/>'


def _sa():
    # the writing and the sword shrink to a bar and a line at this size
    return (_field("#006c35") + _rect(5, 7.6, 14, 2.2, "#fff") +
            _rect(6, 15, 12, 1.3, "#fff") + _rect(15.4, 13.4, 1.4, 4.6, "#fff"))


def _my():
    out = [_rect(0, i*3, 24, 3, "#cc0001" if i % 2 == 0 else "#fff")
           for i in range(8)]
    out += [_rect(0, 0, 13, 12, "#010066"),
            '<circle cx="5.8" cy="6" r="3.8" fill="#fc0"/>'
            '<circle cx="7" cy="6" r="3.1" fill="#010066"/>',
            _star(9.8, 6, 1.9, "#fc0")]
    return "".join(out)


def _tw():
    return (_field("#fe0000") + _rect(0, 0, 12, 12, "#000095") +
            '<circle cx="6" cy="6" r="3.5" fill="#fff"/>'
            '<circle cx="6" cy="6" r="2.5" fill="#000095"/>'
            '<circle cx="6" cy="6" r="1.7" fill="#fff"/>')


def _pk():
    return (_field("#01411c") + _rect(0, 0, 6, 24, "#fff") +
            '<circle cx="14.4" cy="12.4" r="4.6" fill="#fff"/>'
            '<circle cx="16" cy="11.4" r="4" fill="#01411c"/>' +
            _star(17.6, 8.8, 1.8))


def _kz():
    return (_field("#00afca") + _rect(1.8, 0, 2.2, 24, "#fec50c") +
            '<circle cx="13" cy="9.4" r="3.4" fill="#fec50c"/>'
            '<circle cx="13" cy="9.4" r="5.4" fill="none" stroke="#fec50c" '
            'stroke-width="1" stroke-dasharray="1.1 1.3"/>'
            '<path d="M7 18Q13 14 19 18Q13 16.8 7 18Z" fill="#fec50c"/>')


def _ge():
    cross = "".join(f'<path d="M{x-1.2} {y}h2.4M{x} {y-1.2}v2.4" stroke="#f00" '
                    f'stroke-width="1.2"/>'
                    for x, y in ((5.4, 5.4), (18.6, 5.4), (5.4, 18.6), (18.6, 18.6)))
    return (_field("#fff") + _rect(10.4, 0, 3.2, 24, "#f00") +
            _rect(0, 10.4, 24, 3.2, "#f00") + cross)


def _rs():
    return (_bands(["#c6363c", "#0c4076", "#fff"]) +
            '<path d="M5.4 7.2h6.2v5.4a3.1 3.1 0 0 1-6.2 0z" fill="#c6363c" '
            'stroke="#fff" stroke-width=".9"/>')


def _ke():
    return (_rect(0, 0, 24, 8, "#000") + _rect(0, 8, 24, 1.2, "#fff") +
            _rect(0, 9.2, 24, 5.6, "#bb0000") + _rect(0, 14.8, 24, 1.2, "#fff") +
            _rect(0, 16, 24, 8, "#006600") +
            '<ellipse cx="12" cy="12" rx="3.4" ry="6" fill="#fff"/>'
            '<ellipse cx="12" cy="12" rx="2.3" ry="4.7" fill="#bb0000"/>')


def _pt():
    return (_field("#da291c") + _rect(0, 0, 9.6, 24, "#046a38") +
            '<circle cx="9.6" cy="12" r="3.2" fill="#ffd700"/>'
            '<circle cx="9.6" cy="12" r="1.7" fill="#da291c"/>')


def _kw():
    return (_bands(["#007a3d", "#fff", "#ce1126"]) +
            '<path d="M0 0L9 8.4V15.6L0 24Z" fill="#000"/>')


def _jo():
    return (_bands(["#000", "#fff", "#007a3d"]) +
            '<path d="M0 0L12.6 12L0 24Z" fill="#ce1126"/>' + _star(4.4, 12, 1.5))


def _ph():
    return (_bands(["#0038a8", "#ce1126"]) +
            '<path d="M0 0L14 12L0 24Z" fill="#fff"/>'
            '<circle cx="4.4" cy="12" r="1.9" fill="#fcd116"/>')


def _cl():
    return (_field("#fff") + _rect(0, 12, 24, 12, "#d52b1e") +
            _rect(0, 0, 11, 12, "#0039a6") + _star(5.5, 6.2, 2.9))


def _co():
    return (_rect(0, 0, 24, 12, "#fcd116") + _rect(0, 12, 24, 6, "#003893") +
            _rect(0, 18, 24, 6, "#ce1126"))


def _gas():
    def flame(shift):
        return ('<rect width="24" height="24" fill="#343841"/>'
                f'<g transform="translate({shift} 0)">'
                '<path d="M12 3.8C14.2 7 17.6 9.6 17.6 14.2a5.6 5.6 0 0 1-11.2 0'
                'c0-2 .9-3.7 2.2-4.9.2 1.5.9 2.3 1.8 2.6C9.9 8.8 10.6 6 12 3.8Z" '
                'fill="#4da3e8"/>'
                '<path d="M12 12.2c1.4 1.5 2.4 2.5 2.4 3.9a2.4 2.4 0 0 1-4.8 0'
                'c0-1.4 1-2.4 2.4-3.9Z" fill="#cfe8ff"/></g>')
    return _Coin(flame(0), flame(-4.6))


# --- the flags -------------------------------------------------------------

FLAGS = {
    "us": _usd(),
    "eu": _eur(),
    "gb": _union_jack(),
    "jp": '<rect width="24" height="24" fill="#fff"/>'
          '<circle cx="12" cy="12" r="7.2" fill="#bc002d"/>',
    "ch": _cross("#d52b1e", "#fff", x=12, width=4.4, arm=6.6),
    "ca": _cad(),
    "au": _au(),
    "nz": _nz(),
    "cn": _cn(),
    "se": _cross("#006aa7", "#fecc00", x=9.2, width=4.4),
    "no": _cross("#ba0c2f", "#fff", "#00205b", x=9.2, width=5),
    "dk": _cross("#c8102e", "#fff", x=9.2, width=4.4),
    "fi": _cross("#fff", "#003580", x=9.2, width=4.4),
    "is": _cross("#02529c", "#fff", "#dc1e35", x=9.2, width=5),
    "de": _bands(["#000", "#dd0000", "#ffce00"]),
    "fr": _bands(["#002395", "#fff", "#ed2939"], vertical=True),
    "it": _bands(["#008c45", "#f4f5f0", "#cd212a"], vertical=True),
    "nl": _bands(["#ae1c28", "#fff", "#21468b"]),
    "es": '<rect width="24" height="24" fill="#aa151b"/>'
          '<rect y="6" width="24" height="12" fill="#f1bf00"/>',
    "pl": '<rect width="24" height="24" fill="#fff"/>'
          '<rect y="12" width="24" height="12" fill="#dc143c"/>',
    "cz": '<rect width="24" height="24" fill="#fff"/>'
          '<rect y="12" width="24" height="12" fill="#d7141a"/>'
          '<path d="M0 0L12 12L0 24Z" fill="#11457e"/>',
    "hu": _bands(["#cd2a3e", "#fff", "#436f4d"]),
    "ru": _bands(["#fff", "#0039a6", "#d52b1e"]),
    "tr": _tr(),
    "za": _za(),
    "mx": _bands(["#006847", "#fff", "#ce1126"], vertical=True) +
          '<circle cx="12" cy="12" r="2.4" fill="none" stroke="#8c6239" '
          'stroke-width="1.2"/>',
    "sg": _sg(),
    "hk": _hk(),
    "in": _in(),
    "br": _br(),
    "kr": _kr(),
    "il": _il(),
    "th": '<rect width="24" height="24" fill="#a51931"/>'
          '<rect y="4" width="24" height="16" fill="#f4f5f8"/>'
          '<rect y="8" width="24" height="8" fill="#2d2a4a"/>',
    "at": _bands(["#ed2939", "#fff", "#ed2939"]),
    "be": _bands(["#000", "#fdda24", "#ef3340"], vertical=True),
    "pt": _pt(),
    # the Gulf: green, white and black or red fields, told apart by what the
    # hoist carries
    "sa": _sa(),
    "ae": _bands(["#00732f", "#fff", "#000"]) + _rect(0, 0, 7, 24, "#f00"),
    "qa": _field("#8d1b3d") + _teeth(7, 11, 9, "#fff"),
    "kw": _kw(),
    "bh": _field("#ce1126") + _teeth(8, 13, 5, "#fff"),
    "om": _bands(["#fff", "#db161b", "#008000"]) + _rect(0, 0, 7, 24, "#db161b"),
    "jo": _jo(),
    "ro": _bands(["#002b7f", "#fcd116", "#ce1126"], vertical=True),
    "bg": _bands(["#fff", "#00966e", "#d62612"]),
    # Serbia is Russia upside down; the shield on the hoist is what tells them
    "rs": _rs(),
    "ua": _bands(["#0057b7", "#ffd700"]),
    "kz": _kz(),
    "ge": _ge(),
    "tw": _tw(),
    # Indonesia is Poland turned over; only the order of the two fields differs
    "id": _bands(["#ce1126", "#fff"]),
    "my": _my(),
    "ph": _ph(),
    "vn": _field("#da251d") + _star(12, 12.8, 6.8, "#ff0"),
    "pk": _pk(),
    "cl": _cl(),
    "co": _co(),
    "pe": _bands(["#d91023", "#fff", "#d91023"], vertical=True),
    "ar": _bands(["#74acdf", "#fff", "#74acdf"]) +
          '<circle cx="12" cy="12" r="2.3" fill="#f6b40e"/>',
    "eg": _bands(["#ce1126", "#fff", "#000"]) +
          '<circle cx="12" cy="12" r="1.9" fill="#c09300"/>',
    "ng": _bands(["#008751", "#fff", "#008751"], vertical=True),
    "ke": _ke(),
    "ma": _field("#c1272d") + _pentagram(12, 12.6, 5.6, "#006233"),
    "gh": _bands(["#ce1126", "#fcd116", "#006b3f"]) + _star(12, 12.4, 3.6, "#000"),
    # metals, coins, oil and the farm goods have no country, so they get a
    # face of their own
    "xau": _disc("#d4af37", "#3d2f05", "Au"),
    "xag": _disc("#b8bdc4", "#2b2f34", "Ag"),
    "xpt": _disc("#8f9aa5", "#14181c", "Pt"),
    "xpd": _disc("#9aa08c", "#1a1c15", "Pd"),
    "xcu": _disc("#b87333", "#2e1a08", "Cu"),
    "btc": _disc("#f7931a", "#fff", "₿", 13),
    "eth": _disc("#627eea", "#fff", "Ξ", 13),
    "usdt": _disc("#26a17b", "#fff", "₮", 12),
    "usdc": _disc("#2775ca", "#fff", "$", 13),
    "oil": _oil(),
    "gas": _gas(),
    "coffee": _disc("#6f4e37", "#fff", "Cf"),
    "cocoa": _disc("#4a2c1a", "#e8c9a0", "Cc"),
    "sugar": _disc("#ece8e1", "#3b3b3b", "Su"),
    "wheat": _disc("#b8863b", "#fff", "Wh"),
    "corn": _disc("#f0c419", "#3d3000", "Cn"),
    "soy": _disc("#6b8e23", "#fff", "Sy"),
    "cotton": _disc("#9fb8d6", "#1f2f45", "Ct"),
    # a coin in its brand colour, the symbol short enough for 18 px
    "sol": _disc("#9945ff", "#fff", "SOL", 8.4),
    "xrp": _disc("#23292f", "#fff", "XRP", 8.4),
    "bnb": _disc("#f3ba2f", "#1e1e1e", "BNB", 8.4),
    "doge": _disc("#c2a633", "#fff", "Ð", 13),
    "ada": _disc("#0033ad", "#fff", "ADA", 8.4),
    "trx": _disc("#ef0027", "#fff", "TRX", 8.4),
    "ton": _disc("#0098ea", "#fff", "TON", 8.4),
    "avax": _disc("#e84142", "#fff", "AVAX", 6.6),
    "dot": _disc("#e6007a", "#fff", "DOT", 8.4),
    "link": _disc("#2a5ada", "#fff", "LINK", 6.6),
    "ltc": _disc("#345d9d", "#fff", "Ł", 13),
    "bch": _disc("#8dc351", "#fff", "₿", 13),
    "shib": _disc("#e2711d", "#fff", "SHIB", 6.4),
    "pol": _disc("#8247e5", "#fff", "POL", 8.4),
    "near": _disc("#1b1b1b", "#fff", "NEAR", 6.4),
    "atom": _disc("#2e3148", "#fff", "ATOM", 6.4),
    "xlm": _disc("#14b6e7", "#0b1f33", "XLM", 8.4),
    "uni": _disc("#ff007a", "#fff", "UNI", 8.4),
    "apt": _disc("#2dd8a7", "#0b2a22", "APT", 8.4),
    "arb": _disc("#28a0f0", "#fff", "ARB", 8.4),
    "op": _disc("#ff0420", "#fff", "OP", 11),
    "sui": _disc("#4da2ff", "#fff", "SUI", 8.4),
    "pepe": _disc("#3d8b2f", "#fff", "PEPE", 6.4),
    "xmr": _disc("#ff6600", "#fff", "XMR", 8.4),
    "etc": _disc("#3ab83a", "#0b2a0b", "ETC", 8.4),
    "fil": _disc("#0090ff", "#fff", "FIL", 9),
    "hbar": _disc("#222", "#fff", "HBAR", 6.4),
}

# the version of a drawing for the coin behind, where there is one
BACK = {code: body.back for code, body in FLAGS.items()
        if isinstance(body, _Coin)}

# --- what a symbol is made of ----------------------------------------------

CURRENCIES = {
    "USD": "us", "EUR": "eu", "GBP": "gb", "JPY": "jp", "CHF": "ch",
    "CAD": "ca", "AUD": "au", "NZD": "nz", "CNY": "cn", "CNH": "cn",
    "SEK": "se", "NOK": "no", "DKK": "dk", "ISK": "is", "PLN": "pl",
    "CZK": "cz", "HUF": "hu", "RUB": "ru", "TRY": "tr", "ZAR": "za",
    "MXN": "mx", "SGD": "sg", "HKD": "hk", "INR": "in", "BRL": "br",
    "KRW": "kr", "ILS": "il", "THB": "th",
    "SAR": "sa", "AED": "ae", "QAR": "qa", "KWD": "kw", "BHD": "bh",
    "OMR": "om", "JOD": "jo", "RON": "ro", "BGN": "bg", "RSD": "rs",
    "UAH": "ua", "KZT": "kz", "GEL": "ge", "TWD": "tw", "IDR": "id",
    "MYR": "my", "PHP": "ph", "VND": "vn", "PKR": "pk", "CLP": "cl",
    "COP": "co", "PEN": "pe", "ARS": "ar", "EGP": "eg", "NGN": "ng",
    "KES": "ke", "MAD": "ma", "GHS": "gh",
    "XAU": "xau", "XAG": "xag", "XPT": "xpt", "XPD": "xpd", "XCU": "xcu",
    "BTC": "btc", "XBT": "btc", "ETH": "eth", "USDT": "usdt", "USDC": "usdc",
    "WTI": "oil", "BRENT": "oil", "XTI": "oil", "XBR": "oil",
    # brokers write the oils as pairs too: UKOUSD is Brent, USOUSD is WTI
    "UKO": "oil", "USO": "oil",
    # and the gas: XNGUSD at one broker, NGASUSD at another
    "XNG": "gas", "NGAS": "gas",
    # a crypto symbol is a base against a dollar, so the base is a code
    "SOL": "sol", "XRP": "xrp", "BNB": "bnb", "DOGE": "doge", "ADA": "ada",
    "TRX": "trx", "TON": "ton", "AVAX": "avax", "DOT": "dot", "LINK": "link",
    "LTC": "ltc", "BCH": "bch", "SHIB": "shib", "MATIC": "pol", "POL": "pol",
    "NEAR": "near", "ATOM": "atom", "XLM": "xlm", "UNI": "uni", "APT": "apt",
    "ARB": "arb", "OP": "op", "SUI": "sui", "PEPE": "pepe", "XMR": "xmr",
    "ETC": "etc", "FIL": "fil", "HBAR": "hbar",
}

# An index is one place, not a pair: it gets a single coin.
INDICES = {
    "US30": "us", "US100": "us", "US500": "us", "US2000": "us", "NAS100": "us",
    "NDX100": "us", "SPX500": "us", "SP500": "us", "USTEC": "us", "DJI": "us",
    "NDX": "us", "SPX": "us", "DXY": "us", "USDX": "us",
    "USOIL": "oil", "UKOIL": "oil", "WTICO": "oil",
    "GER30": "de", "GER40": "de", "DE40": "de", "DAX": "de", "DAX40": "de",
    "UK100": "gb", "FTSE": "gb", "FTSE100": "gb",
    "JPN225": "jp", "JP225": "jp", "NIKKEI": "jp",
    "FRA40": "fr", "CAC40": "fr", "ESP35": "es", "SPA35": "es",
    "ITA40": "it", "NETH25": "nl", "SWI20": "ch", "AUS200": "au",
    "HK50": "hk", "CHINA50": "cn", "IND50": "in",
    "EU50": "eu", "EUSTX50": "eu", "STOXX50": "eu", "ESX50": "eu",
    "GOLD": "xau", "SILVER": "xag", "COPPER": "xcu",
    "VIX": "us", "RUSSELL2000": "us", "WS30": "us",
    "SA40": "za", "SAF40": "za",
    "CHINAH": "hk", "HSCEI": "hk", "HSI": "hk", "HK33": "hk",
    "SG30": "sg", "SGP30": "sg",
    "NOR25": "no", "SWE30": "se",
    "NIFTY": "in", "NIFTY50": "in",
    "KOSPI": "kr", "KR200": "kr",
    "TWIX": "tw", "TW50": "tw",
    "MEX35": "mx", "BRA50": "br", "IBOV": "br",
    "POL20": "pl", "AUT20": "at", "BEL20": "be", "PORT20": "pt",
    # the other energy and the farm goods are goods, not pairs: brokers
    # quote them against nothing, and each gets one coin
    "NATGAS": "gas", "NATURALGAS": "gas", "NG": "gas",
    "COFFEE": "coffee", "COCOA": "cocoa", "SUGAR": "sugar", "WHEAT": "wheat",
    "CORN": "corn", "SOYBEAN": "soy", "SOYBEANS": "soy", "COTTON": "cotton",
}

# What the Accounts tab offers to tick when an account is opened, so the list
# of pairs a trader picks from starts as the instruments brokers really sell
# instead of an empty box. Written the way most brokers write them; anything
# else is still typed by hand and still gets its coins.
CATALOGUE = (
    ("Forex majors", (
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
    )),
    ("Forex minors", (
        "EURGBP", "EURJPY", "EURCHF", "EURCAD", "EURAUD", "EURNZD",
        "GBPJPY", "GBPCHF", "GBPCAD", "GBPAUD", "GBPNZD",
        "CHFJPY", "CADJPY", "AUDJPY", "NZDJPY",
        "CADCHF", "AUDCHF", "NZDCHF", "AUDCAD", "NZDCAD", "AUDNZD",
    )),
    ("Forex exotics", (
        "USDTRY", "USDZAR", "USDMXN", "USDSGD", "USDHKD", "USDNOK", "USDSEK",
        "USDDKK", "USDPLN", "USDHUF", "USDCZK", "USDCNH", "USDILS", "USDTHB",
        "USDINR", "USDBRL", "USDKRW", "USDRON", "USDSAR", "USDAED", "USDCLP",
        "USDCOP", "USDTWD", "USDIDR", "USDPHP",
        "EURTRY", "EURPLN", "EURNOK", "EURSEK", "EURDKK", "EURHUF", "EURCZK",
        "EURZAR", "EURMXN", "EURRON", "EURILS",
    )),
    ("Metals", (
        "XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "XCUUSD", "XAUEUR",
    )),
    ("Energy", (
        "USOIL", "UKOIL", "NATGAS",
    )),
    ("Commodities", (
        "COFFEE", "COCOA", "SUGAR", "WHEAT", "CORN", "SOYBEAN", "COTTON",
    )),
    ("Indices", (
        "US30", "US500", "NAS100", "US2000", "VIX", "DXY",
        "GER40", "UK100", "FRA40", "EU50", "ESP35", "ITA40", "NETH25", "SWI20",
        "JPN225", "HK50", "CHINA50", "AUS200", "IND50", "SA40", "SG30",
    )),
    ("Crypto", (
        "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "BNBUSD", "DOGEUSD", "ADAUSD",
        "TRXUSD", "TONUSD", "AVAXUSD", "DOTUSD", "LINKUSD", "LTCUSD", "BCHUSD",
        "SHIBUSD", "POLUSD", "NEARUSD", "ATOMUSD", "XLMUSD", "UNIUSD",
        "APTUSD", "ARBUSD", "OPUSD", "SUIUSD",
    )),
)

_CLEAN = re.compile(r"[^A-Z0-9]")


def parts(symbol):
    """The one or two faces of a symbol.

    Each is either an id in FLAGS or, for something unknown, the letters to
    write on a plain coin. Nothing recognisable at all, such as an empty name
    or "pair not set", gets no icon: a question mark in every row would be noise.
    """
    name = (symbol or "").upper().strip()
    # a ticker is one word: "pair not set" is a state, not a symbol
    if not name or " " in name:
        return []
    # a broker that writes the two currencies apart (EUR_USD, XAU/USD) is
    # read whole; a suffix is cut off (EURUSD.pro, US30_m) first when the
    # name before it is a pair by itself, or USDCAD.a would read as USDC and ADA
    whole = _CLEAN.sub("", name)
    base = _CLEAN.sub("", re.split(r"[.\-_]", name)[0])
    joined = (_pair(base) if base != whole else None) or _pair(whole)
    if joined:
        return joined
    name = base
    if not name or len(name) > 12:
        return []
    if name in INDICES:
        return [INDICES[name]]
    if name in CURRENCIES:
        return [CURRENCIES[name]]
    return _pair(name) or _pair(name, loose=True) or [name[:3]]


def _pair(name, loose=False):
    """Two faces out of one name, or None. Loose: one side may be a word
    the table does not know, such as a broker's suffix glued to the quote
    (EURUSDm), and its first three letters are looked up before they are
    written on a plain coin."""
    # Six letters are two three-letter codes: USDCOP is the dollar and the
    # peso, not USDC and OP. Longer names try the longer heads first (MATIC,
    # USDT), and the two-letter code (OP) is tried last, so it never steals a
    # letter.
    sizes = (3, 4, 2) if len(name) == 6 else (5, 4, 3, 2)
    for size in sizes:
        head, tail = name[:size], name[size:]
        if head in CURRENCIES and tail in CURRENCIES:
            return [CURRENCIES[head], CURRENCIES[tail]]
    if not loose:
        return None
    for size in (4, 3):                     # a known base, then a known quote with a suffix
        head, tail = name[:size], name[size:]
        if head in CURRENCIES:
            for t in (4, 3):
                if tail[:t] in CURRENCIES:
                    return [CURRENCIES[head], CURRENCIES[tail[:t]]]
    for size in (4, 3):                     # a known base against an unknown quote
        head, tail = name[:size], name[size:]
        if head in CURRENCIES and 2 <= len(tail) <= 5:
            return [CURRENCIES[head], CURRENCIES.get(tail[:3], tail[:3])]
        # three letters at least: a ticker that merely ends in OP is not a pair
        if tail in CURRENCIES and len(tail) >= 3 and 2 <= len(head) <= 5:
            return [CURRENCIES.get(head[:3], head[:3]), CURRENCIES[tail]]
    return None


# --- the markup ------------------------------------------------------------

R = 9                                       # coin radius, in page pixels
SHIFT = 12                                  # how far the second coin is moved

SPRITE = ('<svg class="sprite" aria-hidden="true" focusable="false">'
          '<defs>'
          '<clipPath id="coin" clipPathUnits="userSpaceOnUse">'
          '<circle cx="12" cy="12" r="12"/></clipPath>'
          # the coin in front bites a gap out of the one behind, so two dark
          # flags still read as two circles
          f'<mask id="bite" maskUnits="userSpaceOnUse" x="0" y="0" '
          f'width="{SHIFT + 2*R}" height="{2*R}">'
          f'<rect width="{SHIFT + 2*R}" height="{2*R}" fill="#fff"/>'
          f'<circle cx="{SHIFT + R}" cy="{R}" r="{R + 1.3}" fill="#000"/>'
          '</mask></defs>' +
          "".join(f'<symbol id="fl-{code}" viewBox="0 0 24 24">'
                  f'<g clip-path="url(#coin)">{body}</g></symbol>'
                  for code, body in FLAGS.items()) +
          "".join(f'<symbol id="fl-{code}-b" viewBox="0 0 24 24">'
                  f'<g clip-path="url(#coin)">{body}</g></symbol>'
                  for code, body in BACK.items()) +
          '</svg>')


def _face(face, x, behind=False):
    if face in FLAGS:
        # the coin behind keeps what it shows in the part the next one leaves
        name = f"{face}-b" if behind and face in BACK else face
        return f'<use href="#fl-{name}" x="{x}" y="0" width="{2*R}" height="{2*R}"/>'
    # an unknown symbol still gets a coin: its letters on a colour of its own,
    # steady from page to page because it comes from the letters themselves
    hue = sum(ord(c) for c in face) * 47 % 360
    return (f'<circle cx="{x + R}" cy="{R}" r="{R}" fill="hsl({hue},38%,36%)"/>'
            f'<text x="{x + (R - 3.6 if behind else R)}" y="{R + .4}" fill="#fff" '
            f'font-size="{5.4 if behind else 5.8 if set(face) & set("WM") else 7.4}" '
            f'font-weight="700" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="system-ui,-apple-system,sans-serif">{face[:3]}</text>')


def icon(symbol):
    """The coins for a symbol, as an <svg>. An empty string when there is
    nothing to draw."""
    faces = parts(symbol)
    if not faces:
        return ""
    width = 2*R + SHIFT*(len(faces) - 1)
    body = ""
    for i, face in enumerate(faces):
        behind = i < len(faces) - 1
        piece = _face(face, i * SHIFT, behind)
        # every coin but the last is bitten into by the one that follows it
        body += f'<g mask="url(#bite)">{piece}</g>' if behind else piece
    return (f'<svg class="pi" viewBox="0 0 {width} {2*R}" width="{width}" '
            f'height="{2*R}" aria-hidden="true" focusable="false">{body}</svg>')


def standalone(symbol, x, y, height):
    """The coins of a symbol for a picture that stands alone, at (x, y) and
    `height` tall, and how wide they came out: ("", 0) with nothing to draw.

    `icon` points at the sprite of the page, which a picture rasterised on its
    own does not have, so the drawings it uses are brought along with it."""
    coins = icon(symbol)
    if not coins:
        return "", 0
    used = set(re.findall(r'#fl-([\w-]+)', coins))
    defs = re.search(r"<defs>.*?</defs>", SPRITE, re.S).group(0)
    kept = "".join(m.group(0) for m in
                   re.finditer(r'<symbol id="fl-([\w-]+)".*?</symbol>', SPRITE, re.S)
                   if m.group(1) in used)
    across = int(re.search(r'viewBox="0 0 (\d+) ', coins).group(1))
    width = round(height * across / (2*R))
    head = (f'<svg x="{x}" y="{y}" width="{width}" height="{height}" '
            f'viewBox="0 0 {across} {2*R}">')
    return defs + kept + head + coins[coins.index(">") + 1:], width
