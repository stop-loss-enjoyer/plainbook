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

    def test_a_suffix_after_a_separator_is_not_a_letter_of_the_quote(self):
        # with ADA known, USDCAD.a once read as USDC and ADA
        for name in ("USDCAD.a", "USDCAD_a", "USDCAD-ab"):
            self.assertEqual(flags.parts(name), ["us", "ca"], name)
        self.assertEqual(flags.parts("EUR_USD"), ["eu", "us"])
        self.assertEqual(flags.parts("BTC-USDT"), ["btc", "usdt"])

    def test_separators_and_broker_suffixes(self):
        for name in ("EUR/USD", "EURUSD.pro", "EURUSD-ecn", "EURUSD_m",
                     "EUR_USD", "EUR-USD", "EURUSDm", "EURUSD.m"):
            self.assertEqual(flags.parts(name), ["eu", "us"], name)
        self.assertEqual(flags.parts("XAU_USD"), ["xau", "us"])
        self.assertEqual(flags.parts("US30_m"), ["us"])

    def test_index_is_one_coin(self):
        self.assertEqual(flags.parts("US30"), ["us"])
        self.assertEqual(flags.parts("GER40"), ["de"])

    def test_copper_is_its_own_coin(self):
        # Bybit writes it COPPER-C, other brokers XCUUSD
        self.assertEqual(flags.parts("COPPER-C"), ["xcu"])
        self.assertEqual(flags.parts("COPPER"), ["xcu"])
        self.assertEqual(flags.parts("XCUUSD"), ["xcu", "us"])
        self.assertEqual(flags.parts("XCU/USD"), ["xcu", "us"])

    def test_four_letter_quote(self):
        self.assertEqual(flags.parts("BTCUSDT"), ["btc", "usdt"])

    def test_broker_suffix_after_a_known_quote(self):
        self.assertEqual(flags.parts("USDCHFm"), ["us", "ch"])
        self.assertEqual(flags.parts("USDCADc"), ["us", "ca"])
        self.assertEqual(flags.parts("USDTRYm"), ["us", "tr"])
        self.assertEqual(flags.parts("BTCUSDTm"), ["btc", "usdt"])
        self.assertEqual(flags.parts("EURUSDm"), ["eu", "us"])

    def test_unknown_symbol_keeps_its_letters(self):
        self.assertEqual(flags.parts("TSLA"), ["TSL"])
        # a coin the table does not know yet, against a quote it does
        self.assertEqual(flags.parts("FETUSDT"), ["FET", "usdt"])
        self.assertEqual(flags.parts("SHOP"), ["SHO"])

    def test_more_currencies_and_coins(self):
        self.assertEqual(flags.parts("USDSAR"), ["us", "sa"])
        self.assertEqual(flags.parts("EURRON"), ["eu", "ro"])
        self.assertEqual(flags.parts("SOLUSD"), ["sol", "us"])
        self.assertEqual(flags.parts("SOLUSDT"), ["sol", "usdt"])
        self.assertEqual(flags.parts("DOGEUSD"), ["doge", "us"])
        self.assertEqual(flags.parts("BTCSOL"), ["btc", "sol"])

    def test_gas_in_every_spelling(self):
        for name in ("XNGUSD", "NGASUSD", "XNG/USD", "XNGUSD.pro"):
            self.assertEqual(flags.parts(name), ["gas", "us"], name)
        for name in ("NATGAS", "NGAS", "NG", "NATGAS.cash", "XNG"):
            self.assertEqual(flags.parts(name), ["gas"], name)

    def test_the_farm_goods_are_one_coin_each(self):
        for name, icon_id in (("COFFEE", "coffee"), ("COCOA", "cocoa"),
                              ("SUGAR", "sugar"), ("WHEAT", "wheat"),
                              ("CORN", "corn"), ("SOYBEAN", "soy"),
                              ("COTTON", "cotton")):
            self.assertEqual(flags.parts(name), [icon_id], name)

    def test_more_indices(self):
        self.assertEqual(flags.parts("VIX"), ["us"])
        self.assertEqual(flags.parts("SA40"), ["za"])
        self.assertEqual(flags.parts("TWIX"), ["tw"])
        self.assertEqual(flags.parts("AUT20"), ["at"])
        self.assertEqual(flags.parts("POL20"), ["pl"])
        self.assertEqual(flags.parts("NIFTY50"), ["in"])

    def test_a_short_code_does_not_steal_a_letter(self):
        # OP is a coin, and USDC is a coin: the peso must still win USDCOP
        self.assertEqual(flags.parts("USDCOP"), ["us", "co"])
        self.assertEqual(flags.parts("USDCOPm"), ["us", "co"])
        self.assertEqual(flags.parts("OPUSD"), ["op", "us"])
        self.assertEqual(flags.parts("OPUSDT"), ["op", "usdt"])
        # a ticker that merely ends in the two letters is not a pair
        for name in ("SHOP", "DROP", "STOP"):
            self.assertEqual(flags.parts(name), [name[:3]], name)

    def test_five_letter_base(self):
        self.assertEqual(flags.parts("MATICUSD"), ["pol", "us"])
        self.assertEqual(flags.parts("BRENTUSD"), ["oil", "us"])

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


class Catalogue(unittest.TestCase):
    def test_groups_in_the_order_the_accounts_tab_draws_them(self):
        self.assertEqual([title for title, _ in flags.CATALOGUE],
                         ["Forex majors", "Forex minors", "Forex exotics",
                          "Metals", "Energy", "Commodities", "Indices",
                          "Crypto"])

    def test_every_symbol_is_drawn_with_no_lettered_coin(self):
        for title, symbols in flags.CATALOGUE:
            for symbol in symbols:
                faces = flags.parts(symbol)
                self.assertTrue(faces, symbol)
                for face in faces:
                    self.assertIn(face, flags.FLAGS, f"{title}: {symbol}")

    def test_no_symbol_twice(self):
        everything = [s for _, symbols in flags.CATALOGUE for s in symbols]
        self.assertEqual(len(everything), len(set(everything)))

    def test_it_is_a_catalogue_not_a_stub(self):
        total = sum(len(symbols) for _, symbols in flags.CATALOGUE)
        self.assertTrue(100 <= total <= 140, total)
        for title, symbols in flags.CATALOGUE:
            self.assertTrue(symbols, title)

    def test_the_majors_and_minors_are_the_pairs_they_say(self):
        groups = dict(flags.CATALOGUE)
        self.assertEqual(len(groups["Forex majors"]), 7)
        self.assertEqual(len(groups["Forex minors"]), 21)
        for symbol in groups["Forex majors"]:
            self.assertIn("USD", symbol)
        for symbol in groups["Forex minors"]:
            self.assertNotIn("USD", symbol)
