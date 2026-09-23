#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The icons of a trading symbol: what a name is taken apart into."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import flags, html
from plainbook.model import PAIR_NOT_SET


class Parsing(unittest.TestCase):
    def test_pair_is_two_coins(self):
        self.assertEqual(flags.parts("EURUSD"), ["eu", "us"])
        self.assertEqual(flags.parts("gbpjpy"), ["gb", "jp"])
        self.assertEqual(flags.parts("XAUUSD"), ["xau", "us"])

    def test_separators_and_broker_suffixes(self):
        for name in ("EUR/USD", "EURUSD.pro", "EURUSD-ecn", "EURUSD_m",
                     "EUR_USD", "EUR-USD", "EURUSDm", "EURUSD.m"):
            self.assertEqual(flags.parts(name), ["eu", "us"], name)
        self.assertEqual(flags.parts("XAU_USD"), ["xau", "us"])
        self.assertEqual(flags.parts("US30_m"), ["us"])

    def test_index_is_one_coin(self):
        self.assertEqual(flags.parts("US30"), ["us"])
        self.assertEqual(flags.parts("GER40"), ["de"])

    def test_four_letter_quote(self):
        self.assertEqual(flags.parts("BTCUSDT"), ["btc", "usdt"])

    def test_unknown_symbol_keeps_its_letters(self):
        self.assertEqual(flags.parts("TSLA"), ["TSL"])
        self.assertEqual(flags.parts("SOLUSDT"), ["SOL", "usdt"])

    def test_no_symbol_no_icon(self):
        for name in ("", "   ", None, PAIR_NOT_SET):
            self.assertEqual(flags.parts(name), [], repr(name))


class Markup(unittest.TestCase):
    def test_every_code_has_a_drawing(self):
        for table in (flags.CURRENCIES, flags.INDICES):
            for code, icon_id in table.items():
                self.assertIn(icon_id, flags.FLAGS, code)

    def test_icon_refers_to_the_sprite(self):
        icon = flags.icon("EURUSD")
        self.assertIn('href="#fl-eu"', icon)
        self.assertIn('href="#fl-us"', icon)
        for icon_id in ("fl-eu", "fl-us"):
            self.assertIn(f'id="{icon_id}"', flags.SPRITE)

    def test_the_name_stays_next_to_the_icon(self):
        markup = html.pair("EURUSD")
        self.assertIn("EURUSD", markup)
        self.assertIn("<svg", markup)
        # ready markup must not be escaped a second time on its way to a page
        self.assertEqual(html.esc(markup), markup)

    def test_a_pair_that_is_not_set_is_only_text(self):
        self.assertNotIn("<svg", html.pair(PAIR_NOT_SET))

    def test_a_name_is_still_escaped(self):
        self.assertNotIn("<b>", html.pair("<b>x</b>"))
