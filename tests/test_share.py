#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What leaves the journal: the document holds the trade and not the money."""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import share, store
from plainbook.balances import Journal
from plainbook.html import GROUND
from plainbook.model import (Account, IdeaBlock, PAIR_NOT_SET, Plan, Playbook, Rule,
                             Setup, Trade)

# a one-pixel PNG, enough to be carried into a document
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "05572bd6a20000000049454e44ae426082")

# figures nothing else in a document could produce, so that finding one of them
# in the text means it leaked out of the journal
START_BALANCE = 98765.0
PNL = 4321.0


def without_pictures(text):
    """The document as words: the pictures are base64, and any three digits
    can be found inside them by accident."""
    return re.sub(r"data:image/[a-z]+;base64,[^\"]+", "PICTURE", text)


class ShareCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.save_account(cls.root, Account(id="broker", name="Broker",
                                             start_balance=START_BALANCE))
        book = Playbook(id="sweep", name="Sweep", version="v2",
                        setups=[Setup(name="", rules=[
                            Rule(number=1, text="The level was swept"),
                            Rule(number=2, text="Entry on the retest"),
                        ])],
                        management=[Rule(number=3, text="Stop to break-even at 1 R")])
        store.save_playbook(cls.root, book)
        cls.book = book
        k = Plan(id="2026-08-12-eurusd", title="Sweep of the Asian high",
                 pair="EURUSD", narrative="bullish",
                 day=datetime(2026, 8, 12).date(),
                 until=datetime(2026, 8, 14).date(),
                 analysis=[IdeaBlock(tf="D1", text="Higher lows into the level.",
                                     images=["shots/idea-01-01.png"])],
                 plan="Buy the sweep of the Asian high only.",
                 updates="**13.08.2026**: swept, waiting for the retest"
                         "\n![](shots/update-01.png)",
                 review="It played out.\n\n![](shots/review-01.png)")
        store.save_plan(cls.root, k)
        folder = os.path.join(store.plan_dir(cls.root, k.id), store.SHOTS)
        os.makedirs(folder, exist_ok=True)
        for name in ("idea-01-01.png", "update-01.png", "review-01.png"):
            with open(os.path.join(folder, name), "wb") as f:
                f.write(PNG)
        cls.k = k
        t = Trade(id="2026-08-12-01-eurusd", account="broker", pair="EURUSD",
                  direction="long", style="swing", entry_tf="H4",
                  execution=["SNR"], risk=0.85,
                  opened=datetime(2026, 8, 12, 10, 30), opened_time=True,
                  result="Win", pnl=PNL, closed=datetime(2026, 8, 14),
                  plan="2026-08-12-eurusd",
                  playbook="sweep", playbook_version="v2",
                  deviations=[2], exit_deviations=[],
                  reasons={2: "Entered before the retest was done"},
                  idea=[IdeaBlock(tf="H4", text="Asian high swept.",
                                  images=["shots/idea-01.png"])],
                  exit_images=["shots/exit-01.png"],
                  updates="**13.08.2026 09:00**: stop moved under the sweep"
                          "\n![](shots/update-01.png)",
                  conclusions="Target hit.\n\n![](shots/note-01.png)")
        store.save_trade(cls.root, t)
        folder = os.path.join(store.trade_dir(cls.root, t.id), store.SHOTS)
        os.makedirs(folder, exist_ok=True)
        for name in ("idea-01.png", "exit-01.png", "note-01.png", "update-01.png"):
            with open(os.path.join(folder, name), "wb") as f:
                f.write(PNG)
        cls.j = Journal.load(cls.root)
        cls.t = cls.j.trades[0]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def document(self, **kw):
        return share.trade_document(self.root, self.j, self.t, self.book, **kw)

    def test_the_trade_is_in_it(self):
        text = without_pictures(self.document())
        for word in ("EURUSD", "long", "swing", "H4", "0.85%", "Win",
                     "Asian high swept.", "stop moved under the sweep",
                     "Target hit."):
            self.assertIn(word, text, word)
        # the picture of the update is carried like the rest
        self.assertIn("shots/update-01.png", share.shot_names(self.t))

    def test_it_names_the_plan_the_trade_followed(self):
        text = without_pictures(self.document())
        self.assertIn("Sweep of the Asian high", text)
        self.assertIn("12.08.2026 to 14.08.2026 · EURUSD", text)

    def test_the_r_is_the_figure_it_carries(self):
        r = self.j.r(self.t.id)
        self.assertIsNotNone(r)
        self.assertIn(f"{r:+.2f}", without_pictures(self.document()))

    def test_no_money_leaves_with_it(self):
        """The point of the whole module: a document says R and never a sum."""
        text = without_pictures(self.document())
        for figure in (PNL, START_BALANCE, self.j.balance("broker"),
                       self.j.computed[self.t.id].risk_money,
                       self.j.computed[self.t.id].balance_at_entry):
            for shape in (f"{figure:,.0f}".replace(",", " "),
                          f"{figure:,.0f}".replace(",", ""),
                          f"{figure:.2f}"):
                self.assertNotIn(shape, text, shape)

    def test_no_money_leaves_in_the_documents_of_a_period_or_a_selection(self):
        """The same guard over the two documents that are built from the
        figures of a period, where the money of a month is closest at hand."""
        from plainbook import reports
        r = reports.compose(self.root, self.j, "2026-08")
        texts = [without_pictures(share.report_document(self.root, self.j, r, shots=False)),
                 without_pictures(share.selection_document(
                     self.root, self.j, self.j.trades, "August", "the month", shots=False))]
        for text in texts:
            self.assertIn("EURUSD", text)
            for figure in (PNL, START_BALANCE, self.j.balance("broker"),
                           self.j.computed[self.t.id].risk_money,
                           self.j.computed[self.t.id].balance_at_entry):
                for shape in (f"{figure:,.0f}".replace(",", " "),
                              f"{figure:,.0f}".replace(",", ""),
                              f"{figure:.2f}"):
                    self.assertNotIn(shape, text, shape)

    def test_the_account_is_not_named(self):
        """Traders name accounts by their size; the footer promises the size
        stays home, so the name stays home with it."""
        text = without_pictures(self.document())
        self.assertNotIn("Broker", text)
        self.assertNotIn(">account<", text)

    def test_the_rules_are_ticked_the_way_the_page_ticks_them(self):
        text = without_pictures(self.document())
        self.assertIn("The level was swept", text)
        self.assertIn("Entered before the retest was done", text)
        self.assertIn("1 rule not met", text)
        self.assertIn("every rule held", text)      # the management rules

    def test_a_carried_document_needs_no_journal(self):
        """Nothing in the file points back at this machine."""
        text = self.document()
        self.assertEqual(text.count("data:image/png;base64,"), 4)
        self.assertNotIn('src="/shot/', text)
        self.assertNotIn("127.0.0.1", text)
        self.assertNotIn("localhost", text)

    def test_a_preview_points_at_the_journal_instead(self):
        text = self.document(carry=False)
        self.assertNotIn("data:image/png;base64,", text)
        self.assertEqual(text.count(f'src="/shot/{self.t.id}/'), 4)

    def plan_document(self, **kw):
        return share.plan_document(self.root, self.j, self.k,
                                   [t for t in self.j.trades
                                    if t.plan == self.k.id], **kw)

    def test_a_plan_is_shown_the_same_way(self):
        """The plan whole, with its trades in R, and no money anywhere."""
        text = without_pictures(self.plan_document())
        for word in ("Sweep of the Asian high", "12.08.2026 to 14.08.2026",
                     "bullish", "Higher lows into the level.",
                     "Buy the sweep of the Asian high only.",
                     "swept, waiting for the retest", "It played out.",
                     "Trades of this plan", "with the narrative: 1 trade"):
            self.assertIn(word, text, word)
        self.assertIn(f"{self.j.r(self.t.id):+.2f}", text)
        for figure in (PNL, START_BALANCE):
            for shape in (f"{figure:,.0f}".replace(",", " "),
                          f"{figure:,.0f}".replace(",", ""),
                          f"{figure:.2f}"):
                self.assertNotIn(shape, text, shape)
        self.assertEqual(self.plan_document().count("data:image/png;base64,"), 3)
        preview = self.plan_document(carry=False)
        self.assertNotIn("data:image/png;base64,", preview)
        self.assertEqual(preview.count(f'src="/plan-shot/{self.k.id}/'), 3)
        guess = share.weigh_plan(self.root, self.k)
        real = len(self.plan_document().encode("utf-8"))
        self.assertLess(abs(guess - real), real * 0.2)

    def test_a_missing_picture_does_not_kill_the_document(self):
        os.rename(os.path.join(store.trade_dir(self.root, self.t.id),
                               store.SHOTS, "idea-01.png"),
                  os.path.join(self.root, "gone.png"))
        try:
            text = self.document()
            self.assertIn("Asian high swept.", text)
            self.assertEqual(text.count("data:image/png;base64,"), 3)
        finally:
            os.rename(os.path.join(self.root, "gone.png"),
                      os.path.join(store.trade_dir(self.root, self.t.id),
                                   store.SHOTS, "idea-01.png"))

    def test_the_weight_is_told_before_the_file_is_made(self):
        """The preview says what the file will weigh, so the figure has to be
        near the truth: within a fifth of it."""
        guess = share.weigh(self.root, [self.t])
        real = len(self.document().encode("utf-8"))
        self.assertLess(abs(guess - real), real * 0.2)
        self.assertLess(share.weigh(self.root, [self.t], shots=False), guess)

    def test_a_selection_says_its_figures_in_r(self):
        text = without_pictures(
            share.selection_document(self.root, self.j, self.j.trades,
                                     "Trades", "the whole journal",
                                     shots=False))
        self.assertIn("EURUSD", text)
        self.assertIn("Σ R", text)
        self.assertNotIn(f"{PNL:,.0f}".replace(",", " "), text)

    def test_a_line_of_the_list_leads_to_its_trade(self):
        """The trades stand in full under the list, a line points at its
        trade and the trade points back. Without the screenshots it is the
        same file with the pictures left out, so a long stretch sent light
        still opens trade by trade."""
        full = share.selection_document(self.root, self.j, self.j.trades,
                                        "Trades", "the whole journal")
        at = share.anchor(self.t)
        self.assertIn(f'href="#{at}"', full)
        self.assertIn(f'<section class="trade" id="{at}"', full)
        self.assertIn('href="#trades"', full)
        self.assertIn('<div class="trades">', full)
        self.assertIn(share.HOW_TO_OPEN, full)
        plain = share.selection_document(self.root, self.j, self.j.trades,
                                         "Trades", "the whole journal",
                                         shots=False)
        self.assertIn(f'href="#{at}"', plain)
        self.assertIn(f'<section class="trade" id="{at}"', plain)
        self.assertIn(share.GO_SCRIPT, plain)
        self.assertIn(share.HOW_TO_OPEN, plain)
        self.assertNotIn("<img", plain.split('<div class="trades">')[1])

    def test_the_pages_of_a_file_lead_to_each_other(self):
        """Two trades in a file, the latest on top: it leads on to the
        earlier one, the earlier one back to it, and neither pretends to a
        neighbour it lacks."""
        later = replace(self.t, id="2026-08-15-01-eurusd",
                        opened=datetime(2026, 8, 15, 9), closed=datetime(2026, 8, 16),
                        idea=[], exit_images=[], conclusions="")
        pages = share.trade_pages(self.root, self.j, [later, self.t], None, True)
        first, second = share.anchor(later), share.anchor(self.t)
        self.assertLess(pages.index(f'id="{first}"'), pages.index(f'id="{second}"'))
        self.assertIn(f'href="#{second}">next', pages)
        self.assertIn(f'href="#{first}">&larr; previous', pages)
        self.assertNotIn(f'href="#{first}">next', pages)
        self.assertNotIn(f'href="#{second}">&larr; previous', pages)
        # the strip stands above and below each page, so twice a page
        self.assertEqual(pages.count('<span class="btn off">&larr; previous'), 2)
        self.assertEqual(pages.count('<span class="btn off">next'), 2)
        self.assertEqual(pages.count("1 of 2"), 2)
        self.assertEqual(pages.count("2 of 2"), 2)

    def test_the_owner_words_keep_their_shape(self):
        self.assertIn("<strong>kept</strong>", share.prose("what was **kept**"))
        self.assertIn("<li>one</li>", share.prose("- one\n- two"))

    def test_a_file_that_is_not_a_picture_is_not_carried(self):
        """Only the kinds in MIME travel; anything else is left behind."""
        folder = os.path.join(store.trade_dir(self.root, self.t.id), store.SHOTS)
        path = os.path.join(folder, "notes.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("private")
        try:
            self.assertEqual(share.data_url(path), "")
        finally:
            os.remove(path)

    def test_print_keeps_the_hash_target_and_breaks_between_trades(self):
        text = self.document()
        printed = text[text.index("@media print"):]
        self.assertIn(".sheet:has(.trade[id]:target) .report{display:block}",
                      printed)
        self.assertIn(".report + .trades > .trade:first-child{break-before:page",
                      printed)
        self.assertIn(".onscreen{display:none}", printed)
        self.assertIn(".bar,.ways{display:none}", printed)
        self.assertIn('<span class="onscreen">Press a line', share.HOW_TO_OPEN)

    def test_preview_and_file_draw_the_same_pictures(self):
        t = replace(self.t, exit_images=["shots/evil.svg"],
                    updates="stop moved\n![](shots/missing.png)")
        folder = os.path.join(store.trade_dir(self.root, t.id), store.SHOTS)
        path = os.path.join(folder, "evil.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write("<svg/>")
        try:
            kept = []
            for carry in (False, True):
                text = share.trade_document(self.root, self.j, t, self.book,
                                            carry=carry)
                self.assertNotIn("evil.svg", text)
                self.assertNotIn("missing.png", text)
                kept.append(text.count("<img"))
            self.assertEqual(kept[0], kept[1])
        finally:
            os.remove(path)


def png_of_pixels(rows):
    """A grey PNG from rows of 0 (black) and 255 (white), written by hand from
    the standard library, so that a scanner can read what a table holds."""
    height, width = len(rows), len(rows[0])
    lines = [b"\x00" + bytes(row) for row in rows]      # filter type: none

    def chunk(kind, data):
        body = kind + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body)))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(lines)))
            + chunk(b"IEND", b""))


