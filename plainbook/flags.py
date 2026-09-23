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


def _disc(bg, fg, text, size=10.5):
    """A lettered coin, for metals and coins, which have no flag."""
    return (f'<rect width="24" height="24" fill="{bg}"/>'
            f'<text x="12" y="12.4" fill="{fg}" font-size="{size}" '
            f'font-weight="700" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="system-ui,-apple-system,sans-serif">{text}</text>')


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
    return ('<rect width="24" height="24" fill="#343841"/>'
            '<path d="M12 4.4C15.6 9 17.6 11.6 17.6 14.4a5.6 5.6 0 0 1-11.2 0'
            'C6.4 11.6 8.4 9 12 4.4Z" fill="#e0b13c"/>')


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
    # metals, coins and oil have no country, so they get a lettered face
    "xau": _disc("#d4af37", "#3d2f05", "Au"),
    "xag": _disc("#b8bdc4", "#2b2f34", "Ag"),
    "xpt": _disc("#8f9aa5", "#14181c", "Pt"),
    "xpd": _disc("#9aa08c", "#1a1c15", "Pd"),
    "btc": _disc("#f7931a", "#fff", "₿", 13),
    "eth": _disc("#627eea", "#fff", "Ξ", 13),
    "usdt": _disc("#26a17b", "#fff", "₮", 12),
    "usdc": _disc("#2775ca", "#fff", "$", 13),
    "oil": _oil(),
}

# --- what a symbol is made of ----------------------------------------------

CURRENCIES = {
    "USD": "us", "EUR": "eu", "GBP": "gb", "JPY": "jp", "CHF": "ch",
    "CAD": "ca", "AUD": "au", "NZD": "nz", "CNY": "cn", "CNH": "cn",
    "SEK": "se", "NOK": "no", "DKK": "dk", "ISK": "is", "PLN": "pl",
    "CZK": "cz", "HUF": "hu", "RUB": "ru", "TRY": "tr", "ZAR": "za",
    "MXN": "mx", "SGD": "sg", "HKD": "hk", "INR": "in", "BRL": "br",
    "KRW": "kr", "ILS": "il", "THB": "th",
    "XAU": "xau", "XAG": "xag", "XPT": "xpt", "XPD": "xpd",
    "BTC": "btc", "XBT": "btc", "ETH": "eth", "USDT": "usdt", "USDC": "usdc",
    "WTI": "oil", "BRENT": "oil", "XTI": "oil", "XBR": "oil",
    # brokers write the oils as pairs too: UKOUSD is Brent, USOUSD is WTI
    "UKO": "oil", "USO": "oil",
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
    "GOLD": "xau", "SILVER": "xag",
}

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
    # read whole first; only then is a suffix cut off (EURUSD.pro, US30_m)
    whole = _CLEAN.sub("", name)
    joined = _pair(whole)
    if joined:
        return joined
    name = _CLEAN.sub("", re.split(r"[.\-_]", name)[0])
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
    for size in (4, 3):                     # USDT first, then the three-letter codes
        head, tail = name[:size], name[size:]
        if head in CURRENCIES and tail in CURRENCIES:
            return [CURRENCIES[head], CURRENCIES[tail]]
    if not loose:
        return None
    for size in (4, 3):                     # a known base against an unknown quote
        head, tail = name[:size], name[size:]
        if head in CURRENCIES and 2 <= len(tail) <= 5:
            return [CURRENCIES[head], CURRENCIES.get(tail[:3], tail[:3])]
        if tail in CURRENCIES and 2 <= len(head) <= 5:
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
          '</svg>')


def _face(face, x):
    if face in FLAGS:
        return f'<use href="#fl-{face}" x="{x}" y="0" width="{2*R}" height="{2*R}"/>'
    # an unknown symbol still gets a coin: its letters on a colour of its own,
    # steady from page to page because it comes from the letters themselves
    hue = sum(ord(c) for c in face) * 47 % 360
    return (f'<circle cx="{x + R}" cy="{R}" r="{R}" fill="hsl({hue},38%,36%)"/>'
            f'<text x="{x + R}" y="{R + .4}" fill="#fff" font-size="7.4" '
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
        piece = _face(face, i * SHIFT)
        # every coin but the last is bitten into by the one that follows it
        body += (f'<g mask="url(#bite)">{piece}</g>'
                 if i < len(faces) - 1 else piece)
    return (f'<svg class="pi" viewBox="0 0 {width} {2*R}" width="{width}" '
            f'height="{2*R}" aria-hidden="true" focusable="false">{body}</svg>')
