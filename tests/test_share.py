#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What leaves the journal: the document holds the trade and not the money."""
import os
import re
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import share, store
from plainbook.balances import Journal
from plainbook.model import (Account, IdeaBlock, Plan, Playbook, Rule, Setup, Trade)

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
        """With the trades in full under the list, a line points at its
        trade and the trade points back; without them there is nothing to
        point at, and the list is plain."""
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
        self.assertNotIn(f'href="#{at}"', plain)
        self.assertNotIn(share.GO_SCRIPT, plain)
        self.assertNotIn(share.HOW_TO_OPEN, plain)

    def test_the_pages_of_a_file_lead_to_each_other(self):
        """Two trades in a file: the first leads on to the second, the second
        back to the first, and neither pretends to a neighbour it lacks."""
        later = replace(self.t, id="2026-08-15-01-eurusd",
                        opened=datetime(2026, 8, 15, 9), closed=datetime(2026, 8, 16),
                        idea=[], exit_images=[], conclusions="")
        pages = share.trade_pages(self.root, self.j, [later, self.t], None, True)
        first, second = share.anchor(self.t), share.anchor(later)
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


if __name__ == "__main__":
    unittest.main()