def drawn_qr(tone=share.CARD_UP):
    """What `card_candle` really puts on the card, read back out of its SVG:
    the body of the candle, where the code starts in it, how big a module is
    and which modules are dark."""
    svg = share.card_candle(tone)
    rect = tuple(int(v) for v in re.search(
        rf'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)" rx="22" '
        rf'fill="{tone}"/>', svg).groups())
    off_x, off_y, scale = (int(v) for v in re.search(
        r'translate\((\d+) (\d+)\) scale\((\d+)\)', svg).groups())
    dark = set()
    for bar in re.findall(r'M(\d+) (\d+)h(\d+)v1h-\d+z',
                          re.search(r'scale\(\d+\)" d="([^"]+)"', svg).group(1)):
        left, top, run = (int(v) for v in bar)
        dark |= {(left + i, top) for i in range(run)}
    return svg, rect, (off_x, off_y), scale, dark


def grey(colour):
    """A #rrggbb colour as the grey a scanner sees."""
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return round(.299 * r + .587 * g + .114 * b)


def pair_place(svg):
    """Where the pair stands on a card and how big: its line is the second."""
    x, size = re.search(r'id="card-pair"[^>]* x="(\d+)" y="148"\s+font-size="(\d+)"',
                        svg).groups()
    return int(x), int(size)


def pair_size(svg):
    return pair_place(svg)[1]


class CardCase(unittest.TestCase):
    """The picture of a trade: the pair, the side, the R, the day, the entry
    price when there is one, and no money."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.save_account(cls.root, Account(id="broker", name="Hidden Prop Name",
                                             start_balance=START_BALANCE))
        cls.base = dict(account="broker", direction="long", style="swing",
                        entry_tf="H4", risk=0.85, result="Win", pnl=PNL,
                        opened=datetime(2026, 8, 12, 10, 30), opened_time=True,
                        closed=datetime(2026, 8, 14))
        for i, (pair, over) in enumerate([
                ("EURUSD", {}),
                ("GBPUSD", {"entry_price": 1.2634, "direction": "short",
                            "result": "Lose", "pnl": -PNL}),
                ("USDCHF", {"result": "BE", "pnl": 0.0}),
                ("A" * 14 + " vs " + "B" * 14 + " long pair name", {}),
                ("<b>&amp;", {}),
                ("pair not set", {}),
                ("XAUUSD", {"result": None, "pnl": None, "closed": None})]):
            store.save_trade(cls.root, Trade(
                id=f"2026-08-12-{i + 1:02d}-x", pair=pair, **{**cls.base, **over}))
        cls.j = Journal.load(cls.root)
        cls.by_pair = {t.pair: t for t in cls.j.trades}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def card(self, pair):
        t = self.by_pair[pair]
        return share.trade_card_svg(t, self.j.r(t.id))

    def test_it_says_the_pair_the_side_and_the_r(self):
        svg = self.card("EURUSD")
        r = self.j.r(self.by_pair["EURUSD"].id)
        self.assertIn(">EURUSD<", svg)
        self.assertIn(">LONG<", svg)
        self.assertIn(f">{r:+.2f}<tspan", svg)
        self.assertIn(f"{r:+.2f}R", svg.split(">")[0])       # the label says it whole
        self.assertIn(">12.08.2026<", svg)
        self.assertIn(">Plainbook<", svg)
        self.assertIn(share.REPO, svg)
        self.assertIn(f'fill="{share.CARD_UP}">+', svg)

    def test_a_loss_is_red_and_a_break_even_is_neither(self):
        loss = self.card("GBPUSD")
        self.assertIn(">SHORT<", loss)
        self.assertRegex(loss, rf'fill="{share.CARD_DOWN}">\u2212\d+\.\d\d<tspan')
        even = self.card("USDCHF")
        self.assertIn(f'fill="{share.CARD_FLAT}">0.00<tspan', even)
        self.assertNotIn(share.CARD_UP, even)
        self.assertNotIn(share.CARD_DOWN, even)

    def test_the_entry_price_is_a_row_only_when_it_was_written(self):
        self.assertIn(">1.2634<", self.card("GBPUSD"))
        self.assertIn(">Entry<", self.card("GBPUSD"))
        self.assertNotIn(">Entry<", self.card("EURUSD"))
        self.assertIn(">Opened<", self.card("EURUSD"))

    def test_no_money_and_no_account_on_the_card(self):
        for pair in ("EURUSD", "GBPUSD", "USDCHF"):
            svg = self.card(pair)
            for shape in ("98765", "4321", "Hidden Prop Name", "broker", "0.85",
                          "swing", "H4"):
                self.assertNotIn(shape, svg, (pair, shape))
            t = self.by_pair[pair]
            money = (f"{self.j.computed[t.id].risk_money:.2f}",
                     f"{self.j.computed[t.id].balance_at_entry:.0f}")
            for shape in money:
                self.assertNotIn(shape, svg)

    def test_it_stands_alone(self):
        svg = self.card("EURUSD")
        for attr in ('xmlns="http://www.w3.org/2000/svg"', 'width="1200"',
                     'height="675"', 'viewBox="0 0 1200 675"'):
            self.assertIn(attr, svg.split(">")[0])
        for bad in ("foreignObject", "<image", "<script", "gradient", "filter"):
            self.assertNotIn(bad, svg, bad)
        # the ruled page is as free of them as the rocket is
        t = self.by_pair["EURUSD"]
        plain = share.trade_card_svg(t, self.j.r(t.id), plain=True)
        for bad in ("foreignObject", "<image", "<script", "gradient", "filter"):
            self.assertNotIn(bad, plain, bad)
        self.assertNotEqual(plain, svg)

    def test_a_card_on_a_picture_has_the_one_named_gradient_and_nothing_else_loose(self):
        t = self.by_pair["EURUSD"]
        r = self.j.r(t.id)
        data = "data:image/png;base64,iVBORw0KGgo="
        svg = share.trade_card_svg(t, r, data)
        ET.fromstring(svg)
        self.assertEqual(svg.count("<image"), 1)
        self.assertIn(f'<image href="{data}"', svg)
        self.assertEqual(svg.count("<linearGradient"), 1)
        self.assertIn('id="card-fade"', svg)
        self.assertIn('fill="url(#card-fade)"', svg)
        self.assertRegex(svg, r'<stop offset="\.32" stop-color="[^"]+"/>'
                              r'<stop offset="\.52" [^>]*stop-opacity="0"/>')
        for bad in ("foreignObject", "<script", "filter"):
            self.assertNotIn(bad, svg, bad)
        # the references are inside it: the fade, the coins, and the picture itself
        self.assertEqual(re.findall(r'href="(?!#|data:)[^"]*"', svg), [])
        self.assertEqual(set(re.findall(r'url\(#([^)]+)\)', svg))
                         - set(re.findall(r' id="([^"]+)"', svg)), set())
        # the picture of the owner's is escaped like any text of theirs
        evil = share.trade_card_svg(t, r, 'data:image/png;base64,"><script>')
        self.assertNotIn("<script", evil)
        ET.fromstring(evil)

    def test_a_card_on_a_picture_says_what_the_other_one_says(self):
        t = self.by_pair["GBPUSD"]
        r = self.j.r(t.id)
        svg = share.trade_card_svg(t, r, "data:image/png;base64,AA==")
        for word in (">GBPUSD<", ">SHORT<", "\u2212", "12.08.2026",
                     "1.2634", share.REPO):
            self.assertIn(word, svg, word)
        for shape in ("98765", "4321", "Hidden Prop Name", "broker", "0.85", "swing", "H4"):
            self.assertNotIn(shape, svg, shape)

    def test_the_rocket_goes_up_for_a_long_and_down_for_a_short(self):
        up, down = share.card_rocket("long", share.CARD_UP), share.card_rocket("short", share.CARD_UP)
        self.assertIn("rotate(42)", up)
        self.assertIn("rotate(138)", down)
        self.assertEqual(share.card_rocket("long", share.CARD_UP), up)       # the same sky every time

    def test_the_thumbnails_of_the_strip_are_drawn_from_the_cards_own_pieces(self):
        t = self.by_pair["EURUSD"]
        rocket = share.card_thumb("rocket", t, self.j.r(t.id))
        plain = share.card_thumb("plain")
        for svg in (rocket, plain):
            ET.fromstring(svg)
            self.assertIn('viewBox="0 0 1200 675"', svg)
            self.assertNotIn("<image", svg)
        self.assertIn("M0 -320C92 -222", rocket)
        self.assertIn("M0 75H1200", plain)
        self.assertNotIn("M0 -320C92 -222", plain)

    def test_the_coins_bring_their_drawings_along(self):
        """A picture rasterised alone has no sprite of the page: everything a
        coin points at has to be inside the picture, or it comes out empty."""
        t = self.by_pair["EURUSD"]
        for pair in ("EURUSD", "ETHBTC", "XAUUSD", "US30"):
            svg = share.trade_card_svg(replace(t, pair=pair), 1.5)
            used = set(re.findall(r'href="#([^"]+)"', svg))
            used |= set(re.findall(r'url\(#([^)]+)\)', svg))
            self.assertTrue(used, pair)
            self.assertEqual(used - set(re.findall(r' id="([^"]+)"', svg)), set())
            self.assertEqual(re.findall(r'href="[^#]', svg), [])
            ET.fromstring(svg)

    def test_the_coin_behind_keeps_its_face_and_the_coins_their_scale(self):
        t = self.by_pair["EURUSD"]
        svg = share.trade_card_svg(replace(t, pair="ETHBTC"), 1.5)
        self.assertRegex(svg, r'href="#fl-\w+-b"')
        self.assertRegex(svg, r'<svg x="72" y="92" width="\d+" height="60" '
                              r'viewBox="0 0 30 18">')

    def test_a_coin_of_letters_keeps_them(self):
        t = self.by_pair["EURUSD"]
        svg = share.trade_card_svg(replace(t, pair="XYZ"), 1.5)
        self.assertIn(">XYZ</text>", svg)

    def test_nothing_is_drawn_over_the_code(self):
        """The body of the candle goes down first and the code on it; the wick
        before them both, and what follows stays left of the candle."""
        svg = share.card_candle(share.CARD_UP)
        wick, body = svg.index('width="8"'), svg.index('rx="22"')
        self.assertLess(wick, body)
        self.assertLess(body, svg.index("crispEdges"))
        self.assertEqual(svg.count(f'fill="{share.CARD_UP}"'), 2)

    def test_the_page_can_measure_the_pair(self):
        svg = self.card("EURUSD")
        self.assertRegex(svg, r'<text id="card-pair" data-room="\d+"')

    def test_a_pair_with_no_coins_starts_at_the_margin(self):
        t = replace(self.by_pair["EURUSD"], pair=PAIR_NOT_SET)
        svg = share.trade_card_svg(t, 1.5)
        self.assertNotIn("<use", svg)
        self.assertEqual(pair_place(svg)[0], share.CARD_LEFT)

    def test_a_long_pair_is_made_small(self):
        name = "A" * 14 + " vs " + "B" * 14 + " long pair name"
        self.assertGreater(len(name), 30)
        svg = self.card(name)
        size = pair_size(svg)
        self.assertLess(size, share.card_pair_size("EURUSD"))
        self.assertLessEqual(share.card_width(name) * size, share.CARD_ROOM)
        # the shortest names are not squeezed
        self.assertNotIn("textLength", self.card("EURUSD"))

    def stands_inside(self, pair):
        """The pair of a card is inside the room it has: by the size it was
        given, or pinned by textLength when the estimate says it would not."""
        t = replace(self.by_pair["EURUSD"], pair=pair)
        svg = share.trade_card_svg(t, 1.5)
        x, size = pair_place(svg)
        room = share.CARD_LEFT + share.CARD_ROOM - x
        pinned = re.search(r'textLength="(\d+)"', svg)
        if pinned:
            self.assertEqual(int(pinned.group(1)), room)
            self.assertGreater(share.card_width(pair) * size, room)
            self.assertEqual(size, share.CARD_PAIR_MIN)
        else:
            self.assertLessEqual(share.card_width(pair) * size, room)
        # what is left of the candle is the room: nothing reaches its body
        self.assertLess(x + room, share.CARD_CANDLE_X -
                        (share.QR_SIZE + 2 * share.QR_QUIET) * share.QR_PX // 2)
        ET.fromstring(svg)
        return size, bool(pinned)

    def test_wide_characters_count_as_wide(self):
        self.assertEqual(share.card_width("日本語"), 3.0)
        self.assertEqual(share.card_width("ＥＵＲ"), 3.0)       # full width Latin
        self.assertAlmostEqual(share.card_width("WM"), 2.3)
        self.assertAlmostEqual(share.card_width("EURUSD"), 6 * 0.72)
        self.assertAlmostEqual(share.card_width("us30"), 4 * 0.62)
        self.assertAlmostEqual(share.card_width("mw"), 1.9)
        self.assertAlmostEqual(share.card_width("\u0429"), 1.05)
        self.assertAlmostEqual(share.card_width("😀"), 1.35)

    def test_a_pair_of_wide_letters_stays_inside_the_card(self):
        cjk = "日本語の通貨ペアの名前はとても長い例です"[:19] + "ＡＢＣＤＥ"
        self.assertEqual(len(cjk), 24)
        cases = {cjk: None, "W" * 20: None, "WM" * 10: None, "W" * 34: None,
                 "日" * 60: None, "x" * 120: None, "A" * 14 + " vs " + "B" * 14: None}
        for pair in cases:
            self.stands_inside(pair)
        # more room is not taken by the narrow ones: the CJK pair is smaller
        # than the same number of Latin letters, the pinned ones stop at the least size
        self.assertLess(self.stands_inside(cjk)[0], self.stands_inside("A" * 24)[0])
        self.assertEqual(self.stands_inside("日" * 60), (share.CARD_PAIR_MIN, True))

    def test_the_price_never_has_an_exponent(self):
        for value, shown in ((1.08531, "1.08531"), (0.00001234, "0.00001234"),
                             (123456789012.5, "123456789012.5"), (1234.0, "1234"),
                             (1e22, "10000000000000000000000"), (100, "100"),
                             (0.5, "0.5"), (1.2634, "1.2634")):
            self.assertEqual(share.card_price(value), shown, value)
        t = replace(self.by_pair["EURUSD"], entry_price=0.00001234)
        svg = share.trade_card_svg(t, 1.5)
        self.assertIn(">0.00001234<", svg)
        self.assertNotRegex(svg, r">[0-9.]*e[-+]?[0-9]+<")

    def test_a_very_long_price_is_pinned_between_its_column_and_the_code(self):
        t = replace(self.by_pair["EURUSD"], entry_price=1e60)
        svg = share.trade_card_svg(t, 1.5)
        self.assertIn('textLength="330"', svg)
        # the second column: its value ends short of the body of the candle
        self.assertLess(share.CARD_LEFT + 310 + 74 + 330, share.CARD_CANDLE_X -
                        (share.QR_SIZE + 2 * share.QR_QUIET) * share.QR_PX // 2)

    def test_what_xml_refuses_is_dropped_from_the_pair(self):
        dirty = "EUR\x0b\x1bUSD\ufffe\uffff\x00\ud800"
        t = replace(self.by_pair["EURUSD"], pair=dirty)
        svg = share.trade_card_svg(t, 1.5)
        ET.fromstring(svg)                       # a refused character would raise
        self.assertIn(">EURUSD<", svg)
        self.assertIn('aria-label="EURUSD long, +1.50R"', svg)
        self.assertEqual(share.card_title(t), "EURUSD long card")
        self.assertEqual(share.card_pair_name(replace(t, pair="\x0b\x1b")),
                         share.PAIR_NOT_SET)
        self.assertEqual(share.xml_clean("a\tb\nc\r"), "a\tb\nc\r")

    def test_the_label_the_title_and_the_name_are_the_cards_own(self):
        t = self.by_pair["GBPUSD"]
        r = self.j.r(t.id)
        self.assertEqual(share.card_title(t), "GBPUSD short card")
        self.assertEqual(share.card_label(t, r), f"GBPUSD short, {r:+.2f}R")
        self.assertIn(f'aria-label="{share.card_label(t, r)}"',
                      share.trade_card_svg(t, r))
        self.assertEqual(share.card_file_name(t), "plainbook-GBPUSD-short-2026-08-12.png")
        self.assertNotIn(t.id, share.card_file_name(t))
        self.assertEqual(share.card_file_name(replace(t, pair="EUR/USD  x")),
                         "plainbook-EUR-USD-x-short-2026-08-12.png")
        self.assertEqual(share.card_file_name(replace(t, pair="日本語")),
                         "plainbook-short-2026-08-12.png")
        self.assertEqual(share.card_file_name(replace(t, pair="\x0b")),
                         "plainbook-short-2026-08-12.png")
        # the pair is free text in the label as well
        spiky = replace(t, pair="<b>&")
        self.assertIn('aria-label="&lt;b&gt;&amp; short,', share.trade_card_svg(spiky, r))

    def test_the_colour_follows_the_r_that_is_printed(self):
        t = self.by_pair["EURUSD"]
        for r, shown, fill in ((0.004, "0.00", share.CARD_FLAT),
                               (-0.004, "0.00", share.CARD_FLAT),
                               (0.0, "0.00", share.CARD_FLAT), (0.07, "+0.07", share.CARD_UP),
                               (-0.07, "\u22120.07", share.CARD_DOWN),
                               (2.35, "+2.35", share.CARD_UP)):
            svg = share.trade_card_svg(t, r)
            self.assertIn(f'fill="{fill}">{shown}<tspan', svg, r)
            self.assertNotIn("-0.00", svg)
            self.assertNotIn("\u22120.00", svg)

    def test_the_bar_of_the_share_is_the_bar_of_the_card(self):
        self.assertIn(share.BAR_CSS, share.CSS)
        page = share.card_preview("t", "", "<svg></svg>")
        self.assertIn(share.BAR_CSS, page)
        self.assertIn(":root{color-scheme:dark}", page)    # the date field of BAR_CSS has its own
        self.assertIn(".cardpic > svg{", page)

    def test_the_pair_is_free_text_and_stays_escaped(self):
        svg = self.card("<b>&amp;")
        self.assertIn(">&lt;b&gt;&amp;amp;<", svg)
        self.assertNotIn("<b>", svg)

    def test_a_pair_that_was_never_set_still_draws(self):
        self.assertIn(">pair not set<", self.card(share.PAIR_NOT_SET))

    def test_an_open_trade_has_no_card(self):
        open_trade = self.by_pair["XAUUSD"]
        self.assertFalse(share.card_ready(self.j, open_trade))
        self.assertTrue(share.card_ready(self.j, self.by_pair["EURUSD"]))

    def test_a_close_with_no_r_has_no_card(self):
        class Unmeasured:
            def r(self, trade_id):
                return None
        self.assertFalse(share.card_ready(Unmeasured(), self.by_pair["EURUSD"]))

    def test_the_card_holds_no_money_in_its_source(self):
        """Invariant 11, read off the code: the card is built from named
        fields and never from the money of a trade."""
        import inspect
        source = "".join(inspect.getsource(f) for f in (
            share.trade_card_svg, share.card_candle, share.card_qr,
            share.card_with_picture, share.card_rocket, share.card_small_candle,
            share.card_thumb, share.card_r_text,
            share.card_ready, share.card_preview))
        for word in ("pnl", "risk_money", "balance", "money("):
            self.assertNotIn(word, source, word)


class QrCase(unittest.TestCase):
    def test_the_table_is_33_by_33(self):
        self.assertEqual(len(share.QR_ROWS), 33)
        for row in share.QR_ROWS:
            self.assertEqual(len(row), 33)
            self.assertLessEqual(set(row), {"#", "."})

    def test_the_three_finders_stand_in_their_corners(self):
        finder = ["#######", "#.....#", "#.###.#", "#.###.#", "#.###.#",
                  "#.....#", "#######"]
        rows = share.QR_ROWS
        for top, left in ((0, 0), (0, 26), (26, 0)):
            self.assertEqual([r[left:left + 7] for r in rows[top:top + 7]], finder)
        # the fourth corner has none
        self.assertNotEqual([r[26:33] for r in rows[26:33]], finder)

    def test_a_module_is_a_whole_number_of_pixels(self):
        self.assertIsInstance(share.QR_PX, int)
        self.assertGreaterEqual(share.QR_PX, 5)
        self.assertGreaterEqual(share.QR_QUIET, 4)
        svg = share.card_qr(10, 20)
        self.assertIn("crispEdges", svg)
        self.assertEqual(svg.count("<path"), 1)

    def test_what_is_drawn_is_the_table_in_the_candle(self):
        svg, rect, (off_x, off_y), scale, dark = drawn_qr()
        side = (share.QR_SIZE + 2 * share.QR_QUIET) * share.QR_PX
        x, y, width, height = rect
        self.assertEqual(width, side)
        self.assertGreaterEqual(height, side)
        self.assertEqual(scale, share.QR_PX)
        # the code stands a quiet zone in from the corner of the body
        self.assertEqual((off_x, off_y), (x + share.QR_QUIET * share.QR_PX,
                                          y + share.QR_QUIET * share.QR_PX))
        self.assertEqual(dark, {(x, y) for y, row in enumerate(share.QR_ROWS)
                                for x, c in enumerate(row) if c == "#"})
        self.assertIn(f'fill="{GROUND}" shape-rendering="crispEdges"', svg)

    @unittest.skipUnless(shutil.which("qrencode"), "qrencode is not installed")
    def test_the_table_is_what_qrencode_makes_of_the_address(self):
        out = subprocess.run(["qrencode", "-l", "M", "-m", "0", "-t", "ASCII",
                              "https://" + share.REPO],
                             capture_output=True, text=True, timeout=30).stdout
        rows = tuple("".join("#" if line[i:i + 2] == "##" else "."
                             for i in range(0, 2 * share.QR_SIZE, 2))
                     for line in (x.ljust(2 * share.QR_SIZE)
                                  for x in out.splitlines()))
        self.assertEqual(rows, share.QR_ROWS)

    @unittest.skipUnless(shutil.which("zbarimg"), "zbarimg is not installed")
    def test_a_scanner_reads_the_address_off_every_candle(self):
        for tone in (share.CARD_UP, share.CARD_DOWN, share.CARD_FLAT):
            _, rect, (off_x, off_y), scale, dark = drawn_qr(tone)
            side = rect[2]
            grid = [bytearray([grey(tone)]) * side for _ in range(side)]
            for x, y in dark:
                for dy in range(scale):
                    for dx in range(scale):
                        grid[off_y - rect[1] + y * scale + dy][
                            off_x - rect[0] + x * scale + dx] = grey(GROUND)
            with tempfile.TemporaryDirectory() as folder:
                path = os.path.join(folder, "qr.png")
                with open(path, "wb") as f:
                    f.write(png_of_pixels(grid))
                out = subprocess.run(["zbarimg", "--quiet", "--raw", path],
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(out.stdout.strip(), "https://" + share.REPO, tone)

    def test_the_candles_stand_well_apart_from_the_code(self):
        """The tones are lighter than the palette for this: a phone has to
        tell the modules from the candle, from a screen, at an angle."""
        for tone in (share.CARD_UP, share.CARD_DOWN, share.CARD_FLAT):
            self.assertGreater(grey(tone) - grey(GROUND), 120, tone)


if __name__ == "__main__":
    unittest.main()
